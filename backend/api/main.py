from contextlib import asynccontextmanager
import threading
import time
import os
import logging

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text
from database import engine, get_db, SessionLocal, Base
from models import OrganizationDB, PersonDB, VideoDB, PropositionDB
from structures import (
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    Person,
    PersonCreate,
    PersonUpdate,
    Video,
    VideoCreate,
    VideoUpdate,
    Proposition,
    PropositionCreate,
    PropositionUpdate,
    VerdictCounts,
    OverallStats,
    PersonStats,
    OrganizationStats,
    VideoStats,
    LeaderboardEntry,
    RunningAvgPoint,
    OrgRunningAverage,
    TopOrgsRunningAvgResponse,
)
from verifier import verify_proposition
from typing import List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func, case
import uuid

logger = logging.getLogger(__name__)


def _model_dump(obj, **kwargs):
    """Pydantic v1/v2 compatible model serialization."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(**kwargs)
    return obj.dict(**kwargs)


Base.metadata.create_all(bind=engine)


# --- Background verification job ---
def _verify_all_unverified():
    """Verify all propositions with verdict IS NULL."""
    db = SessionLocal()
    try:
        props = db.query(PropositionDB).filter(PropositionDB.verdict.is_(None)).all()
        if not props:
            return 0
        count = 0
        for p in props:
            try:
                speaker = db.get(PersonDB, p.speaker_id)
                org = db.get(OrganizationDB, speaker.organization_id)
                video = db.get(VideoDB, p.video_id)
                result = verify_proposition(
                    statement=p.statement,
                    speaker_name=speaker.name,
                    speaker_org=org.name,
                    video_title=video.title,
                    date_stated=video.time,
                    verify_at=p.verify_at,
                )
                p.verdict = result["verdict"]
                p.verdict_reasoning = result["reasoning"]
                p.verified_at = datetime.utcnow()
                db.commit()
                count += 1
                logger.info(f"Verified proposition {p.id}: {result['verdict']}")
            except Exception:
                logger.exception(f"Failed to verify proposition {p.id}")
                db.rollback()
        return count
    finally:
        db.close()


def _dedup_propositions():
    """Remove duplicate propositions (same speaker_id + statement + video_id), keeping the lowest id."""
    db = SessionLocal()
    try:
        # Find groups with duplicates
        dupes = (
            db.query(
                PropositionDB.speaker_id,
                PropositionDB.statement,
                PropositionDB.video_id,
                func.min(PropositionDB.id).label("keep_id"),
                func.count(PropositionDB.id).label("cnt"),
            )
            .group_by(
                PropositionDB.speaker_id,
                PropositionDB.statement,
                PropositionDB.video_id,
            )
            .having(func.count(PropositionDB.id) > 1)
            .all()
        )
        removed = 0
        for row in dupes:
            extras = (
                db.query(PropositionDB)
                .filter(
                    PropositionDB.speaker_id == row.speaker_id,
                    PropositionDB.statement == row.statement,
                    PropositionDB.video_id == row.video_id,
                    PropositionDB.id != row.keep_id,
                )
                .all()
            )
            for p in extras:
                db.delete(p)
                removed += 1
        if removed:
            db.commit()
            logger.info(f"Dedup: removed {removed} duplicate propositions")
        return removed
    finally:
        db.close()


def _background_verifier(stop_event: threading.Event):
    """Daemon thread that verifies propositions every 10 minutes."""
    while not stop_event.is_set():
        try:
            n = _verify_all_unverified()
            if n:
                logger.info(f"Background verifier: verified {n} propositions")
        except Exception:
            logger.exception("Background verifier error")
        stop_event.wait(600)  # 10 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    _dedup_propositions()
    stop_event = threading.Event()
    t = threading.Thread(target=_background_verifier, args=(stop_event,), daemon=True)
    t.start()
    logger.info("Background proposition verifier started")
    yield
    stop_event.set()
    t.join(timeout=5)
    logger.info("Background proposition verifier stopped")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


# --- Helpers ---
def _org_to_schema(org: OrganizationDB) -> Organization:
    return Organization(id=org.id, name=org.name, url=org.url, logo_url=org.logo_url)


def _person_to_schema(p: PersonDB, org: OrganizationDB) -> Person:
    return Person(
        id=p.id, name=p.name, position=p.position, organization=_org_to_schema(org)
    )


def _video_to_schema(v: VideoDB) -> Video:
    return Video(
        video_id=v.video_id,
        video_path=v.video_path,
        title=v.title,
        description=v.description,
        video_url=v.video_url,
        time=v.time,
    )


def _prop_to_schema(
    p: PropositionDB, speaker: PersonDB, org: OrganizationDB, video: VideoDB
) -> Proposition:
    return Proposition(
        id=p.id,
        speaker=_person_to_schema(speaker, org),
        statement=p.statement,
        verifyAt=p.verify_at,
        video=_video_to_schema(video),
        verdict=p.verdict,
        verdictReasoning=p.verdict_reasoning,
        verifiedAt=p.verified_at,
    )


# ========== Organization CRUD ==========


@app.post("/organizations", response_model=Organization)
def create_organization(org: OrganizationCreate, db: Session = Depends(get_db)):
    db_org = OrganizationDB(name=org.name, url=org.url, logo_url=org.logo_url)
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    return _org_to_schema(db_org)


@app.get("/organizations", response_model=List[Organization])
def list_organizations(db: Session = Depends(get_db)):
    return [_org_to_schema(o) for o in db.query(OrganizationDB).all()]


@app.get("/organizations/{org_id}", response_model=Organization)
def get_organization(org_id: int, db: Session = Depends(get_db)):
    org = db.get(OrganizationDB, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _org_to_schema(org)


@app.put("/organizations/{org_id}", response_model=Organization)
def update_organization(
    org_id: int, data: OrganizationUpdate, db: Session = Depends(get_db)
):
    org = db.get(OrganizationDB, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for field, value in _model_dump(data, exclude_unset=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return _org_to_schema(org)


@app.delete("/organizations/{org_id}")
def delete_organization(org_id: int, db: Session = Depends(get_db)):
    org = db.get(OrganizationDB, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    db.delete(org)
    db.commit()
    return {"ok": True}


# ========== Person CRUD ==========


def _resolve_org(db: Session, org_name: str) -> OrganizationDB:
    """Look up org by name; create if missing."""
    org = db.query(OrganizationDB).filter(OrganizationDB.name == org_name).first()
    if not org:
        org = OrganizationDB(name=org_name, url="")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


@app.post("/people", response_model=Person)
def create_person(person: PersonCreate, db: Session = Depends(get_db)):
    org = _resolve_org(db, person.organization)
    person_id = str(uuid.uuid4())
    db_person = PersonDB(
        id=person_id, name=person.name, position=person.role, organization_id=org.id
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return _person_to_schema(db_person, org)


@app.get("/people", response_model=List[Person])
def list_people(db: Session = Depends(get_db)):
    people = db.query(PersonDB).all()
    return [
        _person_to_schema(p, db.get(OrganizationDB, p.organization_id)) for p in people
    ]


@app.get("/people/search", response_model=List[Person])
def search_people(
    q: str = Query(
        ..., min_length=1, description="Search query (name, position, or org)"
    ),
    top_k: int = Query(5, ge=1, le=50, description="Number of results"),
    db: Session = Depends(get_db),
):
    """Fuzzy search people by name, position, or organization using trigram similarity + substring matching."""
    rows = db.execute(
        sql_text("""
            SELECT p.id, p.name, p.position,
                   o.id AS org_id, o.name AS org_name, o.url AS org_url, o.logo_url AS org_logo_url,
                   GREATEST(
                       similarity(p.name, :q),
                       similarity(COALESCE(p.position, ''), :q),
                       similarity(o.name, :q)
                   ) AS score
            FROM people p
            JOIN organizations o ON o.id = p.organization_id
            WHERE similarity(p.name, :q) > 0.1
               OR similarity(COALESCE(p.position, ''), :q) > 0.1
               OR similarity(o.name, :q) > 0.1
               OR p.name ILIKE '%' || :q || '%'
               OR COALESCE(p.position, '') ILIKE '%' || :q || '%'
               OR o.name ILIKE '%' || :q || '%'
            ORDER BY score DESC
            LIMIT :k
        """),
        {"q": q, "k": top_k},
    ).fetchall()

    return [
        Person(
            id=row.id,
            name=row.name,
            position=row.position,
            organization=Organization(
                id=row.org_id,
                name=row.org_name,
                url=row.org_url,
                logo_url=row.org_logo_url,
            ),
        )
        for row in rows
    ]


@app.get("/people/{person_id}", response_model=Person)
def get_person(person_id: str, db: Session = Depends(get_db)):
    p = db.get(PersonDB, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    return _person_to_schema(p, db.get(OrganizationDB, p.organization_id))


@app.put("/people/{person_id}", response_model=Person)
def update_person(person_id: str, data: PersonUpdate, db: Session = Depends(get_db)):
    p = db.get(PersonDB, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    updates = _model_dump(data, exclude_unset=True)
    if "name" in updates:
        p.name = updates["name"]
    if "role" in updates:
        p.position = updates["role"]
    if "organization" in updates:
        org = _resolve_org(db, updates["organization"])
        p.organization_id = org.id
    db.commit()
    db.refresh(p)
    return _person_to_schema(p, db.get(OrganizationDB, p.organization_id))


@app.delete("/people/{person_id}")
def delete_person(person_id: str, db: Session = Depends(get_db)):
    p = db.get(PersonDB, person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# ========== Video CRUD ==========


@app.post("/videos", response_model=Video)
def create_video(video: VideoCreate, db: Session = Depends(get_db)):
    db_video = db.get(VideoDB, video.video_id)
    if db_video:
        return _video_to_schema(db_video)
    db_video = VideoDB(**_model_dump(video))
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return _video_to_schema(db_video)


@app.get("/videos/{video_id}/stream")
def stream_video(video_id: str):
    ## Check ext: webm, mp4, mkv
    exts = ["mp4", "webm", "mkv"]
    media_types = [
        "video/mp4",
        "video/webm",
        "video/x-matroska",
    ]
    for ext, media_type in zip(exts, media_types):
        path = f"./video_storage/{video_id}.{ext}"
        if os.path.exists(path):
            return FileResponse(
                path, media_type=media_type, filename=f"{video_id}.{ext}"
            )


@app.get("/videos/{video_id}/results")
def stream_json(video_id: str, db: Session = Depends(get_db)):
    import json

    storage_path = f"/usr/share/vid/{video_id}.json"
    res = []

    db_propositions = (
        db.query(PropositionDB).filter(PropositionDB.video_id == video_id).all()
    )

    with open(storage_path) as f:
        data = json.load(f)
        data = data["statement_analyses"]
        for e in data:
            # find the exact match
            db_prop = None
            for p in db_propositions:
                if p.statement == e["statement"]:
                    db_prop = p
                    break
            e["verifyAt"] = db_prop.verify_at.isoformat() if db_prop else None
            e["verdict"] = db_prop.verdict if db_prop else None
            e["verdictReasoning"] = db_prop.verdict_reasoning if db_prop else None
            e["verifiedAt"] = db_prop.verified_at.isoformat() if db_prop else None

            res.append(e)

    return res


@app.get("/videos", response_model=List[Video])
def list_videos(db: Session = Depends(get_db)):
    return [_video_to_schema(v) for v in db.query(VideoDB).all()]


@app.get("/videos/{video_id}", response_model=Video)
def get_video(video_id: str, db: Session = Depends(get_db)):
    v = db.get(VideoDB, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    return _video_to_schema(v)


@app.put("/videos/{video_id}", response_model=Video)
def update_video(video_id: str, data: VideoUpdate, db: Session = Depends(get_db)):
    v = db.get(VideoDB, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    for field, value in _model_dump(data, exclude_unset=True).items():
        setattr(v, field, value)
    db.commit()
    db.refresh(v)
    return _video_to_schema(v)


@app.delete("/videos/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    v = db.get(VideoDB, video_id)
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    db.delete(v)
    db.commit()
    return {"ok": True}


# ========== Proposition CRUD ==========


@app.post("/propositions", response_model=Proposition)
def create_proposition(prop: PropositionCreate, db: Session = Depends(get_db)):
    speaker = db.get(PersonDB, prop.speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    video = db.get(VideoDB, prop.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    # Dedup: return existing proposition if same speaker+statement+video
    existing = (
        db.query(PropositionDB)
        .filter(
            PropositionDB.speaker_id == prop.speaker_id,
            PropositionDB.statement == prop.statement,
            PropositionDB.video_id == prop.video_id,
        )
        .first()
    )
    if existing:
        org = db.get(OrganizationDB, speaker.organization_id)
        return _prop_to_schema(existing, speaker, org, video)
    db_prop = PropositionDB(
        speaker_id=prop.speaker_id,
        statement=prop.statement,
        verify_at=prop.verify_at,
        video_id=prop.video_id,
    )
    db.add(db_prop)
    db.commit()
    db.refresh(db_prop)
    org = db.get(OrganizationDB, speaker.organization_id)
    return _prop_to_schema(db_prop, speaker, org, video)


@app.get("/propositions", response_model=List[Proposition])
def list_propositions(db: Session = Depends(get_db)):
    props = db.query(PropositionDB).all()
    results = []
    for p in props:
        speaker = db.get(PersonDB, p.speaker_id)
        org = db.get(OrganizationDB, speaker.organization_id)
        video = db.get(VideoDB, p.video_id)
        results.append(_prop_to_schema(p, speaker, org, video))
    return results


@app.get("/propositions/{prop_id}", response_model=Proposition)
def get_proposition(prop_id: int, db: Session = Depends(get_db)):
    p = db.get(PropositionDB, prop_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposition not found")
    speaker = db.get(PersonDB, p.speaker_id)
    org = db.get(OrganizationDB, speaker.organization_id)
    video = db.get(VideoDB, p.video_id)
    return _prop_to_schema(p, speaker, org, video)


@app.put("/propositions/{prop_id}", response_model=Proposition)
def update_proposition(
    prop_id: int, data: PropositionUpdate, db: Session = Depends(get_db)
):
    p = db.get(PropositionDB, prop_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposition not found")
    updates = _model_dump(data, exclude_unset=True)
    if "speaker_id" in updates:
        if not db.get(PersonDB, updates["speaker_id"]):
            raise HTTPException(status_code=404, detail="Speaker not found")
        p.speaker_id = updates["speaker_id"]
    if "statement" in updates:
        p.statement = updates["statement"]
    if "verify_at" in updates:
        p.verify_at = updates["verify_at"]
    if "video_id" in updates:
        if not db.get(VideoDB, updates["video_id"]):
            raise HTTPException(status_code=404, detail="Video not found")
        p.video_id = updates["video_id"]
    db.commit()
    db.refresh(p)
    speaker = db.get(PersonDB, p.speaker_id)
    org = db.get(OrganizationDB, speaker.organization_id)
    video = db.get(VideoDB, p.video_id)
    return _prop_to_schema(p, speaker, org, video)


@app.delete("/propositions/{prop_id}")
def delete_proposition(prop_id: int, db: Session = Depends(get_db)):
    p = db.get(PropositionDB, prop_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposition not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# ========== Proposition Verification ==========


@app.post("/propositions/{prop_id}/verify", response_model=Proposition)
def verify_single_proposition(prop_id: int, db: Session = Depends(get_db)):
    p = db.get(PropositionDB, prop_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposition not found")
    speaker = db.get(PersonDB, p.speaker_id)
    org = db.get(OrganizationDB, speaker.organization_id)
    video = db.get(VideoDB, p.video_id)
    result = verify_proposition(
        statement=p.statement,
        speaker_name=speaker.name,
        speaker_org=org.name,
        video_title=video.title,
        date_stated=video.time,
        verify_at=p.verify_at,
    )
    p.verdict = result["verdict"]
    p.verdict_reasoning = result["reasoning"]
    p.verified_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return _prop_to_schema(p, speaker, org, video)


@app.post("/propositions/verify-all")
def verify_all_propositions():
    count = _verify_all_unverified()
    return {"verified": count}


# ========== Propositions by Person ==========


@app.get("/people/{person_id}/propositions", response_model=List[Proposition])
def get_propositions_by_person(person_id: str, db: Session = Depends(get_db)):
    person_db = db.get(PersonDB, person_id)
    if not person_db:
        raise HTTPException(status_code=404, detail="Person not found")
    org_db = db.get(OrganizationDB, person_db.organization_id)
    props = db.query(PropositionDB).filter(PropositionDB.speaker_id == person_id).all()
    return [
        _prop_to_schema(p, person_db, org_db, db.get(VideoDB, p.video_id))
        for p in props
    ]


# ========== Stats ==========


def _verdict_counts(props) -> VerdictCounts:
    counts = VerdictCounts()
    for p in props:
        if p.verdict == "true":
            counts.true += 1
        elif p.verdict == "false":
            counts.false += 1
        elif p.verdict == "future":
            counts.future += 1
        else:
            counts.unverified += 1
    return counts


def _truth_index(counts: VerdictCounts) -> Optional[float]:
    decided = counts.true + counts.false
    if decided == 0:
        return None
    return round(counts.true / decided, 4)


@app.get("/stats/overview", response_model=OverallStats)
def get_overall_stats(db: Session = Depends(get_db)):
    """Overall truth index and verdict breakdown across all propositions."""
    props = db.query(PropositionDB).all()
    counts = _verdict_counts(props)
    return OverallStats(
        total=len(props),
        verified=counts.true + counts.false + counts.future,
        verdictCounts=counts,
        truthIndex=_truth_index(counts),
    )


@app.get("/stats/by-person", response_model=List[PersonStats])
def get_stats_by_person(db: Session = Depends(get_db)):
    """Truth index per speaker, sorted by number of propositions descending."""
    rows = db.query(PropositionDB.speaker_id).group_by(PropositionDB.speaker_id).all()
    results = []
    for (speaker_id,) in rows:
        person = db.get(PersonDB, speaker_id)
        org = db.get(OrganizationDB, person.organization_id)
        props = (
            db.query(PropositionDB).filter(PropositionDB.speaker_id == speaker_id).all()
        )
        counts = _verdict_counts(props)
        results.append(
            PersonStats(
                person=_person_to_schema(person, org),
                total=len(props),
                verdictCounts=counts,
                truthIndex=_truth_index(counts),
            )
        )
    results.sort(key=lambda s: s.total, reverse=True)
    return results


@app.get("/stats/by-organization", response_model=List[OrganizationStats])
def get_stats_by_organization(db: Session = Depends(get_db)):
    """Truth index per organization, sorted by number of propositions descending."""
    rows = (
        db.query(PersonDB.organization_id)
        .join(PropositionDB, PropositionDB.speaker_id == PersonDB.id)
        .group_by(PersonDB.organization_id)
        .all()
    )
    results = []
    for (org_id,) in rows:
        org = db.get(OrganizationDB, org_id)
        props = (
            db.query(PropositionDB)
            .join(PersonDB, PropositionDB.speaker_id == PersonDB.id)
            .filter(PersonDB.organization_id == org_id)
            .all()
        )
        counts = _verdict_counts(props)
        results.append(
            OrganizationStats(
                organization=_org_to_schema(org),
                total=len(props),
                verdictCounts=counts,
                truthIndex=_truth_index(counts),
            )
        )
    results.sort(key=lambda s: s.total, reverse=True)
    return results


@app.get("/stats/by-video", response_model=List[VideoStats])
def get_stats_by_video(db: Session = Depends(get_db)):
    """Truth index per video, sorted by number of propositions descending."""
    rows = db.query(PropositionDB.video_id).group_by(PropositionDB.video_id).all()
    results = []
    for (video_id,) in rows:
        video = db.get(VideoDB, video_id)
        props = db.query(PropositionDB).filter(PropositionDB.video_id == video_id).all()
        counts = _verdict_counts(props)
        results.append(
            VideoStats(
                video=_video_to_schema(video),
                total=len(props),
                verdictCounts=counts,
                truthIndex=_truth_index(counts),
            )
        )
    results.sort(key=lambda s: s.total, reverse=True)
    return results


@app.get("/stats/leaderboard", response_model=List[LeaderboardEntry])
def get_truth_leaderboard(
    order: str = Query("most_honest", regex="^(most_honest|biggest_liars)$"),
    min_claims: int = Query(
        1, ge=1, description="Minimum true+false claims to qualify"
    ),
    db: Session = Depends(get_db),
):
    """Rank speakers by truth index using a **Bayesian average**.

    The Bayesian truth index shrinks each speaker's raw true-ratio toward
    the global mean, weighted by how many decided claims they have
    relative to the average speaker:

        bayesian_truth_index = (C * m + true_count) / (C + decided)

    where
        C = mean number of decided claims across *all* speakers
        m = global true ratio   (sum of true / sum of decided)

    Speakers with few claims are pulled toward the global average,
    while speakers with many claims are dominated by their own ratio.

    `most_honest` = highest truth index first,
    `biggest_liars` = lowest truth index first.
    Only includes speakers with at least `min_claims` decided (true/false)
    propositions."""

    # -- gather per-speaker counts in a single pass --
    rows = db.query(PropositionDB.speaker_id).group_by(PropositionDB.speaker_id).all()
    speaker_data: list[tuple] = []  # (speaker_id, counts, decided)
    global_true_sum = 0
    global_decided_sum = 0

    for (speaker_id,) in rows:
        props = (
            db.query(PropositionDB).filter(PropositionDB.speaker_id == speaker_id).all()
        )
        counts = _verdict_counts(props)
        decided = counts.true + counts.false
        speaker_data.append((speaker_id, counts, len(props), decided))
        global_true_sum += counts.true
        global_decided_sum += decided

    # -- compute Bayesian prior --
    num_speakers = len(speaker_data)
    if num_speakers == 0 or global_decided_sum == 0:
        return []
    C = global_decided_sum / num_speakers  # avg decided claims per speaker
    m = global_true_sum / global_decided_sum  # global truth ratio

    # -- build leaderboard entries --
    entries: list[LeaderboardEntry] = []
    for speaker_id, counts, total, decided in speaker_data:
        if decided < min_claims:
            continue
        bayesian_ti = round((C * m + counts.true) / (C + decided), 4)
        person = db.get(PersonDB, speaker_id)
        org = db.get(OrganizationDB, person.organization_id)
        entries.append(
            LeaderboardEntry(
                person=_person_to_schema(person, org),
                truthIndex=bayesian_ti,
                total=total,
                trueCount=counts.true,
                falseCount=counts.false,
            )
        )

    reverse = order == "most_honest"
    entries.sort(key=lambda e: (e.truthIndex or 0, e.total), reverse=reverse)
    return entries


@app.get("/people/{person_id}/stats", response_model=PersonStats)
def get_person_stats(person_id: str, db: Session = Depends(get_db)):
    """Truth index and verdict breakdown for a single speaker."""
    person = db.get(PersonDB, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    org = db.get(OrganizationDB, person.organization_id)
    props = db.query(PropositionDB).filter(PropositionDB.speaker_id == person_id).all()
    counts = _verdict_counts(props)
    return PersonStats(
        person=_person_to_schema(person, org),
        total=len(props),
        verdictCounts=counts,
        truthIndex=_truth_index(counts),
    )


@app.get("/organizations/{org_id}/stats", response_model=OrganizationStats)
def get_organization_stats(org_id: int, db: Session = Depends(get_db)):
    """Truth index and verdict breakdown for a single organization."""
    org = db.get(OrganizationDB, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    props = (
        db.query(PropositionDB)
        .join(PersonDB, PropositionDB.speaker_id == PersonDB.id)
        .filter(PersonDB.organization_id == org_id)
        .all()
    )
    counts = _verdict_counts(props)
    return OrganizationStats(
        organization=_org_to_schema(org),
        total=len(props),
        verdictCounts=counts,
        truthIndex=_truth_index(counts),
    )


@app.get("/stats/top-orgs-running-avg", response_model=TopOrgsRunningAvgResponse)
def get_top_orgs_running_avg(
    top_n: int = Query(
        5, ge=1, le=50, description="Number of top organizations to return"
    ),
    db: Session = Depends(get_db),
):
    """Return the running-average truth index for the top N organizations.

    1. Determine each organization's truth index over the **last year** using
       only decided (true / false) propositions whose `verify_at` falls within
       the past 365 days.
    2. Pick the top `top_n` organizations by that recent truth index.
    3. For each selected organization, compute the **running average** truth
       index from the earliest proposition date to the latest, emitting one
       data-point per calendar day that has at least one decided proposition.
    """
    now = datetime.utcnow()
    one_year_ago = now - timedelta(days=365)

    # -- Step 1: collect all orgs and their decided propositions in the last year --
    recent_props = (
        db.query(PropositionDB, PersonDB.organization_id)
        .join(PersonDB, PropositionDB.speaker_id == PersonDB.id)
        .filter(
            PropositionDB.verify_at >= one_year_ago,
            PropositionDB.verdict.in_(["true", "false"]),
        )
        .all()
    )

    org_recent: dict[int, dict] = defaultdict(lambda: {"true": 0, "decided": 0})
    for prop, org_id in recent_props:
        org_recent[org_id]["decided"] += 1
        if prop.verdict == "true":
            org_recent[org_id]["true"] += 1

    # truth index for last year per org
    org_recent_ti: dict[int, float] = {}
    for org_id, c in org_recent.items():
        if c["decided"] > 0:
            org_recent_ti[org_id] = c["true"] / c["decided"]

    if not org_recent_ti:
        return TopOrgsRunningAvgResponse(topN=top_n, organizations=[])

    # -- Step 2: pick top N by recent truth index --
    sorted_orgs = sorted(org_recent_ti.items(), key=lambda x: x[1], reverse=True)
    top_org_ids = [org_id for org_id, _ in sorted_orgs[:top_n]]

    # -- Step 3: running average from earliest to latest for each top org --
    all_props = (
        db.query(PropositionDB, PersonDB.organization_id)
        .join(PersonDB, PropositionDB.speaker_id == PersonDB.id)
        .filter(
            PersonDB.organization_id.in_(top_org_ids),
            PropositionDB.verdict.in_(["true", "false"]),
        )
        .order_by(PropositionDB.verify_at)
        .all()
    )

    # group by org
    org_props: dict[int, list] = defaultdict(list)
    for prop, org_id in all_props:
        org_props[org_id].append(prop)

    results: list[OrgRunningAverage] = []
    for org_id in top_org_ids:
        org = db.get(OrganizationDB, org_id)
        props = org_props.get(org_id, [])
        if not props:
            continue

        cum_true = 0
        cum_decided = 0
        series: list[RunningAvgPoint] = []

        # aggregate by calendar date, emit one point per day with activity
        day_buckets: dict[str, dict] = {}
        for p in props:
            day = p.verify_at.strftime("%Y-%m-%d")
            if day not in day_buckets:
                day_buckets[day] = {"true": 0, "decided": 0}
            day_buckets[day]["decided"] += 1
            if p.verdict == "true":
                day_buckets[day]["true"] += 1

        for day in sorted(day_buckets):
            cum_true += day_buckets[day]["true"]
            cum_decided += day_buckets[day]["decided"]
            series.append(
                RunningAvgPoint(
                    date=day,
                    truthIndex=round(cum_true / cum_decided, 4),
                    cumulativeTrue=cum_true,
                    cumulativeDecided=cum_decided,
                )
            )

        results.append(
            OrgRunningAverage(
                organization=_org_to_schema(org),
                currentTruthIndex=series[-1].truthIndex,
                series=series,
            )
        )

    # maintain the ranking order
    rank = {oid: i for i, oid in enumerate(top_org_ids)}
    results.sort(key=lambda r: rank[r.organization.id])
    return TopOrgsRunningAvgResponse(topN=top_n, organizations=results)
