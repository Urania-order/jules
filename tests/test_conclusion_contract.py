import pytest
from sqlalchemy.orm import Session
from smos.models.conclusion_contract import (
    CLAIM,
    TEXT,
    CONFIDENCE,
    CONCLUSION_SCHEMA_DOC,
    normalize_conclusion,
    get_claim,
    get_confidence,
    validate_conclusion,
)
from smos.models.context_exposure import ContextExposure, AgentType
from smos.services.context_exposure_service import ContextExposureService
from smos.services.convergent_resonance_service import ConvergentResonanceService


def test_normalize_conclusion_returns_dict():
    raw = {"claim": "Hypothesis X holds", "confidence": 0.85}
    norm = normalize_conclusion(raw)
    assert isinstance(norm, dict)
    assert norm == raw


def test_normalize_conclusion_handles_none():
    assert normalize_conclusion(None) == {}
    assert normalize_conclusion("invalid") == {}
    assert normalize_conclusion(123) == {}


def test_normalize_conclusion_preserves_extra_keys():
    raw = {
        "claim": "Test claim",
        "detail": {"step": 1},
        "context_ids": [1, 2],
        "custom_key": "custom_val",
    }
    norm = normalize_conclusion(raw)
    assert norm["custom_key"] == "custom_val"
    assert norm["detail"] == {"step": 1}


def test_get_claim_returns_claim():
    c = {"claim": "Hypothesis X holds under condition C", "confidence": 0.85}
    assert get_claim(c) == "Hypothesis X holds under condition C"


def test_get_claim_falls_back_to_text():
    c = {"text": "Analysis complete"}
    assert get_claim(c) == "Analysis complete"


def test_get_claim_returns_empty_string_when_missing():
    assert get_claim({}) == ""
    assert get_claim({"confidence": 0.9}) == ""
    assert get_claim({"claim": "   "}) == ""


def test_get_claim_returns_empty_string_when_not_dict():
    assert get_claim(None) == ""
    assert get_claim("not a dict") == ""
    assert get_claim(42) == ""


def test_get_confidence_returns_float():
    assert get_confidence({"confidence": 0.85}) == 0.85
    assert get_confidence({"confidence": "0.75"}) == 0.75
    assert get_confidence({"confidence": 1}) == 1.0
    assert get_confidence({"confidence": 0}) == 0.0


def test_get_confidence_returns_none_when_missing():
    assert get_confidence({}) is None
    assert get_confidence({"claim": "test"}) is None
    assert get_confidence({"confidence": None}) is None


def test_get_confidence_returns_none_when_invalid():
    assert get_confidence({"confidence": "invalid"}) is None
    assert get_confidence({"confidence": 1.5}) is None
    assert get_confidence({"confidence": -0.1}) is None
    assert get_confidence({"confidence": True}) is None


def test_validate_conclusion_accepts_canonical():
    c = {
        "claim": "Hypothesis X holds",
        "confidence": 0.85,
        "detail": {"notes": "valid"},
    }
    valid, errors = validate_conclusion(c)
    assert valid is True
    assert errors == []


def test_validate_conclusion_accepts_text_fallback():
    c = {"text": "Analysis complete"}
    valid, errors = validate_conclusion(c)
    assert valid is True
    assert errors == []


def test_validate_conclusion_rejects_empty_claim():
    valid1, errors1 = validate_conclusion({})
    assert valid1 is False
    assert len(errors1) > 0

    valid2, errors2 = validate_conclusion({"claim": ""})
    assert valid2 is False
    assert len(errors2) > 0


def test_validate_conclusion_rejects_invalid_confidence():
    c_out_of_bounds = {"claim": "Claim", "confidence": 1.5}
    valid1, errors1 = validate_conclusion(c_out_of_bounds)
    assert valid1 is False
    assert len(errors1) > 0

    c_non_numeric = {"claim": "Claim", "confidence": "abc"}
    valid2, errors2 = validate_conclusion(c_non_numeric)
    assert valid2 is False
    assert len(errors2) > 0


def test_validate_conclusion_accepts_missing_confidence():
    c = {"claim": "Claim without confidence"}
    valid, errors = validate_conclusion(c)
    assert valid is True
    assert errors == []


def test_existing_context_exposure_conclusion_shape_still_works():
    c1 = {"claim": "Fault line active", "confidence": 0.8}
    assert get_claim(c1) == "Fault line active"
    assert get_confidence(c1) == 0.8

    c2 = {"claim": "Analysis complete"}
    assert get_claim(c2) == "Analysis complete"
    assert get_confidence(c2) is None


def test_context_exposure_service_normalize_on_record(db: Session):
    service = ContextExposureService(db)
    raw_conclusion = {"claim": "Service test claim", "confidence": 0.9, "extra": "data"}

    exposure = service.record(
        agent_type="LLM",
        agent_id=1,
        role="analyst",
        conclusion=raw_conclusion,
    )

    assert exposure.conclusion["claim"] == "Service test claim"
    assert exposure.conclusion["extra"] == "data"
    assert get_claim(exposure.conclusion) == "Service test claim"
    assert get_confidence(exposure.conclusion) == 0.9

    valid, errors = validate_conclusion(exposure.conclusion)
    assert valid is True


def test_convergent_resonance_uses_contract_helpers(db: Session):
    service = ContextExposureService(db)

    # Record exposures with matching claims
    c = {"claim": "Fault line active", "confidence": 0.8}
    exposure1 = service.record(
        agent_type="HUMAN",
        agent_id=1,
        role="geologist",
        context_ids=[101],
        conclusion=c,
    )
    exposure2 = service.record(
        agent_type="LLM",
        agent_id=2,
        role="seismologist",
        context_ids=[102],
        conclusion=c,
    )

    # Verify contract helpers on stored exposures
    norm1 = normalize_conclusion(exposure1.conclusion)
    norm2 = normalize_conclusion(exposure2.conclusion)
    assert get_claim(norm1) == "Fault line active"
    assert get_claim(norm2) == "Fault line active"

    valid1, _ = validate_conclusion(norm1)
    valid2, _ = validate_conclusion(norm2)
    assert valid1 is True and valid2 is True

    # Test ConvergentResonanceService detection
    resonance_service = ConvergentResonanceService(db)
    candidates = resonance_service.detect(min_agents=2)

    assert len(candidates) == 1
    assert candidates[0].kind == "candidate_resonance"
    assert get_claim(candidates[0].converging_conclusion) == "Fault line active"
