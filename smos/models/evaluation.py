"""Evaluation models and status definition (TASK L-05A).

Provides EvaluationStatus enum and EvaluationRecord database model for persistent,
append-only evaluation tracking without mutating target epistemic status.

CRITICAL INVARIANTS:
1. Append-only: Evaluation records are never updated or deleted.
2. No automatic epistemic status mutation: Evaluation status represents interpretation against criteria,
   not truth or fact.
3. Target references are polymorphic without rigid foreign keys.
"""

import enum
from typing import Any, Dict

from sqlalchemy import Column, DateTime, Enum, Integer, JSON, String
from sqlalchemy.sql import func

from smos.core.database import Base


class EvaluationStatus(str, enum.Enum):
    """Explicit outcome statuses for evaluation against criteria.

    - CONFIRMED: available evidence satisfies the explicit evaluation criteria.
    - REFUTED: available evidence contradicts the explicit evaluation criteria.
    - INCONCLUSIVE: evaluation was performed, but available valid observations do not
                    distinguish adequately between competing outcomes.
    - UNDETERMINED: a defensible evaluation cannot be established because required inputs,
                    criteria, or necessary information are missing or invalid.
    """

    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNDETERMINED = "UNDETERMINED"


class EvaluationRecord(Base):
    """Persistent database record for evaluation historical tracking.

    Stores audit trail of evaluation results without mutating target entity state.
    """

    __tablename__ = "evaluation_records"

    id = Column(Integer, primary_key=True, index=True)

    # Target reference (polymorphic)
    target_type = Column(String, nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    prediction_id = Column(Integer, nullable=True, index=True)

    # Evaluation outcome
    status = Column(
        Enum(EvaluationStatus),
        default=EvaluationStatus.UNDETERMINED,
        nullable=False,
    )

    # Criteria reference & version
    criteria_id = Column(String, nullable=False)
    criteria_version = Column(String, default="1.0.0")

    # Timing and temporal cutoff
    evaluated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    as_of = Column(DateTime(timezone=True), nullable=True)

    # Observation evidence references
    observation_refs = Column(JSON, default=list)
    excluded_observation_refs = Column(JSON, default=list)

    # Detailed findings & rationale
    criterion_findings = Column(JSON, default=list)
    rationale = Column(String, nullable=True)
    uncertainty_notes = Column(JSON, default=list)

    # Metadata & provenance
    evaluated_by = Column(String, nullable=True)
    provenance = Column(JSON, default=dict)
    record_hash = Column(String, nullable=True, index=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert evaluation record instance to dictionary representation."""
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "prediction_id": self.prediction_id,
            "status": self.status.value if isinstance(self.status, EvaluationStatus) else str(self.status),
            "criteria_id": self.criteria_id,
            "criteria_version": self.criteria_version,
            "evaluated_at": self.evaluated_at.isoformat() if hasattr(self.evaluated_at, "isoformat") and self.evaluated_at else None,
            "as_of": self.as_of.isoformat() if hasattr(self.as_of, "isoformat") and self.as_of else None,
            "observation_refs": self.observation_refs if self.observation_refs is not None else [],
            "excluded_observation_refs": self.excluded_observation_refs if self.excluded_observation_refs is not None else [],
            "criterion_findings": self.criterion_findings if self.criterion_findings is not None else [],
            "rationale": self.rationale,
            "uncertainty_notes": self.uncertainty_notes if self.uncertainty_notes is not None else [],
            "evaluated_by": self.evaluated_by,
            "provenance": self.provenance if self.provenance is not None else {},
            "record_hash": self.record_hash,
        }
