from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Float, Boolean
from sqlalchemy.sql import func
from smos.core.database import Base

class EpistemicLayer(Base):
    __tablename__ = "epistemic_layers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String) # e.g., OBSERVED_FACT, VERIFIED_SCIENCE, FICTION, BEYOND_CONSENSUS
    confidence_level = Column(Float, default=1.0)
    evidence_type = Column(String, default="DIRECT") # DIRECT, ARCHAEOLOGICAL, etc.

class IntellectualCluster(Base):
    __tablename__ = "intellectual_clusters"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String, nullable=True)
    domains = Column(JSON, default=[])
    members = Column(JSON, default=[]) # List of Cosmonaut IDs
    is_provisional = Column(Boolean, default=False)
    human_sponsor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="ACTIVE") # PROVISIONAL, ACTIVE, ARCHIVED
    dormant_topics = Column(JSON, default=[])
    activation_threshold = Column(Float, default=0.5)
    ambassador_id = Column(Integer, ForeignKey("cosmonauts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ClusterRelation(Base):
    __tablename__ = "cluster_relations"
    id = Column(Integer, primary_key=True, index=True)
    source_cluster_id = Column(Integer, ForeignKey("intellectual_clusters.id"))
    target_cluster_id = Column(Integer, ForeignKey("intellectual_clusters.id"))
    distance = Column(Float, default=1.0)
    interaction_type = Column(String) # INSPIRES, SHARES_PATTERNS, CONFLICTS
