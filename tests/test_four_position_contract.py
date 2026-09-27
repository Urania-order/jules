"""
Tests for Four-Position Analysis Contract (TASK 24).
"""

import sys
import pytest
from smos.models.four_position_contract import (
    FourPosition,
    FOUR_POSITION_QUESTIONS,
    FOUR_POSITION_SCHEMA_DOC,
    FOUR_POSITION_DOC,
    POSITION_KEYS,
    normalize_four_position_analysis,
    validate_four_position_analysis,
    get_position,
    set_position_claim,
    is_four_position_analysis_complete,
)


def test_four_position_enum_has_four_values():
    assert len(FourPosition) == 4


def test_four_position_enum_exact_names():
    names = [p.value for p in FourPosition]
    assert names == ["PRESENT_EXISTS", "ABSENT_ABSENT", "ABSENT_EXISTS", "PRESENT_ABSENT"]


def test_four_position_questions_present():
    for pos in FourPosition:
        assert pos in FOUR_POSITION_QUESTIONS
        assert isinstance(FOUR_POSITION_QUESTIONS[pos], str)
        assert len(FOUR_POSITION_QUESTIONS[pos]) > 0


def test_four_position_questions_human_readable():
    assert "what will exist?" in FOUR_POSITION_QUESTIONS[FourPosition.PRESENT_EXISTS]
    assert "what will NOT exist?" in FOUR_POSITION_QUESTIONS[FourPosition.ABSENT_ABSENT]
    assert "what will exist instead?" in FOUR_POSITION_QUESTIONS[FourPosition.ABSENT_EXISTS]
    assert "what will it displace" in FOUR_POSITION_QUESTIONS[FourPosition.PRESENT_ABSENT]


def test_schema_doc_present():
    assert "Canonical Four-Position Analysis JSON Schema" in FOUR_POSITION_SCHEMA_DOC
    assert "phenomenon_id" in FOUR_POSITION_SCHEMA_DOC
    assert "positions" in FOUR_POSITION_SCHEMA_DOC


def test_position_keys_constant():
    assert POSITION_KEYS == (
        "claim",
        "confidence",
        "evidence",
        "context",
        "provenance",
        "epistemic_status",
    )


# Normalize tests
def test_normalize_none_returns_default():
    norm = normalize_four_position_analysis(None)
    assert norm["phenomenon_id"] == 0
    assert norm["created_at"] is None
    assert set(norm["positions"].keys()) == {
        "PRESENT_EXISTS",
        "ABSENT_ABSENT",
        "ABSENT_EXISTS",
        "PRESENT_ABSENT",
    }
    for pos in norm["positions"].values():
        assert pos == {}


def test_normalize_empty_returns_default():
    norm = normalize_four_position_analysis({})
    assert norm["phenomenon_id"] == 0
    assert norm["created_at"] is None
    assert set(norm["positions"].keys()) == {
        "PRESENT_EXISTS",
        "ABSENT_ABSENT",
        "ABSENT_EXISTS",
        "PRESENT_ABSENT",
    }


def test_normalize_partial_preserves_provided_positions():
    data = {
        "phenomenon_id": 42,
        "positions": {
            "PRESENT_EXISTS": {"claim": "High air quality"},
        },
    }
    norm = normalize_four_position_analysis(data)
    assert norm["phenomenon_id"] == 42
    assert norm["positions"]["PRESENT_EXISTS"]["claim"] == "High air quality"
    assert norm["positions"]["ABSENT_ABSENT"] == {}


def test_normalize_full_preserves_all_positions():
    data = {
        "phenomenon_id": 10,
        "positions": {
            "PRESENT_EXISTS": {"claim": "C1"},
            "ABSENT_ABSENT": {"claim": "C2"},
            "ABSENT_EXISTS": {"claim": "C3"},
            "PRESENT_ABSENT": {"claim": "C4"},
        },
    }
    norm = normalize_four_position_analysis(data)
    assert norm["phenomenon_id"] == 10
    assert norm["positions"]["PRESENT_EXISTS"]["claim"] == "C1"
    assert norm["positions"]["ABSENT_ABSENT"]["claim"] == "C2"
    assert norm["positions"]["ABSENT_EXISTS"]["claim"] == "C3"
    assert norm["positions"]["PRESENT_ABSENT"]["claim"] == "C4"


