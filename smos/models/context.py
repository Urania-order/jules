"""Context model representing domain situations, conditions, or structural settings.

Note: Context ≠ Metadata.
Context is a first-class entity that can participate in relations via ContextRelation.

Note: Context ≠ Fact.
Default epistemic_status is EpistemicStatus.OBSERVED.
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.sql import func
from smos.core.database import Base
from smos.models.models import EpistemicStatus, RelationType


class Context(Base):
    """SQLAlchemy model for Context entities.
    
    A context represents structural or situational parameters.
    Context ≠ metadata: Context is a first-class object that can participate in relations.
    Context ≠ fact: registering a context defaults to OBSERVED epistemic status.
    """

    __tablename__ = "contexts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    components = Column(JSON, default=list)
    source = Column(String, nullable=True)
    epistemic_status = Column(
        Enum(EpistemicStatus),
        default=EpistemicStatus.OBSERVED,
        nullable=False,
    )
    temporal_scope = Column(String, nullable=True)
    spatial_scope = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    provenance = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        """Serialize Context to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "components": self.components if self.components is not None else [],
            "source": self.source,
            "epistemic_status": self.epistemic_status.value if isinstance(self.epistemic_status, EpistemicStatus) else self.epistemic_status,
            "temporal_scope": self.temporal_scope,
            "spatial_scope": self.spatial_scope,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "provenance": self.provenance if self.provenance is not None else {},
        }


class ContextRelation(Base):
    """SQLAlchemy model for relationships between Context entities."""

    __tablename__ = "context_relations"

    id = Column(Integer, primary_key=True, index=True)
    source_context_id = Column(Integer, ForeignKey("contexts.id"), nullable=False)
    target_context_id = Column(Integer, ForeignKey("contexts.id"), nullable=False)
    relation_type = Column(Enum(RelationType), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    provenance = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        """Serialize ContextRelation to a dictionary."""
        return {
            "id": self.id,
            "source_context_id": self.source_context_id,
            "target_context_id": self.target_context_id,
            "relation_type": self.relation_type.value if isinstance(self.relation_type, RelationType) else self.relation_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "provenance": self.provenance if self.provenance is not None else {},
        }
