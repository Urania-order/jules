"""Replay Contract (TASK L-05B).

Defines validation, normalization, canonical serialization, SHA-256 hashing,
and fidelity/completeness classifications for temporal replay requests and results.

CRITICAL INVARIANTS:
1. Knowledge time vs Event time: System availability determines eligibility.
2. Historical fidelity: Entities are classified as VERIFIED, PARTIAL, or UNKNOWN.
3. Content hash stability: content_hash is computed over canonical historical result
   and format_version, strictly excluding `reconstructed_at` and execution metadata.
4. Versioning gap: Explicitly documented as content of Prediction/Hypothesis/Phenomenon/etc.
   is not historically versioned.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

FORMAT_VERSION = "1.0.0"

SUPPORTED_SCOPES = [
    "observation",
    "experiment_run",
    "evaluation",
    "prediction",
    "hypothesis",
    "phenomenon",
    "potential_phenomenon",
    "domain_relation",
    "provenance_record",
]

SUPPORTED_MODES = ["computation", "persisted"]

VALID_FIDELITY = ["VERIFIED", "PARTIAL", "UNKNOWN"]
VALID_COMPLETENESS = ["COMPLETE", "PARTIAL", "INCOMPLETE"]


def validate_replay_request(request: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a temporal replay request dictionary against contract rules."""
    errors: List[str] = []

    if not isinstance(request, dict):
        return False, ["Replay request must be a dictionary"]

    # Cutoff as_of (required)
    if "as_of" not in request or request["as_of"] is None:
        errors.append("Field 'as_of' is required")
    else:
        as_of = request["as_of"]
        if isinstance(as_of, str):
            try:
                dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    errors.append("Field 'as_of' string must be timezone-aware")
            except ValueError:
                errors.append(f"Field 'as_of' string must be valid ISO-formatted datetime, got {as_of!r}")
        elif isinstance(as_of, datetime):
            if as_of.tzinfo is None:
                errors.append("Field 'as_of' datetime object must be timezone-aware")
        else:
            errors.append(f"Field 'as_of' must be an ISO string or datetime object, got type {type(as_of).__name__}")

    # Scope (optional)
    scope = request.get("scope")
    if scope is not None:
        if not isinstance(scope, list):
            errors.append("Field 'scope' must be a list if provided")
        else:
            for item in scope:
                if not isinstance(item, str) or item.strip().lower() not in SUPPORTED_SCOPES:
                    errors.append(f"Scope item '{item}' is invalid. Allowed scopes: {SUPPORTED_SCOPES}")

    # Mode (optional)
    mode = request.get("mode")
    if mode is not None:
        if mode not in SUPPORTED_MODES:
            errors.append(f"Field 'mode' must be one of {SUPPORTED_MODES}, got {mode!r}")

    return len(errors) == 0, errors


def validate_replay_result(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a temporal replay result dictionary against contract rules."""
    errors: List[str] = []

    if not isinstance(result, dict):
        return False, ["Replay result must be a dictionary"]

    # as_of
    if not result.get("as_of"):
        errors.append("Field 'as_of' is required in replay result")

    # completeness
    completeness = result.get("completeness")
    if completeness not in VALID_COMPLETENESS:
        errors.append(f"Field 'completeness' must be one of {VALID_COMPLETENESS}, got {completeness!r}")

    # reconstructed_state
    rec_state = result.get("reconstructed_state")
    if not isinstance(rec_state, dict):
        errors.append("Field 'reconstructed_state' must be a dictionary")

    # content_hash
    content_hash = result.get("content_hash")
    if not content_hash or not isinstance(content_hash, str):
        errors.append("Field 'content_hash' must be a non-empty string")

    return len(errors) == 0, errors


def canonical_replay_json(result: Dict[str, Any]) -> str:
    """Generate deterministic JSON representation of the historical replay state.

    EXCLUDES volatile runtime metadata such as `reconstructed_at` and `id` of execution wrapper.
    """
    rec_state = result.get("reconstructed_state") or {}

    def _sort_entities(entities_list: Any) -> List[Dict[str, Any]]:
        if not isinstance(entities_list, list):
            return []
        sorted_list = []
        for e in entities_list:
            if isinstance(e, dict):
                sorted_list.append(e)
        return sorted(sorted_list, key=lambda x: str(x.get("id", "")))

    canonical_state = {
        k: _sort_entities(rec_state.get(k)) for k in sorted(rec_state.keys())
    }

    diagnostics = result.get("reconstruction_diagnostics") or {}
    prov = result.get("provenance") or {}

    payload = {
        "as_of": result.get("as_of"),
        "format_version": result.get("format_version") or FORMAT_VERSION,
        "completeness": result.get("completeness"),
        "reconstructed_state": canonical_state,
        "reconstruction_diagnostics": diagnostics,
        "provenance": prov,
        "uncertainty_notes": result.get("uncertainty_notes") or [],
        "source_integrity_verified": bool(result.get("source_integrity_verified", True)),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_replay_hash(result: Dict[str, Any]) -> str:
    """Compute SHA-256 hash over canonical historical replay result (excluding reconstructed_at)."""
    canonical_str = canonical_replay_json(result)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def normalize_replay_result(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize replay result dictionary into canonical representation."""
    if not isinstance(raw_result, dict):
        raw_result = {}

    as_of = raw_result.get("as_of")
    if isinstance(as_of, datetime):
        as_of_str = as_of.isoformat()
    elif isinstance(as_of, str):
        as_of_str = as_of
    else:
        as_of_str = None

    reconstructed_at = raw_result.get("reconstructed_at")
    if isinstance(reconstructed_at, datetime):
        reconstructed_at_str = reconstructed_at.isoformat()
    elif isinstance(reconstructed_at, str):
        reconstructed_at_str = reconstructed_at
    else:
        reconstructed_at_str = datetime.now(timezone.utc).isoformat()

    completeness = raw_result.get("completeness")
    if completeness not in VALID_COMPLETENESS:
        completeness = "INCOMPLETE"

    rec_state = raw_result.get("reconstructed_state") or {}
    diagnostics = raw_result.get("reconstruction_diagnostics") or {
        "excluded_counts": {},
        "unknown_availability": {},
        "missing_status_history": [],
        "versioning_gap": {
            "entities": ["prediction", "hypothesis", "phenomenon", "potential_phenomenon", "discovery_recovery"],
            "impact": "Content of domain entities is not historically versioned; presence/existence and status history only are verified.",
        },
        "snapshot_isolation": {
            "supported": True,
            "limitations": "In-memory query isolation against current session database transaction boundary.",
        },
    }

    normalized = {
        "as_of": as_of_str,
        "format_version": raw_result.get("format_version") or FORMAT_VERSION,
        "completeness": completeness,
        "reconstructed_state": rec_state,
        "reconstruction_diagnostics": diagnostics,
        "provenance": raw_result.get("provenance") or {"provenance_refs": [], "relation_refs": []},
        "uncertainty_notes": list(raw_result.get("uncertainty_notes") or []),
        "source_integrity_verified": bool(raw_result.get("source_integrity_verified", True)),
        "content_hash": None,
        "reconstructed_at": reconstructed_at_str,
    }

    normalized["content_hash"] = compute_replay_hash(normalized)
    return normalized
