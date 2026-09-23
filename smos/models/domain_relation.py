"""DomainRelation model representing cross-domain edges between Phenomenon, Context, Constraint, and PotentialPhenomenon.

Note: DomainRelation is the canonical domain relation layer.
It connects domain entities (source_type/source_id -> target_type/target_id)
without imposing causality or replacing type-specific relations (Relation, ContextRelation, etc.).
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON, Float
from sqlalchemy.sql import func
from smos.core.database import Base
from smos.models.models import EpistemicStatus, RelationType


class DomainRelation(Base):
    """SQLAlchemy model for cross-domain relations between domain entities."""

    __tablename__ = "domain_relations"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, nullable=False)  # "phenomenon" | "context" | "constraint" | "potential"
    source_id = Column(Integer, nullable=False)
    target_type = Column(String, nullable=False)  # "phenomenon" | "context" | "constraint" | "potential"
    target_id = Column(Integer, nullable=False)
    relation_type = Column(Enum(RelationType), nullable=False)
    epistemic_status = Column(
        Enum(EpistemicStatus),
        default=EpistemicStatus.OBSERVED,
        nullable=True,
    )
    provenance = Column(JSON, default=dict)
    evidence = Column(JSON, default=list)
    confidence = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> dict:
        """Serialize DomainRelation to a dictionary."""
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value if isinstance(self.relation_type, RelationType) else self.relation_type,
            "epistemic_status": self.epistemic_status.value if isinstance(self.epistemic_status, EpistemicStatus) else self.epistemic_status,
            "provenance": self.provenance if self.provenance is not None else {},
            "evidence": self.evidence if self.evidence is not None else [],
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
