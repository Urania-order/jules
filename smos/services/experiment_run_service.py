"""ExperimentRun Service for experiment lifecycle management (TASK L-03).

Provides explicit state transitions for experiment runs:
  propose -> approve -> execute -> complete / fail / cancel

CRITICAL INVARIANTS:
1. NO auto-execute, NO auto-complete, NO auto-evaluate.
2. Append-only status_history: every transition adds an entry {status, at, by, reason}.
3. NO update or delete methods exist on ExperimentRun or status_history.
4. COMPLETED status does NOT evaluate observations or auto-promote facts.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from smos.models.experiment_run import ExperimentRun, ExperimentRunStatus
from smos.models.experiment_run_contract import (
    validate_experiment_run,
    validate_transition,
)


class ExperimentRunService:
    """Service layer managing ExperimentRun lifecycle in an explicit, append-only manner."""

    def __init__(self, db: Session):
        self.db = db

    def propose(
        self,
        data: Dict[str, Any],
        created_by: Optional[str] = None,
    ) -> Optional[ExperimentRun]:
        """Create a PROPOSED experiment run.

        Initializes status to PROPOSED and status_history with the proposal entry.
        """
        payload = dict(data)
        payload["status"] = ExperimentRunStatus.PROPOSED.value

        is_valid, errors = validate_experiment_run(payload)
        if not is_valid:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        creator = created_by or payload.get("created_by")

        initial_history_entry = {
            "status": ExperimentRunStatus.PROPOSED.value,
            "at": now_iso,
            "by": creator,
            "reason": payload.get("proposal_reason") or "Initial proposal",
        }

        history = list(payload.get("status_history") or [])
        history.append(initial_history_entry)

        run = ExperimentRun(
            tool_blueprint_id=payload["tool_blueprint_id"],
            blueprint_version=payload.get("blueprint_version"),
            observation_refs=list(payload.get("observation_refs") or []),
            recipe_execution_id=payload.get("recipe_execution_id"),
            status=ExperimentRunStatus.PROPOSED.value,
            status_history=history,
            proposed_at=now,
            created_by=creator,
            actual_parameters=dict(payload.get("actual_parameters") or {}),
            execution_conditions=dict(payload.get("execution_conditions") or {}),
            provenance=dict(payload.get("provenance") or {}),
        )

        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def approve(
        self,
        run_id: int,
        approved_by: str,
        reason: Optional[str] = None,
    ) -> Optional[ExperimentRun]:
        """PROPOSED -> APPROVED.

        Appends status history entry and records approved_at timestamp.
        Does NOT execute the experiment automatically.
        """
        run = self.get(run_id)
        if not run:
            return None

        is_valid, _ = validate_transition(run, ExperimentRunStatus.APPROVED.value)
        if not is_valid:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        history = list(run.status_history or [])
        history.append({
            "status": ExperimentRunStatus.APPROVED.value,
            "at": now_iso,
            "by": approved_by,
            "reason": reason or "Run approved",
        })

        run.status = ExperimentRunStatus.APPROVED.value
        run.status_history = history
        run.approved_by = approved_by
        run.approved_at = now

        self.db.commit()
        self.db.refresh(run)
        return run

    def execute(
        self,
        run_id: int,
        actual_parameters: Optional[Dict[str, Any]] = None,
        execution_conditions: Optional[Dict[str, Any]] = None,
        executed_by: Optional[str] = None,
    ) -> Optional[ExperimentRun]:
        """APPROVED -> EXECUTED.

        Records execution parameters/conditions and executed_at timestamp.
        Does NOT run the experiment engine or execute code automatically.
        """
        run = self.get(run_id)
        if not run:
            return None

        is_valid, _ = validate_transition(run, ExperimentRunStatus.EXECUTED.value)
        if not is_valid:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        history = list(run.status_history or [])
        history.append({
            "status": ExperimentRunStatus.EXECUTED.value,
            "at": now_iso,
            "by": executed_by,
            "reason": "Execution started",
        })

        if actual_parameters is not None:
            params = dict(run.actual_parameters or {})
            params.update(actual_parameters)
            run.actual_parameters = params

        if execution_conditions is not None:
            conds = dict(run.execution_conditions or {})
            conds.update(execution_conditions)
            run.execution_conditions = conds

        run.status = ExperimentRunStatus.EXECUTED.value
        run.status_history = history
        run.executed_at = now

        self.db.commit()
        self.db.refresh(run)
        return run

    def complete(
        self,
        run_id: int,
        observation_refs: Optional[List[int]] = None,
        completed_by: Optional[str] = None,
    ) -> Optional[ExperimentRun]:
        """EXECUTED -> COMPLETED.

        Links observation_refs and records completed_at timestamp.
        Does NOT evaluate observations or promote hypotheses automatically.
        """
        run = self.get(run_id)
        if not run:
            return None

        is_valid, _ = validate_transition(run, ExperimentRunStatus.COMPLETED.value)
        if not is_valid:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        history = list(run.status_history or [])
        history.append({
            "status": ExperimentRunStatus.COMPLETED.value,
            "at": now_iso,
            "by": completed_by,
            "reason": "Execution completed",
        })

        if observation_refs is not None:
            existing_refs = set(run.observation_refs or [])
            existing_refs.update(observation_refs)
            run.observation_refs = sorted(list(existing_refs))

        run.status = ExperimentRunStatus.COMPLETED.value
        run.status_history = history
        run.completed_at = now

        self.db.commit()
        self.db.refresh(run)
        return run

    def fail(
        self,
        run_id: int,
        reason: str,
        failed_by: Optional[str] = None,
    ) -> Optional[ExperimentRun]:
        """EXECUTED -> FAILED."""
        run = self.get(run_id)
        if not run:
            return None

        is_valid, _ = validate_transition(run, ExperimentRunStatus.FAILED.value)
        if not is_valid:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        history = list(run.status_history or [])
        history.append({
            "status": ExperimentRunStatus.FAILED.value,
            "at": now_iso,
            "by": failed_by,
            "reason": reason,
        })

        run.status = ExperimentRunStatus.FAILED.value
        run.status_history = history

        self.db.commit()
        self.db.refresh(run)
        return run

    def cancel(
        self,
        run_id: int,
        reason: str,
        cancelled_by: Optional[str] = None,
    ) -> Optional[ExperimentRun]:
        """PROPOSED|APPROVED -> CANCELLED."""
        run = self.get(run_id)
        if not run:
            return None

        is_valid, _ = validate_transition(run, ExperimentRunStatus.CANCELLED.value)
        if not is_valid:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        history = list(run.status_history or [])
        history.append({
            "status": ExperimentRunStatus.CANCELLED.value,
            "at": now_iso,
            "by": cancelled_by,
            "reason": reason,
        })

        run.status = ExperimentRunStatus.CANCELLED.value
        run.status_history = history

        self.db.commit()
        self.db.refresh(run)
        return run

    # QUERY
    def get(self, run_id: int) -> Optional[ExperimentRun]:
        """Retrieve ExperimentRun by ID."""
        return self.db.query(ExperimentRun).filter(ExperimentRun.id == run_id).first()

    def list_by_status(self, status: str, limit: int = 100) -> List[ExperimentRun]:
        """List experiment runs matching a specific status."""
        return (
            self.db.query(ExperimentRun)
            .filter(ExperimentRun.status == status)
            .order_by(ExperimentRun.id.asc())
            .limit(limit)
            .all()
        )

    def list_by_blueprint(self, tool_blueprint_id: str, limit: int = 100) -> List[ExperimentRun]:
        """List experiment runs referencing a specific tool blueprint ID."""
        return (
            self.db.query(ExperimentRun)
            .filter(ExperimentRun.tool_blueprint_id == tool_blueprint_id)
            .order_by(ExperimentRun.id.asc())
            .limit(limit)
            .all()
        )
