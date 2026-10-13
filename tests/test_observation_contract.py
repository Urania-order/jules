"""Unit tests for Observation Contract in Epistemic Isolation Proxy (EIP)."""

from datetime import datetime

from smos.models.observation_contract import (
    calculate_observation_hash,
    canonical_serialize_observation,
    classify_conflict,
    normalize_observation,
    validate_observation,
)


def test_valid_observation():
    data = {
        "metric_name": "temperature",
        "metric_value": 23.5,
        "metric_unit": "celsius",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is True
    assert errors == []


def test_minimal_observation():
    data = {
        "metric_name": "count",
        "metric_value": 42,
        "observed_at": datetime.now().isoformat(),
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is True
    assert errors == []


def test_observation_requires_metric_name():
    data = {
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("metric_name" in e for e in errors)


def test_observation_requires_metric_value():
    data = {
        "metric_name": "pressure",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("metric_value" in e for e in errors)


def test_observation_requires_observed_at():
    data = {
        "metric_name": "pressure",
        "metric_value": 101.3,
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("observed_at" in e for e in errors)


def test_metric_value_any_json():
    data = {
        "metric_name": "complex_metric",
        "metric_value": {"nested": [1, 2, "three"], "status": True},
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is True


def test_hypothesis_refs_list_of_int():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "hypothesis_refs": [1, 2, "invalid"],
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("hypothesis_refs" in e for e in errors)


def test_prediction_refs_list_of_int():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "prediction_refs": [1, 2],
    }
    is_valid, _ = validate_observation(data)
    assert is_valid is True


def test_assumption_refs_list_of_str():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "assumption_refs": ["sensor_calibrated", 123],
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("assumption_refs" in e for e in errors)


def test_phenomenon_refs_list_of_int():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "phenomenon_refs": [101, 102],
    }
    is_valid, _ = validate_observation(data)
    assert is_valid is True


def test_execution_conditions_dict():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "execution_conditions": "not_a_dict",
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("execution_conditions" in e for e in errors)


def test_epistemic_classification_default():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    normalized = normalize_observation(data)
    assert normalized["epistemic_classification"] == "UNVALIDATED_OBSERVATION"


def test_epistemic_classification_allowed_values():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "epistemic_classification": "INVALID_STATUS",
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("epistemic_classification" in e for e in errors)


def test_correction_requires_reason():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "supersedes_observation_id": 1,
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is False
    assert any("correction_reason" in e for e in errors)


def test_correction_requires_supersedes_id():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "supersedes_observation_id": 1,
        "correction_reason": "Sensor noise adjustment",
    }
    is_valid, errors = validate_observation(data)
    assert is_valid is True


def test_validate_does_not_mutate_input():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    copy_data = dict(data)
    validate_observation(data)
    assert data == copy_data


def test_normalize_does_not_promote():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    normalized = normalize_observation(data)
    assert normalized["epistemic_classification"] == "UNVALIDATED_OBSERVATION"


def test_canonical_serialize_sorted_keys():
    data = {
        "metric_value": 10,
        "metric_name": "temp",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    serialized = canonical_serialize_observation(data)
    assert '"metric_name":"temp"' in serialized
    assert serialized.startswith("{") and serialized.endswith("}")


def test_observation_hash_stable():
    data = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    hash1 = calculate_observation_hash(data)
    hash2 = calculate_observation_hash(data)
    assert hash1 == hash2


def test_observation_hash_changes_on_content():
    data1 = {
        "metric_name": "temp",
        "metric_value": 10,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    data2 = {
        "metric_name": "temp",
        "metric_value": 10.5,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    hash1 = calculate_observation_hash(data1)
    hash2 = calculate_observation_hash(data2)
    assert hash1 != hash2


def test_observation_hash_includes_all_fields():
    data1 = {
        "metric_name": "temp",
        "metric_value": 10,
        "metric_unit": "celsius",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    data2 = {
        "metric_name": "temp",
        "metric_value": 10,
        "metric_unit": "fahrenheit",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    hash1 = calculate_observation_hash(data1)
    hash2 = calculate_observation_hash(data2)
    assert hash1 != hash2


def test_classify_conflict_no_conflict():
    obs1 = {"metric_name": "temp", "metric_value": 10, "observed_at": "2026-10-13T10:00:00"}
    obs2 = {"metric_name": "humidity", "metric_value": 50, "observed_at": "2026-10-13T10:00:00"}
    classification = classify_conflict(obs1, obs2)
    assert classification == "NO_CONFLICT"


def test_classify_conflict_different_values():
    obs1 = {"metric_name": "temp", "metric_value": 10, "observed_at": "2026-10-13T10:00:00"}
    obs2 = {"metric_name": "temp", "metric_value": 15, "observed_at": "2026-10-13T10:00:00"}
    classification = classify_conflict(obs1, obs2)
    assert classification == "CONTRADICTION_SIGNAL"


def test_classify_conflict_same_value_different_time():
    obs1 = {"metric_name": "temp", "metric_value": 10, "observed_at": "2026-10-13T10:00:00"}
    obs2 = {"metric_name": "temp", "metric_value": 10, "observed_at": "2026-10-13T11:00:00"}
    classification = classify_conflict(obs1, obs2)
    assert classification == "POTENTIAL_DUPLICATE"


def test_classify_conflict_is_pure():
    obs1 = {"metric_name": "temp", "metric_value": 10, "observed_at": "2026-10-13T10:00:00"}
    obs2 = {"metric_name": "temp", "metric_value": 15, "observed_at": "2026-10-13T10:00:00"}
    copy1 = dict(obs1)
    copy2 = dict(obs2)
    classify_conflict(obs1, obs2)
    assert obs1 == copy1
    assert obs2 == copy2
