from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text
from database import engine, get_db, Base
from models import OrganizationDB, PersonDB, VideoDB, PropositionDB
from structures import Organization, Person, Video, Proposition
from typing import List

Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- Organization ---
@app.post("/organizations", response_model=Organization)
def create_organization(org: Organization, db: Session = Depends(get_db)):
    db_org = OrganizationDB(**org.model_dump())
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    return db_org

# --- Person ---
@app.post("/people", response_model=Person)
def create_person(person: Person, db: Session = Depends(get_db)):
    # Ensure the organization exists
    org = db.get(OrganizationDB, person.organization.id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    db_person = PersonDB(
        id=person.id,
        name=person.name,
        position=person.position,
        organization_id=person.organization.id,
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return person

# --- Video ---
@app.post("/videos", response_model=Video)
def create_video(video: Video, db: Session = Depends(get_db)):
    db_video = VideoDB(**video.model_dump())
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

# --- Proposition ---
@app.post("/propositions", response_model=Proposition)
def create_proposition(prop: Proposition, db: Session = Depends(get_db)):
    # Ensure speaker and video exist
    speaker = db.get(PersonDB, prop.speaker.id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    video = db.get(VideoDB, prop.video.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    db_prop = PropositionDB(
        id=prop.id,
        speaker_id=prop.speaker.id,
        statement=prop.statement,
        verify_at=prop.verifyAt,
        video_id=prop.video.video_id,
    )
    db.add(db_prop)
    db.commit()
    db.refresh(db_prop)
    return prop

# --- Fuzzy Search ---
@app.get("/people/search", response_model=List[Person])
def search_people(
    q: str = Query(..., min_length=1, description="Search query (name, position, or org)"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results"),
    db: Session = Depends(get_db),
):
    """Fuzzy search people by name, position, or organization using trigram similarity."""
    rows = db.execute(
        sql_text("""
            SELECT p.id, p.name, p.position, p.organization_id,
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
            ORDER BY score DESC
            LIMIT :k
        """),
        {"q": q, "k": top_k},
    ).fetchall()

    people: List[Person] = []
    for row in rows:
        org_db = db.get(OrganizationDB, row.organization_id)
        people.append(
            Person(
                id=row.id,
                name=row.name,
                position=row.position,
                organization=Organization(
                    id=org_db.id,
                    name=org_db.name,
                    url=org_db.url,
                    logo_url=org_db.logo_url,
                ),
            )
        )
    return people