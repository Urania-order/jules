"""Contract tests for Controlled Experiment Execution Contract (TASK L-04)."""

import pytest

from smos.models.experiment_execution_contract import (
    EXECUTION_STATUS_FAILED,
    EXECUTION_STATUS_SUCCEEDED,
    calculate_execution_result_hash,
    canonical_serialize_execution_result,
    normalize_execution_result,
    validate_execution_request,
    validate_execution_result,
    validate_parameters_against_blueprint,
)


@pytest.fixture
def sample_blueprint():
    return {
        "blueprint_id": "test_blueprint_v1",
        "version": "1.0.0",
        "specification": {
            "title": "Test Sensor Tool",
            "description": "Measures sensor output",
            "tool_type": "DATA_COLLECTION",
            "parameters": [
                {
                    "name": "temperature",
                    "type": "float",
                    "required": True,
                    "min": -50.0,
                    "max": 100.0,
                },
                {
                    "name": "sample_count",
                    "type": "int",
                    "required": False,
                    "default": 10,
                    "min": 1,
                    "max": 100,
                },
                {
                    "name": "mode",
                    "type": "enum",
                    "required": False,
                    "default": "FAST",
                    "allowed_values": ["FAST", "ACCURATE"],
                },
            ],
            "expected_outputs": [
                {
                    "name": "reading",
                    "type": "float",
                    "unit": "celsius",
                }
            ],
        },
    }


def test_validate_execution_request_valid():
    req = {
        "experiment_run_id": 123,
        "parameters": {"temperature": 25.5},
        "executed_by": "operator_1",
        "execution_conditions": {"env": "lab"},
        "idempotency_key": "key-999",
    }
    valid, errors = validate_execution_request(req)
    assert valid is True
    assert len(errors) == 0


def test_validate_execution_request_forbidden_keys():
    req = {
        "experiment_run_id": 123,
        "epistemic_status": "PROMOTED",
    }
    valid, errors = validate_execution_request(req)
    assert valid is False
    assert any("Forbidden key" in e for e in errors)


def test_validate_execution_request_invalid_id():
    req = {
        "experiment_run_id": True,
    }
    valid, errors = validate_execution_request(req)
    assert valid is False
    assert any("experiment_run_id" in e for e in errors)


def test_validate_parameters_against_blueprint_valid(sample_blueprint):
    params = {
        "temperature": 22.0,
        "sample_count": 50,
        "mode": "ACCURATE",
    }
    valid, errors = validate_parameters_against_blueprint(params, sample_blueprint)
    assert valid is True
    assert len(errors) == 0


def test_validate_parameters_against_blueprint_missing_required(sample_blueprint):
    params = {
        "sample_count": 10,
    }
    valid, errors = validate_parameters_against_blueprint(params, sample_blueprint)
    assert valid is False
    assert any("Missing required parameter 'temperature'" in e for e in errors)


def test_validate_parameters_against_blueprint_out_of_bounds(sample_blueprint):
    params = {
        "temperature": 150.0,  # max is 100.0
    }
    valid, errors = validate_parameters_against_blueprint(params, sample_blueprint)
    assert valid is False
    assert any("above maximum" in e for e in errors)


def test_validate_parameters_against_blueprint_unknown_param(sample_blueprint):
    params = {
        "temperature": 20.0,
        "unknown_setting": "abc",
    }
    valid, errors = validate_parameters_against_blueprint(params, sample_blueprint)
    assert valid is False
    assert any("not defined in blueprint" in e for e in errors)


def test_validate_execution_result_valid():
    res = {
        "experiment_run_id": 456,
        "executor_id": "test_executor",
        "status": EXECUTION_STATUS_SUCCEEDED,
        "started_at": "2026-10-13T20:00:00Z",
        "finished_at": "2026-10-13T20:01:00Z",
        "measurements": [
            {
                "metric_name": "temp_sensor_1",
                "metric_value": 24.2,
                "metric_unit": "celsius",
            }
        ],
        "observation_refs": [1, 2],
        "partial_persistence": False,
    }
    valid, errors = validate_execution_result(res)
    assert valid is True
    assert len(errors) == 0


def test_validate_execution_result_forbidden_keys():
    res = {
        "experiment_run_id": 456,
        "executor_id": "test_executor",
        "status": EXECUTION_STATUS_SUCCEEDED,
        "evidence": "verified_truth",
    }
    valid, errors = validate_execution_result(res)
    assert valid is False
    assert any("Forbidden epistemic key" in e for e in errors)


def test_canonical_serialization_and_hash_stability():
    res1 = {
        "experiment_run_id": 1,
        "executor_id": "exec_a",
        "status": EXECUTION_STATUS_SUCCEEDED,
        "observation_refs": [2, 1],
        "measurements": [{"metric_name": "m1", "metric_value": 10}],
    }
    res2 = {
        "executor_id": "exec_a",
        "experiment_run_id": 1,
        "measurements": [{"metric_name": "m1", "metric_value": 10}],
        "observation_refs": [1, 2],
        "status": EXECUTION_STATUS_SUCCEEDED,
    }

    hash1 = calculate_execution_result_hash(res1)
    hash2 = calculate_execution_result_hash(res2)
    assert hash1 == hash2

    # Change value -> hash changes
    res3 = dict(res1, status=EXECUTION_STATUS_FAILED)
    assert calculate_execution_result_hash(res3) != hash1


def test_validation_does_not_mutate_input():
    original = {
        "experiment_run_id": 10,
        "parameters": {"temp": 20},
    }
    copied = dict(original)
    validate_execution_request(original)
    assert original == copied
