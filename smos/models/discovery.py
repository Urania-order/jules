from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float
from sqlalchemy.sql import func
from smos.core.database import Base

class LostKnowledge(Base):
    __tablename__ = "lost_knowledge"
    id = Column(Integer, primary_key=True, index=True)
    artifacts = Column(JSON, default=[])
    known_facts = Column(JSON, default=[])
    unknowns = Column(JSON, default=[])
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Hypothesis(Base):
    __tablename__ = "hypotheses"
    id = Column(Integer, primary_key=True, index=True)
    claim = Column(String)
    evidence = Column(JSON, default=[])
    confidence = Column(Float, default=0.0)
    lost_knowledge_id = Column(Integer, ForeignKey("lost_knowledge.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DiscoveryRecovery(Base):
    __tablename__ = "discovery_recoveries"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=True)
    hypotheses = Column(JSON, default=[])
    experimental_results = Column(JSON, default=[])
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
