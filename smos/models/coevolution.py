from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float
from sqlalchemy.sql import func
from smos.core.database import Base

class UnderstandingValidation(Base):
    __tablename__ = "understanding_validations"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("cosmonauts.id"))
    human_id = Column(Integer, ForeignKey("users.id"))
    original_interpretation = Column(String)
    human_feedback = Column(String)
    revised_interpretation = Column(String, nullable=True)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ComprehensionTest(Base):
    __tablename__ = "comprehension_tests"
    id = Column(Integer, primary_key=True, index=True)
    idea_id = Column(Integer, nullable=True) # ID of memory node or thought
    llm_explanation = Column(String)
    human_explanation = Column(String)
    similarity_score = Column(Float, default=0.0)
    disagreements = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