# Validate tests
def test_validate_accepts_canonical():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": {
                "claim": "Clean air in region",
                "confidence": 0.85,
                "evidence": [101, 102],
                "context": [5],
                "provenance": {"source": "expert"},
                "epistemic_status": "HYPOTHESIZED",
            },
            "ABSENT_ABSENT": {"claim": "Reduced respiratory incidents"},
            "ABSENT_EXISTS": {"claim": "Persistent smog"},
            "PRESENT_ABSENT": {"claim": "Industrial pollution plumes"},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is True
    assert errors == []


def test_validate_rejects_missing_positions_key():
    valid, errors = validate_four_position_analysis({"phenomenon_id": 1})
    assert valid is False
    assert any("positions" in e for e in errors)


def test_validate_rejects_unknown_position_key():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": {"claim": "ok"},
            "ABSENT_ABSENT": {"claim": "ok"},
            "ABSENT_EXISTS": {"claim": "ok"},
            "PRESENT_ABSENT": {"claim": "ok"},
            "UNKNOWN_POS": {"claim": "bad"},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is False
    assert any("Positions keys must match exactly" in e for e in errors)


def test_validate_rejects_non_dict_position():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": "not a dict",
            "ABSENT_ABSENT": {},
            "ABSENT_EXISTS": {},
            "PRESENT_ABSENT": {},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is False
    assert any("must be a dict" in e for e in errors)


def test_validate_rejects_empty_claim():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": {"claim": "   "},
            "ABSENT_ABSENT": {},
            "ABSENT_EXISTS": {},
            "PRESENT_ABSENT": {},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is False
    assert any("non-empty string" in e for e in errors)


def test_validate_rejects_bad_confidence():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": {"claim": "valid", "confidence": 1.5},
            "ABSENT_ABSENT": {},
            "ABSENT_EXISTS": {},
            "PRESENT_ABSENT": {},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is False
    assert any("between 0.0 and 1.0" in e for e in errors)


def test_validate_rejects_non_list_evidence():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": {"claim": "valid", "evidence": "not a list"},
            "ABSENT_ABSENT": {},
            "ABSENT_EXISTS": {},
            "PRESENT_ABSENT": {},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is False
    assert any("list of integers" in e for e in errors)


def test_validate_rejects_non_dict_provenance():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": {"claim": "valid", "provenance": ["not", "dict"]},
            "ABSENT_ABSENT": {},
            "ABSENT_EXISTS": {},
            "PRESENT_ABSENT": {},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is False
    assert any("provenance must be a dict" in e for e in errors)


