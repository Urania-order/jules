from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float, Enum
from sqlalchemy.sql import func
import enum
from smos.core.database import Base

class SessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"

class CognitiveSession(Base):
    __tablename__ = "cognitive_sessions"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    topic = Column(String)
    participants = Column(JSON, default=[]) # List of user IDs
    agents = Column(JSON, default=[]) # List of agent names
    active_timeline_id = Column(Integer, ForeignKey("timelines.id"))
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Thought(Base):
    __tablename__ = "thoughts"
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"))
    timeline_id = Column(Integer, ForeignKey("timelines.id"))
    content = Column(String)
    references = Column(JSON, default=[]) # List of memory node or thought IDs
    confidence = Column(Float, default=1.0)
    emotional_weight = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
