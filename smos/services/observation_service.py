"""Observation Service for Epistemic Isolation Proxy (EIP).

Provides append-only observation ingestion, querying, deduplication, conflict classification,
and correction chains.

CRITICAL INVARIANTS:
1. Append-only: NO update() or delete() methods exist.
2. Provenance != Evidence: Provenance describes source/method/path, NOT truth.
3. Epistemic classification != interpretation of truth: Ingest defaults to UNVALIDATED_OBSERVATION.
   NO auto-promotion or auto-classification on ingest or conflict detection.
4. Original records preserved forever on corrections.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from smos.models.observation import Observation
from smos.models.observation_contract import (
    calculate_observation_hash,
    classify_conflict,
    normalize_observation,
    validate_observation,
)


class ObservationService:
    """Service layer managing raw experimental observations in an append-only manner."""

    def __init__(self, db: Session):
        self.db = db

    def ingest(self, data: Dict[str, Any]) -> Optional[Observation]:
        """Validate and store raw observation.

        Computes payload_hash. NO update or deletion.
        Defaults epistemic_classification to UNVALIDATED_OBSERVATION.
        Returns created Observation or None if validation fails.
        """
        is_valid, errors = validate_observation(data)
        if not is_valid:
            return None

        normalized = normalize_observation(data)
        payload_hash = calculate_observation_hash(normalized)

        observed_at = normalized["observed_at"]
        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at)

        obs = Observation(
            metric_name=normalized["metric_name"],
            metric_value=normalized["metric_value"],
            metric_unit=normalized.get("metric_unit"),
            tool_blueprint_id=normalized.get("tool_blueprint_id"),
            tool_id=normalized.get("tool_id"),
            experiment_run_id=normalized.get("experiment_run_id"),
            execution_id=normalized.get("execution_id"),
            hypothesis_refs=normalized.get("hypothesis_refs", []),
            prediction_refs=normalized.get("prediction_refs", []),
            assumption_refs=normalized.get("assumption_refs", []),
            phenomenon_refs=normalized.get("phenomenon_refs", []),
            execution_conditions=normalized.get("execution_conditions", {}),
            observed_at=observed_at,
            epistemic_classification=normalized.get(
                "epistemic_classification", "UNVALIDATED_OBSERVATION"
            ),
            provenance=normalized.get("provenance", {}),
            payload_hash=payload_hash,
            supersedes_observation_id=normalized.get("supersedes_observation_id"),
            correction_reason=normalized.get("correction_reason"),
        )

        self.db.add(obs)
        self.db.commit()
        self.db.refresh(obs)
        return obs

    def ingest_correction(
        self,
        original_id: int,
        corrected_data: Dict[str, Any],
        reason: str,
    ) -> Optional[Observation]:
        """Create a NEW observation correcting an existing observation.

        Original record remains unchanged.
        New record gets supersedes_observation_id=original_id and correction_reason=reason.
        """
        if not reason or not isinstance(reason, str) or not reason.strip():
            return None

        original = self.get(original_id)
        if not original:
            return None

        payload = dict(corrected_data)
        payload["supersedes_observation_id"] = original_id
        payload["correction_reason"] = reason
        payload["epistemic_classification"] = "OBSERVATION_CORRECTED"

        return self.ingest(payload)

    def get(self, observation_id: int) -> Optional[Observation]:
        """Retrieve observation by ID."""
        return self.db.query(Observation).filter(Observation.id == observation_id).first()

    def list_for_tool(self, tool_blueprint_id: str, limit: int = 100) -> List[Observation]:
        """List observations produced by a specific tool blueprint."""
        return (
            self.db.query(Observation)
            .filter(Observation.tool_blueprint_id == tool_blueprint_id)
            .order_by(Observation.id.asc())
            .limit(limit)
            .all()
        )

    def list_for_hypothesis(self, hypothesis_id: int, limit: int = 100) -> List[Observation]:
        """List observations referencing a specific hypothesis ID."""
        from sqlalchemy import String, cast
        return (
            self.db.query(Observation)
            .filter(cast(Observation.hypothesis_refs, String).like(f"%{hypothesis_id}%"))
            .order_by(Observation.id.asc())
            .limit(limit)
            .all()
        )

    def list_for_execution(self, execution_id: int, limit: int = 100) -> List[Observation]:
        """List observations linked to a specific recipe execution ID."""
        return (
            self.db.query(Observation)
            .filter(Observation.execution_id == execution_id)
            .order_by(Observation.id.asc())
            .limit(limit)
            .all()
        )

    def find_duplicates(self, payload_hash: str) -> List[Observation]:
        """Find observations matching a specific payload hash."""
        return (
            self.db.query(Observation)
            .filter(Observation.payload_hash == payload_hash)
            .order_by(Observation.id.asc())
            .all()
        )

    def list_conflicts_for_metric(
        self,
        metric_name: str,
    ) -> List[Tuple[Observation, Observation]]:
        """Return pairs of conflicting observations for a given metric_name.

        DOES NOT resolve conflicts.
        DOES NOT mark any observation as CONTRADICTION_SIGNAL automatically in the database.
        """
        obs_list = (
            self.db.query(Observation)
            .filter(Observation.metric_name == metric_name)
            .order_by(Observation.id.asc())
            .all()
        )

        conflicts: List[Tuple[Observation, Observation]] = []
        n = len(obs_list)
        for i in range(n):
            dict_i = obs_list[i].to_dict()
            for j in range(i + 1, n):
                dict_j = obs_list[j].to_dict()
                classification = classify_conflict(dict_i, dict_j)
                if classification in ("CONTRADICTION_SIGNAL", "POTENTIAL_DUPLICATE"):
                    conflicts.append((obs_list[i], obs_list[j]))

        return conflicts
