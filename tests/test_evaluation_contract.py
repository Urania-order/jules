"""Contract unit tests for Evaluation Contract (TASK L-05A)."""

from datetime import datetime, timezone

from smos.models.evaluation import EvaluationStatus
from smos.models.evaluation_contract import (
    canonical_evaluation_json,
    compute_evaluation_hash,
    normalize_evaluation_result,
    validate_evaluation_request,
    validate_evaluation_result,
)


def test_valid_evaluation_request():
    req = {
        "target_type": "prediction",
        "target_id": 1,
        "prediction_id": 1,
        "criteria": {"criteria_id": "c1", "specs": [{"metric_name": "temp", "expected_value": 25.0}]},
        "as_of": "2026-10-14T10:00:00Z",
    }
    valid, errors = validate_evaluation_request(req)
    assert valid is True
    assert errors == []


def test_invalid_target_type():
    req = {"target_type": "invalid_type", "target_id": 1}
    valid, errors = validate_evaluation_request(req)
    assert valid is False
    assert any("Target type 'invalid_type' is not supported" in e for e in errors)


def test_invalid_target_id():
    req = {"target_type": "prediction", "target_id": -5}
    valid, errors = validate_evaluation_request(req)
    assert valid is False
    assert any("Field 'target_id' must be a positive integer" in e for e in errors)


def test_forbidden_keys_rejected():
    req = {
        "target_type": "prediction",
        "target_id": 1,
        "promote_to_fact": True,
        "epistemic_status_mutation": "VERIFIED",
    }
    valid, errors = validate_evaluation_request(req)
    assert valid is False
    assert any("Forbidden key" in e for e in errors)


def test_validate_evaluation_result_valid():
    res = {
        "target_type": "prediction",
        "target_id": 1,
        "status": "CONFIRMED",
        "observation_refs": [10, 11],
        "excluded_observation_refs": [],
        "criterion_findings": [{"metric_name": "temp", "status": "CONFIRMED"}],
        "uncertainty_notes": [],
    }
    valid, errors = validate_evaluation_result(res)
    assert valid is True
    assert errors == []


def test_validate_evaluation_result_invalid_status():
    res = {
        "target_type": "prediction",
        "target_id": 1,
        "status": "PROMOTED_TO_FACT",
    }
    valid, errors = validate_evaluation_result(res)
    assert valid is False
    assert any("Invalid evaluation status" in e for e in errors)


def test_normalize_evaluation_result_and_hash_stability():
    raw = {
        "target_type": "PREDICTION",
        "target_id": 42,
        "status": EvaluationStatus.CONFIRMED,
        "observation_refs": [2, 1],
        "excluded_observation_refs": [3],
        "criterion_findings": [{"metric": "a"}],
    }
    norm1 = normalize_evaluation_result(raw)
    norm2 = normalize_evaluation_result(raw)

    assert norm1["status"] == "CONFIRMED"
    assert norm1["target_type"] == "prediction"
    assert norm1["record_hash"] is not None
    assert norm1["record_hash"] == norm2["record_hash"]


def test_canonical_json_ignores_id_and_eval_time():
    res1 = {
        "id": 1,
        "target_type": "prediction",
        "target_id": 10,
        "status": "CONFIRMED",
        "evaluated_at": "2026-10-14T10:00:00Z",
        "observation_refs": [1, 2],
    }
    res2 = {
        "id": 999,
        "target_type": "prediction",
        "target_id": 10,
        "status": "CONFIRMED",
        "evaluated_at": "2026-10-15T12:00:00Z",
        "observation_refs": [2, 1],  # order differs, canonical sorts it
    }

    cj1 = canonical_evaluation_json(res1)
    cj2 = canonical_evaluation_json(res2)
    assert cj1 == cj2
    assert compute_evaluation_hash(res1) == compute_evaluation_hash(res2)


def test_validation_does_not_mutate_input():
    req = {"target_type": "prediction", "target_id": 10, "as_of": "2026-10-14T00:00:00Z"}
    req_copy = dict(req)
    validate_evaluation_request(req)
    assert req == req_copy
