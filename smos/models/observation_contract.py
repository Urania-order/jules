"""Observation Contract module for Epistemic Isolation Proxy (EIP).

Provides strict, deterministic validation, normalization, canonical serialization,
hash computation, and conflict classification for raw experimental observations.

EPISTEMIC PRINCIPLES & INVARIANTS:
1. Provenance != Evidence: Provenance describes source, method, path, NOT truth.
2. Epistemic status != interpretation of truth: Default is UNVALIDATED_OBSERVATION.
   classify_conflict and normalize_observation MUST NOT alter epistemic_classification.
3. Pure functions: Functions must not mutate input data structures.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ALLOWED_EPISTEMIC_CLASSIFICATIONS = {
    "UNVALIDATED_OBSERVATION",
    "PARTIAL",
    "CONTRADICTION_SIGNAL",
    "OBSERVATION_CORRECTED",
}


def validate_observation(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate observation dictionary against contract rules.

    Does NOT mutate input data.
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return False, ["Input data must be a dictionary"]

    # Required metric_name: non-empty string
    metric_name = data.get("metric_name")
    if not isinstance(metric_name, str) or not metric_name.strip():
        errors.append("metric_name must be a non-empty string")

    # Required metric_value: JSON-serializable
    if "metric_value" not in data or data.get("metric_value") is None:
        errors.append("metric_value is required and cannot be None")
    else:
        try:
            json.dumps(data["metric_value"])
        except (TypeError, ValueError):
            errors.append("metric_value must be JSON-serializable")

    # Required observed_at: ISO8601 string or datetime
    observed_at = data.get("observed_at")
    if observed_at is None:
        errors.append("observed_at is required")
    elif isinstance(observed_at, str):
        try:
            datetime.fromisoformat(observed_at)
        except ValueError:
            errors.append("observed_at must be a valid ISO8601 string or datetime object")
    elif not isinstance(observed_at, datetime):
        errors.append("observed_at must be a valid ISO8601 string or datetime object")

    # Optional integer reference lists
    for ref_key in ("hypothesis_refs", "prediction_refs", "phenomenon_refs"):
        if ref_key in data and data[ref_key] is not None:
            val = data[ref_key]
            if not isinstance(val, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in val):
                errors.append(f"{ref_key} must be a list of integers")

    # Optional string reference list
    if "assumption_refs" in data and data["assumption_refs"] is not None:
        val = data["assumption_refs"]
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            errors.append("assumption_refs must be a list of strings")

    # Optional execution_conditions: dict
    if "execution_conditions" in data and data["execution_conditions"] is not None:
        if not isinstance(data["execution_conditions"], dict):
            errors.append("execution_conditions must be a dictionary")

    # Optional epistemic_classification
    epistemic_classification = data.get("epistemic_classification")
    if epistemic_classification is not None and epistemic_classification not in ALLOWED_EPISTEMIC_CLASSIFICATIONS:
        errors.append(
            f"epistemic_classification must be one of {sorted(ALLOWED_EPISTEMIC_CLASSIFICATIONS)}"
        )

    # Correction chain checks
    supersedes_id = data.get("supersedes_observation_id")
    correction_reason = data.get("correction_reason")

    if supersedes_id is not None:
        if not (isinstance(supersedes_id, int) and not isinstance(supersedes_id, bool)):
            errors.append("supersedes_observation_id must be an integer or None")
        if not correction_reason or not isinstance(correction_reason, str) or not correction_reason.strip():
            errors.append("correction_reason is required when supersedes_observation_id is set")

    return len(errors) == 0, errors


def normalize_observation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize observation dictionary according to contract rules.

    Does NOT mutate input data or auto-promote epistemic_classification beyond default.
    """
    normalized = dict(data)  # Shallow copy to avoid input mutation

    # Ensure list references default to empty list if absent/None
    for ref_key in ("hypothesis_refs", "prediction_refs", "phenomenon_refs"):
        if normalized.get(ref_key) is None:
            normalized[ref_key] = []

    if normalized.get("assumption_refs") is None:
        normalized["assumption_refs"] = []

    if normalized.get("execution_conditions") is None:
        normalized["execution_conditions"] = {}

    if normalized.get("provenance") is None:
        normalized["provenance"] = {}

    if "epistemic_classification" not in normalized or not normalized["epistemic_classification"]:
        normalized["epistemic_classification"] = "UNVALIDATED_OBSERVATION"

    if isinstance(normalized.get("observed_at"), datetime):
        normalized["observed_at"] = normalized["observed_at"].isoformat()

    return normalized


def canonical_serialize_observation(data: Dict[str, Any]) -> str:
    """Produce deterministic canonical JSON string for an observation.

    Does NOT mutate input data. Sorts keys and ensures stable formatting.
    """
    normalized = normalize_observation(data)

    # Filter canonical fields for hashing/serialization
    canonical_payload = {
        "metric_name": str(normalized.get("metric_name", "")),
        "metric_value": normalized.get("metric_value"),
        "metric_unit": normalized.get("metric_unit"),
        "tool_blueprint_id": normalized.get("tool_blueprint_id"),
        "tool_id": normalized.get("tool_id"),
        "experiment_run_id": normalized.get("experiment_run_id"),
        "execution_id": normalized.get("execution_id"),
        "hypothesis_refs": sorted(normalized.get("hypothesis_refs", [])),
        "prediction_refs": sorted(normalized.get("prediction_refs", [])),
        "assumption_refs": sorted(normalized.get("assumption_refs", [])),
        "phenomenon_refs": sorted(normalized.get("phenomenon_refs", [])),
        "execution_conditions": normalized.get("execution_conditions", {}),
        "observed_at": str(normalized.get("observed_at", "")),
        "epistemic_classification": str(normalized.get("epistemic_classification", "UNVALIDATED_OBSERVATION")),
        "provenance": normalized.get("provenance", {}),
        "supersedes_observation_id": normalized.get("supersedes_observation_id"),
        "correction_reason": normalized.get("correction_reason"),
    }

    return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))


def calculate_observation_hash(data: Dict[str, Any]) -> str:
    """Calculate SHA256 payload hash from canonical observation string."""
    canonical_str = canonical_serialize_observation(data)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def classify_conflict(obs1: Dict[str, Any], obs2: Dict[str, Any]) -> str:
    """Classify conflict relationship between two observations.

    Pure function. Returns one of:
      - "NO_CONFLICT"
      - "CONTRADICTION_SIGNAL" (same metric_name, different metric_value)
      - "POTENTIAL_DUPLICATE"  (same metric_name, same metric_value, different observed_at)
    """
    metric1 = obs1.get("metric_name")
    metric2 = obs2.get("metric_name")

    if not metric1 or not metric2 or metric1 != metric2:
        return "NO_CONFLICT"

    val1 = obs1.get("metric_value")
    val2 = obs2.get("metric_value")

    if val1 != val2:
        return "CONTRADICTION_SIGNAL"

    obs_at_1 = obs1.get("observed_at")
    obs_at_2 = obs2.get("observed_at")

    if obs_at_1 != obs_at_2:
        return "POTENTIAL_DUPLICATE"

    return "NO_CONFLICT"
