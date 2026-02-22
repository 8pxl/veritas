from pydantic import BaseModel
from typing import Optional, List
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


# --- 5. Stats ---
class VerdictCounts(BaseModel):
    true: int = 0
    false: int = 0
    future: int = 0
    unverified: int = 0

class OverallStats(BaseModel):
    total: int
    verified: int
    verdictCounts: VerdictCounts
    truthIndex: Optional[float] = None  # true / (true + false), null if no true/false

class PersonStats(BaseModel):
    person: Person
    total: int
    verdictCounts: VerdictCounts
    truthIndex: Optional[float] = None

class OrganizationStats(BaseModel):
    organization: Organization
    total: int
    verdictCounts: VerdictCounts
    truthIndex: Optional[float] = None

class VideoStats(BaseModel):
    video: Video
    total: int
    verdictCounts: VerdictCounts
    truthIndex: Optional[float] = None

class LeaderboardEntry(BaseModel):
    person: Person
    truthIndex: Optional[float] = None
    total: int
    trueCount: int
    falseCount: int


class RunningAvgPoint(BaseModel):
    date: str                       # ISO date string (YYYY-MM-DD)
    truthIndex: float               # running average truth index up to this date
    cumulativeTrue: int
    cumulativeDecided: int


class OrgRunningAverage(BaseModel):
    organization: Organization
    currentTruthIndex: float        # latest cumulative truth index
    series: List[RunningAvgPoint]   # chronological running average points


class TopOrgsRunningAvgResponse(BaseModel):
    topN: int
    organizations: List[OrgRunningAverage]
