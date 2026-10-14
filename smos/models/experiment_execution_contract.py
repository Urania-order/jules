"""Controlled Experiment Execution Contract (TASK L-04).

Contract-as-code module without persistence layer (no SQLAlchemy model, no DB table).

This module defines strict schemas, validation, normalization, canonical serialization,
and hashing for experiment execution requests, parameter matching against ToolBlueprint,
and execution results.

CRITICAL INVARIANTS:
1. Specification and execution only; no epistemic promotion or hypothesis evaluation.
2. No forbidden keys: 'epistemic_status', 'evidence', 'actual_outcome'.
3. Pure functions: no mutation of input dictionaries.
"""

import copy
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

FORBIDDEN_RESERVED_KEYS = {"epistemic_status", "evidence", "actual_outcome"}

EXECUTION_STATUS_SUCCEEDED = "SUCCEEDED"
EXECUTION_STATUS_FAILED = "FAILED"
ALLOWED_EXECUTION_STATUSES = {EXECUTION_STATUS_SUCCEEDED, EXECUTION_STATUS_FAILED}

ALLOWED_REQUEST_KEYS = {
    "experiment_run_id",
    "parameters",
    "executed_by",
    "execution_conditions",
    "idempotency_key",
}

ALLOWED_RESULT_KEYS = {
    "experiment_run_id",
    "executor_id",
    "status",
    "started_at",
    "finished_at",
    "structured_output",
    "measurements",
    "observation_refs",
    "partial_persistence",
    "error_message",
    "error_details",
    "provenance",
}


