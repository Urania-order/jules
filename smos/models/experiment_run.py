"""ExperimentRun model for experiment lifecycle tracking (TASK L-03).

INVARIANTS:
1. Explicit state transitions: NO auto-execute, NO auto-complete, NO auto-evaluate.
2. Append-only status_history: Every state transition is recorded in status_history.
3. No update/delete methods on history or run: Lifecycle state moves strictly forward via explicit operations.
4. No auto-evaluation / auto-promotion: COMPLETED != evaluated. Observations != facts.
"""

import enum
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, func

from smos.core.database import Base


class ExperimentRunStatus(str, enum.Enum):
    """Experiment run status enum."""

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ExperimentRun(Base):
    """Lifecycle tracker for a single experiment run.

    Links:
        - tool_blueprint_id (String reference, no FK)
        - observation_refs (JSON list of observation IDs, no FK)
        - recipe_execution_id (Optional FK to recipe_executions.id)
    """

    __tablename__ = "experiment_runs"

    id = Column(Integer, primary_key=True, index=True)

    # LINK TO BLUEPRINT (String reference, no FK)
    tool_blueprint_id = Column(String, nullable=False, index=True)
    blueprint_version = Column(String, nullable=True)

    # LINK TO OBSERVATIONS (JSON references, no FK)
    observation_refs = Column(JSON, default=list)  # List[int]

    # LINK TO RECIPE EXECUTION (optional FK, canonical entity)
    recipe_execution_id = Column(
        Integer,
        ForeignKey("recipe_executions.id"),
        nullable=True,
    )

    # LIFECYCLE
    status = Column(String, default="PROPOSED", nullable=False)
    status_history = Column(JSON, default=list)
    # [{status, at, by, reason}]

    # TIMESTAMPS
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    proposed_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # PROVENANCE
    created_by = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)

    # CONTEXT
    actual_parameters = Column(JSON, default=dict)
    execution_conditions = Column(JSON, default=dict)

    # PROVENANCE (metadata)
    provenance = Column(JSON, default=dict)

    def to_dict(self) -> dict:
        """Convert ExperimentRun instance to dictionary representation."""
        return {
            "id": self.id,
            "tool_blueprint_id": self.tool_blueprint_id,
            "blueprint_version": self.blueprint_version,
            "observation_refs": self.observation_refs if self.observation_refs is not None else [],
            "recipe_execution_id": self.recipe_execution_id,
            "status": self.status,
            "status_history": self.status_history if self.status_history is not None else [],
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at) if self.created_at else None,
            "proposed_at": self.proposed_at.isoformat() if hasattr(self.proposed_at, "isoformat") else str(self.proposed_at) if self.proposed_at else None,
            "approved_at": self.approved_at.isoformat() if hasattr(self.approved_at, "isoformat") else str(self.approved_at) if self.approved_at else None,
            "executed_at": self.executed_at.isoformat() if hasattr(self.executed_at, "isoformat") else str(self.executed_at) if self.executed_at else None,
            "completed_at": self.completed_at.isoformat() if hasattr(self.completed_at, "isoformat") else str(self.completed_at) if self.completed_at else None,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "actual_parameters": self.actual_parameters if self.actual_parameters is not None else {},
            "execution_conditions": self.execution_conditions if self.execution_conditions is not None else {},
            "provenance": self.provenance if self.provenance is not None else {},
        }
