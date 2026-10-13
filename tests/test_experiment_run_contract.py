"""Tests for ExperimentRun contract (TASK L-03)."""

import pytest
from smos.models.experiment_run_contract import (
    ALLOWED_EXPERIMENT_STATUSES,
    ALLOWED_TRANSITIONS,
    FORBIDDEN_EXPERIMENT_RUN_KEYS,
    calculate_experiment_run_hash,
    canonical_serialize_experiment_run,
    is_valid_transition,
    normalize_experiment_run,
    validate_experiment_run,
    validate_transition,
)


def test_valid_experiment_run():
    payload = {
        "tool_blueprint_id": "bp_sensor_01",
        "status": "PROPOSED",
        "observation_refs": [1, 2],
        "actual_parameters": {"temp_threshold": 25.5},
        "execution_conditions": {"humidity": 60},
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is True
    assert len(errors) == 0


def test_minimal_experiment_run():
    payload = {
        "tool_blueprint_id": "bp_sim_01",
        "status": "PROPOSED",
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is True
    assert len(errors) == 0


def test_requires_tool_blueprint_id():
    payload = {
        "status": "PROPOSED",
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is False
    assert any("tool_blueprint_id" in err for err in errors)


def test_requires_status():
    payload = {
        "tool_blueprint_id": "bp_01",
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is False
    assert any("status" in err for err in errors)


def test_status_must_be_allowed():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "UNKNOWN_STATUS",
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is False
    assert any("UNKNOWN_STATUS" in err for err in errors)


def test_status_history_list_of_dicts():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "status_history": [
            {"status": "PROPOSED", "at": "2026-10-13T10:00:00Z", "by": "user1", "reason": "init"},
        ],
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is True

    bad_payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "status_history": ["not a dict"],
    }
    is_valid_bad, errors_bad = validate_experiment_run(bad_payload)
    assert is_valid_bad is False


def test_observation_refs_list_of_int():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "observation_refs": [1, 2, 3],
    }
    assert validate_experiment_run(payload)[0] is True

    bad_payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "observation_refs": ["1", "2"],
    }
    assert validate_experiment_run(bad_payload)[0] is False


def test_actual_parameters_dict():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "actual_parameters": {"a": 1},
    }
    assert validate_experiment_run(payload)[0] is True

    bad_payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "actual_parameters": [1, 2],
    }
    assert validate_experiment_run(bad_payload)[0] is False


def test_execution_conditions_dict():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "execution_conditions": {"env": "prod"},
    }
    assert validate_experiment_run(payload)[0] is True

    bad_payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "execution_conditions": "invalid",
    }
    assert validate_experiment_run(bad_payload)[0] is False


def test_no_epistemic_status_field():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "epistemic_status": "OBSERVED",
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is False
    assert any("epistemic_status" in err for err in errors)


def test_no_evidence_field():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "evidence": ["ev_1"],
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is False
    assert any("evidence" in err for err in errors)


def test_no_actual_outcome_field():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "actual_outcome": {"result": "success"},
    }
    is_valid, errors = validate_experiment_run(payload)
    assert is_valid is False
    assert any("actual_outcome" in err for err in errors)


def test_validate_does_not_mutate():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "observation_refs": [1, 2],
    }
    original_copy = dict(payload)
    original_refs = list(payload["observation_refs"])

    validate_experiment_run(payload)

    assert payload == original_copy
    assert payload["observation_refs"] == original_refs


def test_normalize_does_not_promote():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
    }
    normalized = normalize_experiment_run(payload)

    assert "epistemic_status" not in normalized
    assert "evidence" not in normalized
    assert "actual_outcome" not in normalized
    assert normalized["status"] == "PROPOSED"
    assert normalized["observation_refs"] == []


def test_canonical_serialize_sorted_keys():
    payload1 = {
        "status": "PROPOSED",
        "tool_blueprint_id": "bp_01",
        "observation_refs": [2, 1],
        "actual_parameters": {"b": 2, "a": 1},
    }
    payload2 = {
        "actual_parameters": {"a": 1, "b": 2},
        "tool_blueprint_id": "bp_01",
        "observation_refs": [1, 2],
        "status": "PROPOSED",
    }

    serialized1 = canonical_serialize_experiment_run(payload1)
    serialized2 = canonical_serialize_experiment_run(payload2)

    assert serialized1 == serialized2


def test_experiment_run_hash_stable():
    payload = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "observation_refs": [1, 2],
    }
    hash1 = calculate_experiment_run_hash(payload)
    hash2 = calculate_experiment_run_hash(payload)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string length


def test_experiment_run_hash_changes_on_content():
    payload1 = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "observation_refs": [1, 2],
    }
    payload2 = {
        "tool_blueprint_id": "bp_01",
        "status": "PROPOSED",
        "observation_refs": [1, 2, 3],
    }
    hash1 = calculate_experiment_run_hash(payload1)
    hash2 = calculate_experiment_run_hash(payload2)
    assert hash1 != hash2


def test_is_valid_transition_from_proposed_to_approved():
    assert is_valid_transition("PROPOSED", "APPROVED") is True


def test_is_valid_transition_from_proposed_to_cancelled():
    assert is_valid_transition("PROPOSED", "CANCELLED") is True


def test_is_valid_transition_from_proposed_to_executed_rejected():
    assert is_valid_transition("PROPOSED", "EXECUTED") is False


def test_is_valid_transition_from_approved_to_cancelled():
    assert is_valid_transition("APPROVED", "CANCELLED") is True


def test_is_valid_transition_from_completed_to_any_rejected():
    for status in ALLOWED_EXPERIMENT_STATUSES:
        assert is_valid_transition("COMPLETED", status) is False


def test_transition_pure_function():
    run_dict = {"status": "PROPOSED", "tool_blueprint_id": "bp_01"}
    run_copy = dict(run_dict)

    is_valid, errors = validate_transition(run_dict, "APPROVED")
    assert is_valid is True
    assert run_dict == run_copy
