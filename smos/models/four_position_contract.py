"""
Four-Position Analysis Contract.

Contract-as-code module without persistence layer
(no SQLAlchemy model, no DB table) UNLESS STEP 0 finds
a canonical persistent FourPosition model already exists.

Four positions of one Phenomenon₀:

    I   PRESENT_EXISTS   "If present, what exists?"
    II  ABSENT_ABSENT    "If absent, what does not exist?"
    III ABSENT_EXISTS    "If absent, what exists instead?"
    IV  PRESENT_ABSENT   "If present, what does not exist?"

Each position is a modal projection, not a fact.
"""

import copy
import enum
from typing import Any, Dict, List, Optional, Tuple


class FourPosition(str, enum.Enum):
    PRESENT_EXISTS = "PRESENT_EXISTS"   # I
    ABSENT_ABSENT = "ABSENT_ABSENT"    # II
    ABSENT_EXISTS = "ABSENT_EXISTS"    # III
    PRESENT_ABSENT = "PRESENT_ABSENT"   # IV


FOUR_POSITION_QUESTIONS = {
    FourPosition.PRESENT_EXISTS:
        "If the phenomenon emerges, what will exist?",
    FourPosition.ABSENT_ABSENT:
        "If the phenomenon does not emerge, what will NOT exist?",
    FourPosition.ABSENT_EXISTS:
        "If the phenomenon does not emerge, what will exist instead?",
    FourPosition.PRESENT_ABSENT:
        "If the phenomenon emerges, what will NOT exist (what will it displace)?",
}


FOUR_POSITION_SCHEMA_DOC = """
Canonical Four-Position Analysis JSON Schema:

{
  "phenomenon_id": int,                    # REQUIRED — source Phenomenon₀
  "positions": {
    "PRESENT_EXISTS": {
      "claim": "string",
      "confidence": 0.0,
      "evidence": [int],
      "context": [int],
      "provenance": {},
      "epistemic_status": "HYPOTHESIZED"
    },
    "ABSENT_ABSENT": { ... },
    "ABSENT_EXISTS": { ... },
    "PRESENT_ABSENT": { ... }
  },
  "created_at": string | null
}
"""

FOUR_POSITION_DOC = """
Four-Position Analysis is a modal analysis of one Phenomenon₀.
It does NOT create new Phenomena, DomainRelations, or Predictions.
It does NOT promote modal claims to fact.
Each position is HYPOTHESIZED by default.
"""

POSITION_KEYS = (
    "claim",
    "confidence",
    "evidence",
    "context",
    "provenance",
    "epistemic_status",
)

ALLOWED_EPISTEMIC_STATUSES = {
    "HYPOTHESIZED",
    "INFERRED",
    "PREDICTED",
    "UNVALIDATED",
    "CONTESTED",
    "REFUTED",
    "OBSERVED",
}


def _pos_key(position: FourPosition | str) -> str:
    if isinstance(position, FourPosition):
        return position.value
    return str(position)


