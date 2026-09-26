"""
Conclusion Contract — explicit JSON contract for conclusion payload in ContextExposure.

Contract-as-code module without persistence layer (no SQLAlchemy model, no DB table).
"""

from typing import Any, Dict, List, Optional, Tuple

CLAIM = "claim"
TEXT = "text"
CONFIDENCE = "confidence"

CONCLUSION_SCHEMA_DOC = """
Canonical Conclusion JSON Schema:

{
  "claim": "string",          # REQUIRED (or "text" fallback)
  "text": "string",           # fallback for claim
  "confidence": 0.0,          # OPTIONAL, float in [0, 1]
  "detail": {...},            # OPTIONAL, free-form
  "context_ids": [...],       # OPTIONAL, list of int
  "evidence_ids": [...],      # OPTIONAL, list of int
  "provenance": {...}         # OPTIONAL, free-form
}
"""


def normalize_conclusion(conclusion: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize conclusion input to a dictionary, preserving all extra keys."""
    if conclusion is None or not isinstance(conclusion, dict):
        return {}
    return dict(conclusion)


def get_claim(conclusion: Optional[Dict[str, Any]]) -> str:
    """Extract claim from conclusion dictionary, falling back to 'text' key.

    Returns empty string if not a dict or no claim/text found.
    """
    if not isinstance(conclusion, dict):
        return ""
    claim = conclusion.get(CLAIM) or conclusion.get(TEXT) or ""
    return str(claim).strip()


def get_confidence(conclusion: Optional[Dict[str, Any]]) -> Optional[float]:
    """Extract confidence as float from conclusion dictionary.

    Returns float in [0.0, 1.0] or None if missing or invalid.
    """
    if not isinstance(conclusion, dict):
        return None
    if CONFIDENCE not in conclusion or conclusion[CONFIDENCE] is None:
        return None
    val = conclusion[CONFIDENCE]
    if isinstance(val, bool):
        return None
    try:
        fval = float(val)
        if 0.0 <= fval <= 1.0:
            return fval
        return None
    except (ValueError, TypeError):
        return None


def validate_conclusion(conclusion: Any) -> Tuple[bool, List[str]]:
    """Validate a conclusion payload against the Conclusion JSON contract.

    Returns (True, []) if valid, (False, errors) otherwise.
    """
    errors: List[str] = []
    if not isinstance(conclusion, dict):
        return False, ["Conclusion must be a dict"]

    claim = get_claim(conclusion)
    if not claim:
        errors.append("Missing required field 'claim' or 'text' (or value is empty)")

    if CONFIDENCE in conclusion and conclusion[CONFIDENCE] is not None:
        conf_val = conclusion[CONFIDENCE]
        if isinstance(conf_val, bool):
            errors.append(f"Invalid confidence '{conf_val}': must be numeric float")
        else:
            try:
                fval = float(conf_val)
                if not (0.0 <= fval <= 1.0):
                    errors.append(f"Invalid confidence '{conf_val}': must be a float between 0.0 and 1.0")
            except (ValueError, TypeError):
                errors.append(f"Invalid confidence '{conf_val}': must be numeric")

    return len(errors) == 0, errors
