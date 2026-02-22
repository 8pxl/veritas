from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# --- 1. Organization ---
class OrganizationCreate(BaseModel):
    name: str
    url: str = ""
    logo_url: Optional[str] = None

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    logo_url: Optional[str] = None

class Organization(BaseModel):
    id: int
    name: str
    url: str
    logo_url: Optional[str] = None

# --- 2. People ---
class PersonCreate(BaseModel):
    name: str
    organization: str
    role: Optional[str] = None

class PersonUpdate(BaseModel):
    name: Optional[str] = None
    organization: Optional[str] = None
    role: Optional[str] = None

class Person(BaseModel):
    name: str
    position: Optional[str] = None
    id: str
    organization: Organization

# --- 3. Video ---
class VideoCreate(BaseModel):
    video_id: str
    video_path: str
    title: str
    description: Optional[str] = None
    video_url: str
    time: datetime

class VideoUpdate(BaseModel):
    video_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    time: Optional[datetime] = None

class Video(BaseModel):
    video_id: str
    video_path: str
    title: str
    description: Optional[str] = None
    video_url: str
    time: datetime

# --- 4. Proposition ---
class PropositionCreate(BaseModel):
    speaker_id: str
    statement: str
    verify_at: datetime
    video_id: str

class PropositionUpdate(BaseModel):
    speaker_id: Optional[str] = None
    statement: Optional[str] = None
    verify_at: Optional[datetime] = None
    video_id: Optional[str] = None
    verdict: Optional[str] = None
    verdictReasoning: Optional[str] = None
    verifiedAt: Optional[datetime] = None

class Proposition(BaseModel):
    id: int
    speaker: Person
    statement: str
    verifyAt: datetime
    video: Video
    verdict: Optional[str] = None
    verdictReasoning: Optional[str] = None
    verifiedAt: Optional[datetime] = None
