from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float, Boolean
from sqlalchemy.sql import func
from smos.core.database import Base

class KnowledgeImpact(Base):
    __tablename__ = "knowledge_impacts"
    id = Column(Integer, primary_key=True, index=True)
    source_node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    target_domain = Column(String)
    influence_type = Column(String) # DIRECT_INFLUENCE, INDIRECT_INFLUENCE, BEHAVIORAL_SHIFT, etc.
    confidence = Column(Float, default=0.0)
    cascade_depth = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class KnowledgeActivation(Base):
    __tablename__ = "knowledge_activations"
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    usage_count = Column(Integer, default=0)
    real_world_application = Column(JSON, default=[])
    decay_rate = Column(Float, default=0.01)
    last_reinforced_at = Column(DateTime(timezone=True), server_default=func.now())

class ValueAssessment(Base):
    __tablename__ = "value_assessments"
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    knowledge_value = Column(Float, default=0.0)
    human_benefit = Column(Float, default=0.0)
    environmental_impact = Column(Float, default=0.0)
    social_impact = Column(Float, default=0.0)
    uncertainty = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ResearchPortal(Base):
    __tablename__ = "research_portals"
    id = Column(Integer, primary_key=True, index=True)
    hypothesis_id = Column(Integer, ForeignKey("hypotheses.id"))
    budget = Column(Float, default=0.0)
    status = Column(String, default="OPEN") # OPEN, FUNDED, COMPLETED
    outcomes = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ResearchSponsorship(Base):
    __tablename__ = "research_sponsorships"
    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(Integer, ForeignKey("research_portals.id"))
    sponsor_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    is_transparent = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("memory_nodes.id"))
    created_by_id = Column(Integer, ForeignKey("cosmonauts.id"))
    contributors = Column(JSON, default=[]) # List of cosmonaut IDs
    evidence_links = Column(JSON, default=[])
    revision_history = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ReputationCredit(Base):
    __tablename__ = "reputation_credits"
    id = Column(Integer, primary_key=True, index=True)
    cosmonaut_id = Column(Integer, ForeignKey("cosmonauts.id"))
    amount = Column(Float, default=0.0)
    reason = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TranslatedMessage(Base):
    __tablename__ = "translated_messages"
    id = Column(Integer, primary_key=True, index=True)
    original_content = Column(String)
    interpreted_meaning = Column(String)
    suggested_rewrite = Column(String)
    emotional_weight = Column(Float, default=0.0)
    risk_of_conflict = Column(Float, default=0.0)
    source_cosmonaut_id = Column(Integer, ForeignKey("cosmonauts.id"))
    target_behavior_profile_id = Column(Integer, ForeignKey("behavior_profiles.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
