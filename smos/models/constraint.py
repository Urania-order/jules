"""Constraint model representing limiting conditions, boundaries, or structural restrictions.

Note: Constraint ≠ Cause.
A Constraint represents a limiting condition or bounding envelope, NOT a causal agent.
Constraints restrict the space of possible states or actions without causing events.
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON, Float
from sqlalchemy.sql import func
import enum
from smos.core.database import Base


class ConstraintType(str, enum.Enum):
    """Types of domain constraints."""

    PHYSICAL = "PHYSICAL"
    ECONOMIC = "ECONOMIC"
    LEGAL = "LEGAL"
    SOCIAL = "SOCIAL"
    TECHNICAL = "TECHNICAL"
    ECOLOGICAL = "ECOLOGICAL"
    INFORMATIONAL = "INFORMATIONAL"
    ORGANIZATIONAL = "ORGANIZATIONAL"
    SECURITY = "SECURITY"
    INFRASTRUCTURAL = "INFRASTRUCTURAL"
    TEMPORAL = "TEMPORAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_upper = value.strip().upper()
            for member in cls:
                if member.name.upper() == val_upper or member.value.upper() == val_upper:
                    return member
        return None

    @classmethod
    def from_str(cls, value: str) -> "ConstraintType":
        """Parse string value into ConstraintType (case-insensitive)."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid ConstraintType: {value}")


class ConstraintStatus(str, enum.Enum):
    """Statuses of domain constraints."""

    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_upper = value.strip().upper()
            for member in cls:
                if member.name.upper() == val_upper or member.value.upper() == val_upper:
                    return member
        return None

    @classmethod
    def from_str(cls, value: str) -> "ConstraintStatus":
        """Parse string value into ConstraintStatus (case-insensitive)."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid ConstraintStatus: {value}")


class Constraint(Base):
    """SQLAlchemy model for Constraint entities.

    Constraint ≠ Cause:
    A constraint is a limiting condition or structural boundary, not a causal agent.
    Registering or updating a constraint does not create or infer causal relationships.
    """

    __tablename__ = "constraints"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    type = Column(
        Enum(ConstraintType),
        default=ConstraintType.UNKNOWN,
        nullable=False,
    )
    strength = Column(Float, nullable=True)  # 0.0-1.0
    status = Column(
        Enum(ConstraintStatus),
        default=ConstraintStatus.UNKNOWN,
        nullable=False,
    )
    evidence = Column(JSON, default=list)
    context = Column(String, nullable=True)  # free-form context ref (or "context:<id>")
    confidence = Column(Float, default=0.5)  # 0.0-1.0
    provenance = Column(JSON, default=dict)
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
        """Serialize Constraint to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type.value if isinstance(self.type, ConstraintType) else self.type,
            "strength": self.strength,
            "status": self.status.value if isinstance(self.status, ConstraintStatus) else self.status,
            "evidence": self.evidence if self.evidence is not None else [],
            "context": self.context,
            "confidence": self.confidence,
            "provenance": self.provenance if self.provenance is not None else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
