from contextlib import asynccontextmanager
import threading
import time
import logging

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
)
from verifier import verify_proposition
from typing import List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

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
    allow_origins=["*"],        # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],        # Allow all HTTP methods
    allow_headers=["*"],        # Allow all headers
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
    for field, value in data.model_dump(exclude_unset=True).items():
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
    updates = data.model_dump(exclude_unset=True)
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
    db_video = VideoDB(**video.dict())
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return _video_to_schema(db_video)


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
    for field, value in data.model_dump(exclude_unset=True).items():
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
    updates = data.model_dump(exclude_unset=True)
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
