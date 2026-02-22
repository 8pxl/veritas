from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class OrganizationDB(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    logo_url = Column(String, nullable=True)

class PersonDB(Base):
    __tablename__ = "people"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    position = Column(String, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    organization = relationship("OrganizationDB")

class VideoDB(Base):
    __tablename__ = "videos"
    video_id = Column(String, primary_key=True, index=True)
    video_path = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    video_url = Column(String, nullable=False)
    time = Column(DateTime, nullable=False)

class PropositionDB(Base):
    __tablename__ = "propositions"
    id = Column(Integer, primary_key=True, index=True)
    speaker_id = Column(String, ForeignKey("people.id"), nullable=False)
    statement = Column(Text, nullable=False)
    verify_at = Column(DateTime, nullable=False)
    video_id = Column(String, ForeignKey("videos.video_id"), nullable=False)
    verdict = Column(String, nullable=True)
    verdict_reasoning = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)

    speaker = relationship("PersonDB")
    video = relationship("VideoDB")