def normalize_four_position_analysis(
    analysis: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a normalized dict with all 4 positions present (default empty)."""
    if not isinstance(analysis, dict):
        base: Dict[str, Any] = {}
    else:
        base = copy.deepcopy(analysis)

    phenomenon_id = base.get("phenomenon_id", 0)
    if not isinstance(phenomenon_id, int) or isinstance(phenomenon_id, bool):
        phenomenon_id = 0

    created_at = base.get("created_at", None)

    positions_raw = base.get("positions")
    if not isinstance(positions_raw, dict):
        positions_raw = {}

    positions: Dict[str, Any] = {}
    for pos in FourPosition:
        key = pos.value
        val = positions_raw.get(key)
        if isinstance(val, dict):
            positions[key] = copy.deepcopy(val)
        else:
            positions[key] = {}

    return {
        "phenomenon_id": phenomenon_id,
        "positions": positions,
        "created_at": created_at,
    }


def validate_four_position_analysis(
    analysis: Any,
) -> Tuple[bool, List[str]]:
    """Validate structure and semantics."""
    errors: List[str] = []

    if not isinstance(analysis, dict):
        return False, ["Analysis must be a dict"]

    if "phenomenon_id" not in analysis:
        errors.append("Missing required field 'phenomenon_id'")
    else:
        pid = analysis["phenomenon_id"]
        if not isinstance(pid, int) or isinstance(pid, bool) or pid < 0:
            errors.append(f"Invalid phenomenon_id '{pid}': must be a non-negative integer")

    if "positions" not in analysis:
        errors.append("Missing required field 'positions'")
        return False, errors

    positions = analysis["positions"]
    if not isinstance(positions, dict):
        errors.append("Field 'positions' must be a dict")
        return False, errors

    expected_keys = {pos.value for pos in FourPosition}
    actual_keys = set(positions.keys())

    if actual_keys != expected_keys:
        errors.append(f"Positions keys must match exactly {sorted(expected_keys)}, got {sorted(actual_keys)}")

    for key in sorted(actual_keys):
        pos_val = positions[key]
        if not isinstance(pos_val, dict):
            errors.append(f"Position '{key}' must be a dict")
            continue

        if "claim" in pos_val and pos_val["claim"] is not None:
            claim = pos_val["claim"]
            if not isinstance(claim, str) or not claim.strip():
                errors.append(f"Position '{key}' claim must be a non-empty string")

        if "confidence" in pos_val and pos_val["confidence"] is not None:
            conf = pos_val["confidence"]
            if isinstance(conf, bool):
                errors.append(f"Position '{key}' confidence must be numeric float, got bool")
            else:
                try:
                    fconf = float(conf)
                    if not (0.0 <= fconf <= 1.0):
                        errors.append(f"Position '{key}' confidence must be float between 0.0 and 1.0")
                except (ValueError, TypeError):
                    errors.append(f"Position '{key}' confidence must be numeric float")

        if "evidence" in pos_val and pos_val["evidence"] is not None:
            ev = pos_val["evidence"]
            if not isinstance(ev, list) or any(not isinstance(x, int) or isinstance(x, bool) for x in ev):
                errors.append(f"Position '{key}' evidence must be a list of integers")

        if "context" in pos_val and pos_val["context"] is not None:
            ctx = pos_val["context"]
            if not isinstance(ctx, list) or any(not isinstance(x, int) or isinstance(x, bool) for x in ctx):
                errors.append(f"Position '{key}' context must be a list of integers")

        if "provenance" in pos_val and pos_val["provenance"] is not None:
            prov = pos_val["provenance"]
            if not isinstance(prov, dict):
                errors.append(f"Position '{key}' provenance must be a dict")

        if "epistemic_status" in pos_val and pos_val["epistemic_status"] is not None:
            st = pos_val["epistemic_status"]
            if not isinstance(st, str) or st not in ALLOWED_EPISTEMIC_STATUSES:
                errors.append(f"Position '{key}' epistemic_status must be one of {sorted(ALLOWED_EPISTEMIC_STATUSES)}")

    return len(errors) == 0, errors


def get_position(
    analysis: Dict[str, Any],
    position: FourPosition | str,
) -> Dict[str, Any]:
    """Return the sub-dict for a given position (empty if missing)."""
    if not isinstance(analysis, dict):
        return {}
    key = _pos_key(position)
    positions = analysis.get("positions")
    if isinstance(positions, dict):
        val = positions.get(key)
        if isinstance(val, dict):
            return copy.deepcopy(val)
    return {}


def set_position_claim(
    analysis: Dict[str, Any],
    position: FourPosition | str,
    claim: str,
    confidence: Optional[float] = None,
    evidence: Optional[List[int]] = None,
    context: Optional[List[int]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    epistemic_status: str = "HYPOTHESIZED",
) -> Dict[str, Any]:
    """Return a new analysis dict with the given position populated."""
    norm = normalize_four_position_analysis(analysis)
    key = _pos_key(position)

    pos_dict: Dict[str, Any] = {
        "claim": claim,
        "epistemic_status": epistemic_status,
    }
    if confidence is not None:
        pos_dict["confidence"] = confidence
    if evidence is not None:
        pos_dict["evidence"] = list(evidence)
    if context is not None:
        pos_dict["context"] = list(context)
    if provenance is not None:
        pos_dict["provenance"] = dict(provenance)

    norm["positions"][key] = pos_dict
    return norm


def is_four_position_analysis_complete(
    analysis: Dict[str, Any],
) -> bool:
    """True if all 4 positions have a non-empty claim."""
    if not isinstance(analysis, dict):
        return False
    positions = analysis.get("positions")
    if not isinstance(positions, dict):
        return False

    for pos in FourPosition:
        key = pos.value
        pos_data = positions.get(key)
        if not isinstance(pos_data, dict):
            return False
        claim = pos_data.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            return False

    return True
