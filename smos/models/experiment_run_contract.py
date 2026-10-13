"""ExperimentRun Contract module (TASK L-03).

Provides validation, normalization, canonical serialization, hash computation,
and state transition validation for experiment runs.

CRITICAL INVARIANTS:
1. No epistemic_status, evidence, or actual_outcome fields allowed in ExperimentRun payload.
2. Pure functions: validation and serialization do NOT mutate input data structures.
3. Explicit state transitions following ALLOWED_TRANSITIONS.
"""

import copy
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

ALLOWED_EXPERIMENT_STATUSES = {
    "PROPOSED",
    "APPROVED",
    "EXECUTED",
    "COMPLETED",
    "CANCELLED",
    "FAILED",
}

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "PROPOSED": {"APPROVED", "CANCELLED"},
    "APPROVED": {"EXECUTED", "CANCELLED"},
    "EXECUTED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
    "FAILED": set(),
}

FORBIDDEN_EXPERIMENT_RUN_KEYS = {
    "epistemic_status",
    "evidence",
    "actual_outcome",
    "fact_status",
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Pure function checking whether a transition from from_status to to_status is valid."""
    if from_status not in ALLOWED_TRANSITIONS:
        return False
    return to_status in ALLOWED_TRANSITIONS[from_status]


def validate_transition(run_or_status: Any, to_status: str) -> Tuple[bool, List[str]]:
    """Validate a status transition for a run instance or status string."""
    errors: List[str] = []
    if isinstance(run_or_status, str):
        from_status = run_or_status
    elif isinstance(run_or_status, dict):
        from_status = run_or_status.get("status", "")
    elif hasattr(run_or_status, "status"):
        from_status = getattr(run_or_status, "status", "")
    else:
        return False, ["Invalid run input for transition validation"]

    if from_status not in ALLOWED_EXPERIMENT_STATUSES:
        errors.append(f"Invalid starting status '{from_status}'")
    if to_status not in ALLOWED_EXPERIMENT_STATUSES:
        errors.append(f"Invalid target status '{to_status}'")

    if errors:
        return False, errors

    if not is_valid_transition(from_status, to_status):
        errors.append(f"Transition from '{from_status}' to '{to_status}' is not allowed")
        return False, errors

    return True, []


def validate_experiment_run(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate experiment run dictionary against contract rules.

    Does NOT mutate input data.
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return False, ["Input data must be a dictionary"]

    # Check forbidden keys
    for key in FORBIDDEN_EXPERIMENT_RUN_KEYS:
        if key in data:
            errors.append(f"Forbidden field '{key}' is not allowed in ExperimentRun")

    # tool_blueprint_id: required non-empty string
    tool_blueprint_id = data.get("tool_blueprint_id")
    if not isinstance(tool_blueprint_id, str) or not tool_blueprint_id.strip():
        errors.append("tool_blueprint_id must be a non-empty string")

    # status: required, must be allowed
    status = data.get("status")
    if status is None:
        errors.append("status is required")
    elif status not in ALLOWED_EXPERIMENT_STATUSES:
        errors.append(f"status '{status}' must be one of {sorted(ALLOWED_EXPERIMENT_STATUSES)}")

    # status_history: list of dicts with {status, at, by, reason}
    if "status_history" in data and data["status_history"] is not None:
        sh = data["status_history"]
        if not isinstance(sh, list):
            errors.append("status_history must be a list")
        else:
            for idx, entry in enumerate(sh):
                if not isinstance(entry, dict):
                    errors.append(f"status_history[{idx}] must be a dict")
                else:
                    if "status" not in entry or entry["status"] not in ALLOWED_EXPERIMENT_STATUSES:
                        errors.append(f"status_history[{idx}].status must be a valid status")

    # observation_refs: List[int]
    if "observation_refs" in data and data["observation_refs"] is not None:
        refs = data["observation_refs"]
        if not isinstance(refs, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in refs):
            errors.append("observation_refs must be a list of integers")

    # actual_parameters: dict
    if "actual_parameters" in data and data["actual_parameters"] is not None:
        if not isinstance(data["actual_parameters"], dict):
            errors.append("actual_parameters must be a dictionary")

    # execution_conditions: dict
    if "execution_conditions" in data and data["execution_conditions"] is not None:
        if not isinstance(data["execution_conditions"], dict):
            errors.append("execution_conditions must be a dictionary")

    # recipe_execution_id: optional int
    if "recipe_execution_id" in data and data["recipe_execution_id"] is not None:
        if isinstance(data["recipe_execution_id"], bool) or not isinstance(data["recipe_execution_id"], int):
            errors.append("recipe_execution_id must be an integer or None")

    return len(errors) == 0, errors


def normalize_experiment_run(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize experiment run dictionary according to contract rules.

    Does NOT mutate input data.
    """
    normalized = copy.deepcopy(data) if isinstance(data, dict) else {}

    normalized.setdefault("tool_blueprint_id", "")
    normalized.setdefault("blueprint_version", None)

    if normalized.get("observation_refs") is None:
        normalized["observation_refs"] = []

    normalized.setdefault("recipe_execution_id", None)

    if not normalized.get("status"):
        normalized["status"] = "PROPOSED"

    if normalized.get("status_history") is None:
        normalized["status_history"] = []

    if normalized.get("actual_parameters") is None:
        normalized["actual_parameters"] = {}

    if normalized.get("execution_conditions") is None:
        normalized["execution_conditions"] = {}

    if normalized.get("provenance") is None:
        normalized["provenance"] = {}

    return normalized


def canonical_serialize_experiment_run(data: Dict[str, Any]) -> str:
    """Produce deterministic canonical JSON string for an experiment run.

    Does NOT mutate input data. Sorts keys and ensures stable formatting.
    """
    normalized = normalize_experiment_run(data)

    canonical_payload = {
        "tool_blueprint_id": str(normalized.get("tool_blueprint_id", "")),
        "blueprint_version": normalized.get("blueprint_version"),
        "observation_refs": sorted(normalized.get("observation_refs", [])),
        "recipe_execution_id": normalized.get("recipe_execution_id"),
        "status": str(normalized.get("status", "PROPOSED")),
        "status_history": normalized.get("status_history", []),
        "created_by": normalized.get("created_by"),
        "approved_by": normalized.get("approved_by"),
        "actual_parameters": normalized.get("actual_parameters", {}),
        "execution_conditions": normalized.get("execution_conditions", {}),
        "provenance": normalized.get("provenance", {}),
    }

    return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))


def calculate_experiment_run_hash(data: Dict[str, Any]) -> str:
    """Calculate SHA256 payload hash from canonical experiment run string."""
    canonical_str = canonical_serialize_experiment_run(data)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
