"""Evaluation Contract (TASK L-05A).

Defines validation, normalization, canonical serialization, SHA-256 hashing, and forbidden key checks
for evaluation requests and results.

CRITICAL INVARIANTS:
1. No epistemic mutation instructions or forbidden fields in evaluation results.
2. Canonical deterministic JSON serialization and hashing.
3. Explicit validation rejecting unknown target types or forbidden keys.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from smos.models.evaluation import EvaluationStatus

SUPPORTED_TARGET_TYPES = ["prediction", "phenomenon", "potential_phenomenon"]

FORBIDDEN_EVALUATION_KEYS = [
    "epistemic_status_mutation",
    "promote_to_fact",
    "demote_status",
    "auto_execute",
    "mutate_target",
]


def validate_evaluation_request(request: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an evaluation request dictionary against contract rules."""
    errors: List[str] = []

    if not isinstance(request, dict):
        return False, ["Evaluation request must be a dictionary"]

    # Check forbidden keys
    for k in FORBIDDEN_EVALUATION_KEYS:
        if k in request:
            errors.append(f"Forbidden key '{k}' in evaluation request")

    # Target type
    target_type = request.get("target_type")
    if not isinstance(target_type, str) or not target_type.strip():
        errors.append("Field 'target_type' must be a non-empty string")
    elif target_type.strip().lower() not in SUPPORTED_TARGET_TYPES:
        errors.append(f"Target type '{target_type}' is not supported. Must be one of {SUPPORTED_TARGET_TYPES}")

    # Target ID
    target_id = request.get("target_id")
    if target_id is None:
        errors.append("Field 'target_id' is required")
    elif not isinstance(target_id, int) or target_id <= 0:
        errors.append(f"Field 'target_id' must be a positive integer, got {target_id!r}")

    # Prediction ID (optional)
    prediction_id = request.get("prediction_id")
    if prediction_id is not None:
        if not isinstance(prediction_id, int) or prediction_id <= 0:
            errors.append(f"Field 'prediction_id' must be a positive integer if provided, got {prediction_id!r}")

    # Criteria specification / reference
    criteria = request.get("criteria")
    if criteria is not None and not isinstance(criteria, (dict, str)):
        errors.append("Field 'criteria' must be a dictionary or string criteria ID if provided")

    # Cutoff as_of (optional)
    as_of = request.get("as_of")
    if as_of is not None:
        if isinstance(as_of, str):
            try:
                datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"Field 'as_of' string must be ISO-formatted, got {as_of!r}")
        elif not isinstance(as_of, datetime):
            errors.append(f"Field 'as_of' must be an ISO string or datetime object, got type {type(as_of).__name__}")

    return len(errors) == 0, errors


def validate_evaluation_result(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an evaluation result dictionary against contract rules."""
    errors: List[str] = []

    if not isinstance(result, dict):
        return False, ["Evaluation result must be a dictionary"]

    # Check forbidden keys
    for k in FORBIDDEN_EVALUATION_KEYS:
        if k in result:
            errors.append(f"Forbidden key '{k}' in evaluation result")

    # Status validation
    status = result.get("status")
    valid_statuses = [s.value for s in EvaluationStatus]
    if status not in valid_statuses:
        errors.append(f"Invalid evaluation status '{status}'. Must be one of {valid_statuses}")

    # Target type & target ID
    target_type = result.get("target_type")
    if not isinstance(target_type, str) or not target_type.strip():
        errors.append("Field 'target_type' must be a non-empty string in result")

    target_id = result.get("target_id")
    if target_id is None or not isinstance(target_id, int) or target_id <= 0:
        errors.append("Field 'target_id' must be a positive integer in result")

    # Lists validation
    for field_name in ["observation_refs", "excluded_observation_refs", "criterion_findings", "uncertainty_notes"]:
        val = result.get(field_name)
        if val is not None and not isinstance(val, list):
            errors.append(f"Field '{field_name}' must be a list in result")

    return len(errors) == 0, errors


def normalize_evaluation_result(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize evaluation result dictionary into canonical representation."""
    if not isinstance(raw_result, dict):
        raw_result = {}

    status_raw = raw_result.get("status")
    if isinstance(status_raw, EvaluationStatus):
        status_str = status_raw.value
    elif isinstance(status_raw, str) and status_raw in [s.value for s in EvaluationStatus]:
        status_str = status_raw
    else:
        status_str = EvaluationStatus.UNDETERMINED.value

    target_type = str(raw_result.get("target_type") or "unknown").strip().lower()
    target_id = raw_result.get("target_id") if isinstance(raw_result.get("target_id"), int) else 0
    prediction_id = raw_result.get("prediction_id") if isinstance(raw_result.get("prediction_id"), int) else None

    evaluated_at = raw_result.get("evaluated_at")
    if isinstance(evaluated_at, datetime):
        evaluated_at_str = evaluated_at.isoformat()
    elif isinstance(evaluated_at, str):
        evaluated_at_str = evaluated_at
    else:
        evaluated_at_str = datetime.now(timezone.utc).isoformat()

    as_of = raw_result.get("as_of")
    if isinstance(as_of, datetime):
        as_of_str = as_of.isoformat()
    elif isinstance(as_of, str):
        as_of_str = as_of
    else:
        as_of_str = None

    normalized = {
        "id": raw_result.get("id"),
        "target_type": target_type,
        "target_id": target_id,
        "prediction_id": prediction_id,
        "status": status_str,
        "criteria_id": str(raw_result.get("criteria_id") or "DEFAULT_CRITERIA"),
        "criteria_version": str(raw_result.get("criteria_version") or "1.0.0"),
        "evaluated_at": evaluated_at_str,
        "as_of": as_of_str,
        "observation_refs": list(raw_result.get("observation_refs") or []),
        "excluded_observation_refs": list(raw_result.get("excluded_observation_refs") or []),
        "criterion_findings": list(raw_result.get("criterion_findings") or []),
        "rationale": str(raw_result.get("rationale") or "") if raw_result.get("rationale") is not None else None,
        "uncertainty_notes": list(raw_result.get("uncertainty_notes") or []),
        "evaluated_by": str(raw_result.get("evaluated_by")) if raw_result.get("evaluated_by") is not None else None,
        "provenance": dict(raw_result.get("provenance") or {}),
        "record_hash": None,
    }

    # Hash canonical payload
    normalized["record_hash"] = compute_evaluation_hash(normalized)
    return normalized


def canonical_evaluation_json(result: Dict[str, Any]) -> str:
    """Generate deterministic JSON string for evaluation result, omitting volatile IDs/hashes."""
    payload = {
        "target_type": result.get("target_type"),
        "target_id": result.get("target_id"),
        "prediction_id": result.get("prediction_id"),
        "status": result.get("status"),
        "criteria_id": result.get("criteria_id"),
        "criteria_version": result.get("criteria_version"),
        "as_of": result.get("as_of"),
        "observation_refs": sorted(list(result.get("observation_refs") or [])),
        "excluded_observation_refs": sorted(list(result.get("excluded_observation_refs") or [])),
        "criterion_findings": result.get("criterion_findings") or [],
        "rationale": result.get("rationale"),
        "uncertainty_notes": result.get("uncertainty_notes") or [],
        "evaluated_by": result.get("evaluated_by"),
        "provenance": result.get("provenance") or {},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_evaluation_hash(result: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of canonical evaluation JSON representation."""
    canonical = canonical_evaluation_json(result)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
