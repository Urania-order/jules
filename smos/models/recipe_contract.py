"""
Recipe Learning Evidence Contract — contract for analytical learning evidence.

Contract-as-code module without persistence layer (no SQLAlchemy model, no DB table).

This module defines the relationship between analytical evidence and reusable procedural knowledge (Recipe).

Semantics:
    - source_exposure_ids  -> references ContextExposure.id
    - source_prediction_ids -> references Prediction.id
    - source_event_ids      -> references DomainEvent.id
    - knowledge_ids         -> references MemoryNode.id
"""

from typing import Any, Dict, List, Optional, Tuple

SOURCE_EXPOSURE_IDS = "source_exposure_ids"
SOURCE_PREDICTION_IDS = "source_prediction_ids"
SOURCE_EVENT_IDS = "source_event_ids"
KNOWLEDGE_IDS = "knowledge_ids"
EVALUATION_SUMMARY = "evaluation_summary"
CREATED_AT = "created_at"

LEARNING_EVIDENCE_SCHEMA_DOC = """
Canonical Learning Evidence JSON Schema:

{
  "source_exposure_ids": [int],   # list of ContextExposure.id
  "source_prediction_ids": [int], # list of Prediction.id
  "source_event_ids": [int],      # list of DomainEvent.id
  "knowledge_ids": [int],         # list of MemoryNode.id
  "evaluation_summary": dict,     # aggregate summary over linked evidence
  "created_at": string | null     # ISO timestamp or null
}
"""

LEARNING_LOOP_DOC = """
Learning Loop Concept:

Recipe != Learning Loop.
- Recipe is a reusable procedure ("How can X be done?").
- Learning Loop is the analytical process ("What did the system learn from an observed analytical process?").

Conceptual progression:
    Analysis -> Conclusion -> Prediction -> Outcome -> Evaluation -> Learning -> reusable Recipe

Learning Loop connects analytical evidence to reusable knowledge without altering
existing Recipe models or automatically promoting epistemic statuses.
"""


def normalize_learning_evidence(evidence: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize learning evidence input to a dictionary with default fields.

    Does not remove invalid elements (validation rejects invalid payloads);
    converts None / missing fields to default values.
    """
    if evidence is None or not isinstance(evidence, dict):
        return {
            SOURCE_EXPOSURE_IDS: [],
            SOURCE_PREDICTION_IDS: [],
            SOURCE_EVENT_IDS: [],
            KNOWLEDGE_IDS: [],
            EVALUATION_SUMMARY: {},
            CREATED_AT: None,
        }

    res = dict(evidence)
    if SOURCE_EXPOSURE_IDS not in res or res[SOURCE_EXPOSURE_IDS] is None:
        res[SOURCE_EXPOSURE_IDS] = []
    if SOURCE_PREDICTION_IDS not in res or res[SOURCE_PREDICTION_IDS] is None:
        res[SOURCE_PREDICTION_IDS] = []
    if SOURCE_EVENT_IDS not in res or res[SOURCE_EVENT_IDS] is None:
        res[SOURCE_EVENT_IDS] = []
    if KNOWLEDGE_IDS not in res or res[KNOWLEDGE_IDS] is None:
        res[KNOWLEDGE_IDS] = []
    if EVALUATION_SUMMARY not in res or res[EVALUATION_SUMMARY] is None:
        res[EVALUATION_SUMMARY] = {}
    if CREATED_AT not in res:
        res[CREATED_AT] = None

    return res


def validate_learning_evidence(evidence: Any) -> Tuple[bool, List[str]]:
    """Validate learning evidence payload against the Learning Evidence JSON contract.

    Returns (True, []) if valid, (False, errors) otherwise.
    """
    errors: List[str] = []
    if not isinstance(evidence, dict):
        return False, ["Learning evidence must be a dict"]

    id_fields = [
        (SOURCE_EXPOSURE_IDS, "source_exposure_ids"),
        (SOURCE_PREDICTION_IDS, "source_prediction_ids"),
        (SOURCE_EVENT_IDS, "source_event_ids"),
        (KNOWLEDGE_IDS, "knowledge_ids"),
    ]

    for key, label in id_fields:
        if key in evidence and evidence[key] is not None:
            val = evidence[key]
            if not isinstance(val, list):
                errors.append(f"Field '{label}' must be a list of integers")
            else:
                for elem in val:
                    if isinstance(elem, bool) or not isinstance(elem, int):
                        errors.append(f"Field '{label}' contains non-integer element: {elem!r}")
                        break

    if EVALUATION_SUMMARY in evidence and evidence[EVALUATION_SUMMARY] is not None:
        if not isinstance(evidence[EVALUATION_SUMMARY], dict):
            errors.append("Field 'evaluation_summary' must be a dict")

    return len(errors) == 0, errors


def get_sources(evidence: Optional[Dict[str, Any]]) -> Dict[str, List[int]]:
    """Extract typed source ID lists from learning evidence dictionary."""
    normalized = normalize_learning_evidence(evidence)
    return {
        SOURCE_EXPOSURE_IDS: list(normalized.get(SOURCE_EXPOSURE_IDS, [])),
        SOURCE_PREDICTION_IDS: list(normalized.get(SOURCE_PREDICTION_IDS, [])),
        SOURCE_EVENT_IDS: list(normalized.get(SOURCE_EVENT_IDS, [])),
        KNOWLEDGE_IDS: list(normalized.get(KNOWLEDGE_IDS, [])),
    }