def test_validate_accepts_partial_positions():
    analysis = {
        "phenomenon_id": 1,
        "positions": {
            "PRESENT_EXISTS": {"claim": "Partial claim"},
            "ABSENT_ABSENT": {},
            "ABSENT_EXISTS": {},
            "PRESENT_ABSENT": {},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is True
    assert errors == []


# Accessors tests
def test_get_position_returns_sub_dict():
    analysis = set_position_claim({}, FourPosition.PRESENT_EXISTS, "Test Claim", confidence=0.9)
    pos = get_position(analysis, FourPosition.PRESENT_EXISTS)
    assert pos["claim"] == "Test Claim"
    assert pos["confidence"] == 0.9


def test_get_position_returns_empty_for_missing():
    pos = get_position({}, FourPosition.PRESENT_EXISTS)
    assert pos == {}


def test_set_position_claim_populates_position():
    analysis = set_position_claim(
        {},
        "PRESENT_EXISTS",
        "Air filtration operational",
        confidence=0.8,
        evidence=[1, 2],
        context=[10],
        provenance={"agent": "tester"},
        epistemic_status="HYPOTHESIZED",
    )
    pos = get_position(analysis, FourPosition.PRESENT_EXISTS)
    assert pos["claim"] == "Air filtration operational"
    assert pos["confidence"] == 0.8
    assert pos["evidence"] == [1, 2]
    assert pos["context"] == [10]
    assert pos["provenance"] == {"agent": "tester"}
    assert pos["epistemic_status"] == "HYPOTHESIZED"


def test_set_position_claim_preserves_other_positions():
    a1 = set_position_claim({}, FourPosition.PRESENT_EXISTS, "Claim 1")
    a2 = set_position_claim(a1, FourPosition.ABSENT_ABSENT, "Claim 2")
    assert get_position(a2, FourPosition.PRESENT_EXISTS)["claim"] == "Claim 1"
    assert get_position(a2, FourPosition.ABSENT_ABSENT)["claim"] == "Claim 2"


def test_is_complete_false_when_missing_claims():
    analysis = set_position_claim({}, FourPosition.PRESENT_EXISTS, "Claim 1")
    assert is_four_position_analysis_complete(analysis) is False


def test_is_complete_true_when_all_claims_present():
    a = {}
    for pos in FourPosition:
        a = set_position_claim(a, pos, f"Claim for {pos.value}")
    assert is_four_position_analysis_complete(a) is True


# Semantics tests
def test_four_position_is_not_a_phenomenon():
    assert "modal analysis" in FOUR_POSITION_DOC or "modal projection" in FOUR_POSITION_DOC
    assert "create new Phenomena" in FOUR_POSITION_DOC or "projection" in FOUR_POSITION_DOC.lower()


def test_four_position_is_not_a_prediction():
    assert "Predictions" in FOUR_POSITION_DOC or "prediction" in FOUR_POSITION_DOC.lower()


def test_four_position_is_not_a_recipe():
    # Verify module does not import Recipe
    import smos.models.four_position_contract as mod
    assert not hasattr(mod, "Recipe")


def test_four_position_does_not_create_domain_relation():
    import smos.models.four_position_contract as mod
    assert not hasattr(mod, "DomainRelation")


def test_default_epistemic_status_is_hypothesized():
    analysis = set_position_claim({}, FourPosition.PRESENT_EXISTS, "A claim")
    pos = get_position(analysis, FourPosition.PRESENT_EXISTS)
    assert pos["epistemic_status"] == "HYPOTHESIZED"


def test_no_automatic_epistemic_promotion():
    analysis = set_position_claim({}, FourPosition.PRESENT_EXISTS, "A claim", confidence=1.0)
    pos = get_position(analysis, FourPosition.PRESENT_EXISTS)
    assert pos["epistemic_status"] == "HYPOTHESIZED"


# Integration smoke tests
def test_four_position_with_canonical_phenomenon_id():
    analysis = {
        "phenomenon_id": 99,
        "positions": {
            "PRESENT_EXISTS": {"claim": "P1"},
            "ABSENT_ABSENT": {"claim": "P2"},
            "ABSENT_EXISTS": {"claim": "P3"},
            "PRESENT_ABSENT": {"claim": "P4"},
        },
    }
    valid, errors = validate_four_position_analysis(analysis)
    assert valid is True
    assert errors == []


def test_four_position_scenario_air_cleaning_facility():
    # Air cleaning facility hypothesis scenario
    analysis = normalize_four_position_analysis({"phenomenon_id": 77})
    analysis = set_position_claim(
        analysis,
        FourPosition.PRESENT_EXISTS,
        "Clean local ambient air and reduced particulate matter.",
        confidence=0.9,
        context=[12],
    )
    analysis = set_position_claim(
        analysis,
        FourPosition.ABSENT_ABSENT,
        "Absence of localized air filter operational logs.",
        confidence=0.85,
    )
    analysis = set_position_claim(
        analysis,
        FourPosition.ABSENT_EXISTS,
        "Continued atmospheric pollutant accumulation.",
        confidence=0.95,
    )
    analysis = set_position_claim(
        analysis,
        FourPosition.PRESENT_ABSENT,
        "Displacement of persistent toxic smog layer.",
        confidence=0.88,
    )

    valid, errors = validate_four_position_analysis(analysis)
    assert valid is True
    assert errors == []
    assert is_four_position_analysis_complete(analysis) is True
