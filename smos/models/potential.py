"""Potential Phenomenon model representing phenomena that could emerge.

Note: Potential Phenomenon ≠ Prediction.
- Prediction: epistemic claim about what WILL happen (forward-looking).
- Potential Phenomenon: modal/structural representation of what COULD emerge,
  conditional on conditions/contexts/constraints.
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum, JSON
from sqlalchemy.sql import func
import enum
from smos.core.database import Base


class PotentialStatus(str, enum.Enum):
    """Statuses of potential phenomena."""

    POSSIBLE = "POSSIBLE"
    UNLIKELY = "UNLIKELY"
    BLOCKED = "BLOCKED"
    TEMPORARILY_BLOCKED = "TEMPORARILY_BLOCKED"
    STRUCTURALLY_BLOCKED = "STRUCTURALLY_BLOCKED"
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
    def from_str(cls, value: str) -> "PotentialStatus":
        """Parse string value into PotentialStatus (case-insensitive)."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Invalid PotentialStatus: {value}")


class PotentialPhenomenon(Base):
    """SQLAlchemy model for PotentialPhenomenon entities.

    Potential Phenomenon ≠ Prediction.
    - Prediction: epistemic claim about what WILL happen (forward-looking).
    - Potential Phenomenon: modal/structural representation of what COULD emerge,
      conditional on conditions/contexts/constraints.
    """

    __tablename__ = "potential_phenomena"

    id = Column(Integer, primary_key=True, index=True)
    phenomenon = Column(String, index=True, nullable=False)
    status = Column(
        Enum(PotentialStatus),
        default=PotentialStatus.UNKNOWN,
        nullable=False,
    )
    required_conditions = Column(JSON, default=list)
    supporting_contexts = Column(JSON, default=list)
    blocking_constraints = Column(JSON, default=list)
    dependencies = Column(JSON, default=list)
    expected_impacts = Column(JSON, default=list)
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
        """Serialize PotentialPhenomenon to a dictionary."""
        return {
            "id": self.id,
            "phenomenon": self.phenomenon,
            "status": self.status.value if isinstance(self.status, PotentialStatus) else self.status,
            "required_conditions": self.required_conditions if self.required_conditions is not None else [],
            "supporting_contexts": self.supporting_contexts if self.supporting_contexts is not None else [],
            "blocking_constraints": self.blocking_constraints if self.blocking_constraints is not None else [],
            "dependencies": self.dependencies if self.dependencies is not None else [],
            "expected_impacts": self.expected_impacts if self.expected_impacts is not None else [],
            "provenance": self.provenance if self.provenance is not None else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
