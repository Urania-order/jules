"""Observation model for Epistemic Isolation Proxy (EIP).

INVARIANTS:
1. Append-only: Observations are never updated or deleted.
2. Provenance != Evidence: Provenance describes source/method/path, not truth.
3. Epistemic classification != interpretation of truth: Default is UNVALIDATED_OBSERVATION.
4. Experiment run reference is future-safe (nullable String, no FK).
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, func

from smos.core.database import Base


class Observation(Base):
    """Raw experimental observation.

    Note: Provenance metadata describes source/method/path and does NOT confirm truth of measurement.
    """

    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)

    # WHAT
    metric_name = Column(String, nullable=False, index=True)
    metric_value = Column(JSON, nullable=False)
    metric_unit = Column(String, nullable=True)

    # WHERE FROM (provenance, NOT evidence)
    tool_blueprint_id = Column(String, nullable=True, index=True)
    tool_id = Column(String, nullable=True)
    experiment_run_id = Column(String, nullable=True, index=True)
    execution_id = Column(
        Integer,
        ForeignKey("recipe_executions.id"),
        nullable=True,
    )

    # CONTEXT (references only, NOT evidence)
    hypothesis_refs = Column(JSON, default=list)  # List[int]
    prediction_refs = Column(JSON, default=list)  # List[int]
    assumption_refs = Column(JSON, default=list)  # List[str]
    phenomenon_refs = Column(JSON, default=list)  # List[int]

    # EXECUTION CONDITIONS
    execution_conditions = Column(JSON, default=dict)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # EPISTEMIC CLASSIFICATION (metadata only)
    epistemic_classification = Column(
        String,
        default="UNVALIDATED_OBSERVATION",
    )

    # PROVENANCE (metadata, NOT evidence)
    provenance = Column(JSON, default=dict)

    # DEDUPLICATION
    payload_hash = Column(String, nullable=True, index=True)

    # CORRECTION CHAIN
    supersedes_observation_id = Column(
        Integer,
        ForeignKey("observations.id"),
        nullable=True,
    )
    correction_reason = Column(String, nullable=True)

    def to_dict(self):
        """Convert observation instance to dictionary representation."""
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "tool_blueprint_id": self.tool_blueprint_id,
            "tool_id": self.tool_id,
            "experiment_run_id": self.experiment_run_id,
            "execution_id": self.execution_id,
            "hypothesis_refs": self.hypothesis_refs if self.hypothesis_refs is not None else [],
            "prediction_refs": self.prediction_refs if self.prediction_refs is not None else [],
            "assumption_refs": self.assumption_refs if self.assumption_refs is not None else [],
            "phenomenon_refs": self.phenomenon_refs if self.phenomenon_refs is not None else [],
            "execution_conditions": self.execution_conditions if self.execution_conditions is not None else {},
            "observed_at": self.observed_at.isoformat() if hasattr(self.observed_at, "isoformat") else str(self.observed_at) if self.observed_at else None,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at) if self.created_at else None,
            "epistemic_classification": self.epistemic_classification,
            "provenance": self.provenance if self.provenance is not None else {},
            "payload_hash": self.payload_hash,
            "supersedes_observation_id": self.supersedes_observation_id,
            "correction_reason": self.correction_reason,
        }