def validate_execution_request(request: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an execution request dictionary against contract rules."""
    errors: List[str] = []

    if not isinstance(request, dict):
        return False, ["Execution request must be a dictionary"]

    for k in request.keys():
        if k in FORBIDDEN_RESERVED_KEYS:
            errors.append(f"Forbidden key '{k}' found in execution request")
        elif k not in ALLOWED_REQUEST_KEYS:
            errors.append(f"Unknown key '{k}' in execution request")

    if "experiment_run_id" not in request or request["experiment_run_id"] is None:
        errors.append("Missing required field 'experiment_run_id'")
    else:
        run_id = request["experiment_run_id"]
        if isinstance(run_id, bool) or not isinstance(run_id, (int, str)):
            errors.append("experiment_run_id must be an integer or string")

    if "parameters" in request and request["parameters"] is not None:
        if not isinstance(request["parameters"], dict):
            errors.append("parameters must be a dictionary")

    if "execution_conditions" in request and request["execution_conditions"] is not None:
        if not isinstance(request["execution_conditions"], dict):
            errors.append("execution_conditions must be a dictionary")

    if "executed_by" in request and request["executed_by"] is not None:
        if not isinstance(request["executed_by"], str):
            errors.append("executed_by must be a string")

    if "idempotency_key" in request and request["idempotency_key"] is not None:
        if not isinstance(request["idempotency_key"], str):
            errors.append("idempotency_key must be a string")

    return len(errors) == 0, errors


def validate_parameters_against_blueprint(
    parameters: Dict[str, Any],
    blueprint: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validate actual execution parameters against a ToolBlueprint specification.

    Checks:
      - Required parameters are supplied.
      - Types match (int, float, string, bool, enum).
      - Min/max bounds for int/float.
      - Allowed values for enum.
      - No unknown parameter keys (if parameter spec is defined).
    """
    errors: List[str] = []
    if not isinstance(parameters, dict):
        return False, ["Parameters must be a dictionary"]

    if not isinstance(blueprint, dict):
        return False, ["Blueprint must be a dictionary"]

    spec = blueprint.get("specification", {})
    if not isinstance(spec, dict):
        return False, ["Blueprint missing valid specification dictionary"]

    param_specs = spec.get("parameters", [])
    if not isinstance(param_specs, list):
        return False, ["Blueprint specification.parameters must be a list"]

    spec_map = {p.get("name"): p for p in param_specs if isinstance(p, dict) and p.get("name")}

    # Check for unknown parameters
    for p_name in parameters.keys():
        if p_name not in spec_map:
            errors.append(f"Parameter '{p_name}' is not defined in blueprint specification")

    # Check each parameter spec
    for p_name, p_spec in spec_map.items():
        is_required = p_spec.get("required", False)
        ptype = p_spec.get("type")
        p_min = p_spec.get("min")
        p_max = p_spec.get("max")
        p_default = p_spec.get("default")
        p_allowed = p_spec.get("allowed_values")

        if p_name not in parameters:
            if is_required and p_default is None:
                errors.append(f"Missing required parameter '{p_name}'")
            continue

        val = parameters[p_name]

        if val is None:
            if is_required:
                errors.append(f"Required parameter '{p_name}' cannot be None")
            continue

        if ptype == "int":
            if isinstance(val, bool) or not isinstance(val, int):
                errors.append(f"Parameter '{p_name}' must be an int, got {val!r}")
            else:
                if p_min is not None and val < p_min:
                    errors.append(f"Parameter '{p_name}' value {val} is below minimum {p_min}")
                if p_max is not None and val > p_max:
                    errors.append(f"Parameter '{p_name}' value {val} is above maximum {p_max}")

        elif ptype == "float":
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                errors.append(f"Parameter '{p_name}' must be a float or int, got {val!r}")
            else:
                if p_min is not None and val < p_min:
                    errors.append(f"Parameter '{p_name}' value {val} is below minimum {p_min}")
                if p_max is not None and val > p_max:
                    errors.append(f"Parameter '{p_name}' value {val} is above maximum {p_max}")

        elif ptype == "string":
            if not isinstance(val, str):
                errors.append(f"Parameter '{p_name}' must be a string, got {val!r}")

        elif ptype == "bool":
            if not isinstance(val, bool):
                errors.append(f"Parameter '{p_name}' must be a bool, got {val!r}")

        elif ptype == "enum":
            if p_allowed and val not in p_allowed:
                errors.append(f"Parameter '{p_name}' value {val!r} is not in allowed_values {p_allowed!r}")

    return len(errors) == 0, errors


def validate_execution_result(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate an execution result dictionary against contract rules."""
    errors: List[str] = []

    if not isinstance(result, dict):
        return False, ["Execution result must be a dictionary"]

    for k in result.keys():
        if k in FORBIDDEN_RESERVED_KEYS:
            errors.append(f"Forbidden epistemic key '{k}' found in execution result")
        elif k not in ALLOWED_RESULT_KEYS:
            errors.append(f"Unknown key '{k}' in execution result")

    if "experiment_run_id" not in result or result["experiment_run_id"] is None:
        errors.append("Missing required field 'experiment_run_id'")
    else:
        run_id = result["experiment_run_id"]
        if isinstance(run_id, bool) or not isinstance(run_id, (int, str)):
            errors.append("experiment_run_id must be an integer or string")

    if "executor_id" not in result or not isinstance(result.get("executor_id"), str) or not result["executor_id"].strip():
        errors.append("executor_id must be a non-empty string")

    status = result.get("status")
    if status not in ALLOWED_EXECUTION_STATUSES:
        errors.append(f"status must be one of {sorted(ALLOWED_EXECUTION_STATUSES)}")

    for dt_field in ("started_at", "finished_at"):
        val = result.get(dt_field)
        if val is not None:
            if isinstance(val, str):
                try:
                    datetime.fromisoformat(val)
                except ValueError:
                    errors.append(f"{dt_field} must be a valid ISO8601 string or datetime")
            elif not isinstance(val, datetime):
                errors.append(f"{dt_field} must be a valid ISO8601 string or datetime")

    if "measurements" in result and result["measurements"] is not None:
        if not isinstance(result["measurements"], list):
            errors.append("measurements must be a list of measurement dictionaries")
        else:
            for idx, meas in enumerate(result["measurements"]):
                if not isinstance(meas, dict):
                    errors.append(f"measurements[{idx}] must be a dict")
                else:
                    if "metric_name" not in meas or not isinstance(meas.get("metric_name"), str) or not meas["metric_name"].strip():
                        errors.append(f"measurements[{idx}].metric_name must be a non-empty string")
                    if "metric_value" not in meas or meas.get("metric_value") is None:
                        errors.append(f"measurements[{idx}].metric_value is required")

    if "observation_refs" in result and result["observation_refs"] is not None:
        refs = result["observation_refs"]
        if not isinstance(refs, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in refs):
            errors.append("observation_refs must be a list of integers")

    if "partial_persistence" in result and result["partial_persistence"] is not None:
        if not isinstance(result["partial_persistence"], bool):
            errors.append("partial_persistence must be a boolean")

    return len(errors) == 0, errors


def normalize_execution_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized copy of an execution result dictionary."""
    normalized = copy.deepcopy(result)

    normalized.setdefault("status", EXECUTION_STATUS_FAILED)
    normalized.setdefault("measurements", [])
    normalized.setdefault("observation_refs", [])
    normalized.setdefault("partial_persistence", False)
    normalized.setdefault("provenance", {})
    normalized.setdefault("error_message", None)
    normalized.setdefault("error_details", None)
    normalized.setdefault("structured_output", {})

    for dt_field in ("started_at", "finished_at"):
        if isinstance(normalized.get(dt_field), datetime):
            normalized[dt_field] = normalized[dt_field].isoformat()

    return normalized


def canonical_serialize_execution_result(result: Dict[str, Any]) -> str:
    """Return canonical deterministic JSON serialization for an execution result."""
    norm = normalize_execution_result(result)
    payload = {
        "experiment_run_id": str(norm.get("experiment_run_id", "")),
        "executor_id": norm.get("executor_id", ""),
        "status": norm.get("status", ""),
        "started_at": str(norm.get("started_at", "")),
        "finished_at": str(norm.get("finished_at", "")),
        "structured_output": norm.get("structured_output", {}),
        "measurements": norm.get("measurements", []),
        "observation_refs": sorted(norm.get("observation_refs", [])),
        "partial_persistence": norm.get("partial_persistence", False),
        "error_message": norm.get("error_message"),
        "provenance": norm.get("provenance", {}),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def calculate_execution_result_hash(result: Dict[str, Any]) -> str:
    """Calculate SHA-256 hash of canonical execution result representation."""
    serialized = canonical_serialize_execution_result(result)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
