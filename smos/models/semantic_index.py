from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint, func
from smos.core.database import Base


class SemanticIndexEntry(Base):
    """Derived, rebuildable semantic vector index entry for canonical entities.

    Stores polymorphic references (entity_type, entity_id) with vector representations.
    Is NOT a source of truth and does not maintain foreign key constraints to canonical tables.
    """

    __tablename__ = "semantic_index_entries"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, index=True, nullable=False)
    entity_id = Column(Integer, index=True, nullable=False)
    text_hash = Column(String, nullable=False)
    vector = Column(JSON, nullable=False)
    dimension = Column(Integer, nullable=False)
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "model_name", name="uix_semantic_index_entity_model"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "text_hash": self.text_hash,
            "dimension": self.dimension,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
