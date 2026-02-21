from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# --- 1. Organization Structure ---
class Organization(BaseModel):
    id: int
    name: str
    url: str
    logo_url: Optional[str] = None

# --- 2. People Structure ---
class Person(BaseModel):
    name: str
    position: Optional[str] = None
    id: str
    organization: Organization


# --- 3. Video Structure (The Top Level) ---
# This "Has Many" Propositions
class Video(BaseModel):
    video_id: str
    video_path: str
    title: str
    description: Optional[str] = None
    video_url: str
    time: datetime
    
# --- 4. Proposition Structure ---
# This "Belongs To" a Video Segment
class Proposition(BaseModel):
    id: int
    speaker: Person
    statement: str
    verifyAt: datetime
    video: Video
