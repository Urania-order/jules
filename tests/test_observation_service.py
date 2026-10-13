"""Unit tests for Observation Service in Epistemic Isolation Proxy (EIP)."""

import pytest

from smos.models.experience import RecipeExecution
from smos.models.observation import Observation
from smos.services.observation_service import ObservationService


def test_ingest_valid(db):
    service = ObservationService(db)
    data = {
        "metric_name": "temperature",
        "metric_value": 23.5,
        "metric_unit": "celsius",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    obs = service.ingest(data)
    assert obs is not None
    assert obs.id is not None
    assert obs.metric_name == "temperature"
    assert obs.metric_value == 23.5
    assert obs.epistemic_classification == "UNVALIDATED_OBSERVATION"


def test_ingest_invalid_rejected(db):
    service = ObservationService(db)
    data = {
        "metric_value": 23.5,
    }
    obs = service.ingest(data)
    assert obs is None


def test_ingest_computes_payload_hash(db):
    service = ObservationService(db)
    data = {
        "metric_name": "voltage",
        "metric_value": 12.0,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    obs = service.ingest(data)
    assert obs is not None
    assert obs.payload_hash is not None
    assert len(obs.payload_hash) == 64  # SHA256 length


def test_ingest_does_not_auto_classify(db):
    service = ObservationService(db)
    data = {
        "metric_name": "voltage",
        "metric_value": 12.0,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    obs = service.ingest(data)
    assert obs.epistemic_classification == "UNVALIDATED_OBSERVATION"


def test_get_by_id(db):
    service = ObservationService(db)
    data = {
        "metric_name": "voltage",
        "metric_value": 12.0,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    created = service.ingest(data)
    fetched = service.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_list_for_tool(db):
    service = ObservationService(db)
    data1 = {
        "metric_name": "m1",
        "metric_value": 1,
        "tool_blueprint_id": "tool-alpha",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    data2 = {
        "metric_name": "m2",
        "metric_value": 2,
        "tool_blueprint_id": "tool-beta",
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    service.ingest(data1)
    service.ingest(data2)

    alpha_list = service.list_for_tool("tool-alpha")
    assert len(alpha_list) == 1
    assert alpha_list[0].metric_name == "m1"


def test_list_for_hypothesis(db):
    service = ObservationService(db)
    data1 = {
        "metric_name": "m1",
        "metric_value": 1,
        "hypothesis_refs": [10, 20],
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    data2 = {
        "metric_name": "m2",
        "metric_value": 2,
        "hypothesis_refs": [30],
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    service.ingest(data1)
    service.ingest(data2)

    h10_list = service.list_for_hypothesis(10)
    assert len(h10_list) == 1
    assert h10_list[0].metric_name == "m1"


def test_list_for_execution(db):
    execution = RecipeExecution(result="SUCCESS")
    db.add(execution)
    db.commit()
    db.refresh(execution)

    service = ObservationService(db)
    data = {
        "metric_name": "m1",
        "metric_value": 1,
        "execution_id": execution.id,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    service.ingest(data)

    exec_list = service.list_for_execution(execution.id)
    assert len(exec_list) == 1
    assert exec_list[0].execution_id == execution.id


def test_find_duplicates_by_hash(db):
    service = ObservationService(db)
    data1 = {
        "metric_name": "m1",
        "metric_value": 1,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    data2 = {
        "metric_name": "m1",
        "metric_value": 1,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    obs1 = service.ingest(data1)
    obs2 = service.ingest(data2)

    duplicates = service.find_duplicates(obs1.payload_hash)
    assert len(duplicates) == 2
    assert {obs.id for obs in duplicates} == {obs1.id, obs2.id}


def test_ingest_correction_creates_new_record(db):
    service = ObservationService(db)
    original_data = {
        "metric_name": "temp",
        "metric_value": 100,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    original = service.ingest(original_data)

    corrected_data = {
        "metric_name": "temp",
        "metric_value": 98.6,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    correction = service.ingest_correction(
        original.id,
        corrected_data,
        reason="Calibrated sensor bias",
    )

    assert correction is not None
    assert correction.id != original.id
    assert correction.supersedes_observation_id == original.id
    assert correction.correction_reason == "Calibrated sensor bias"
    assert correction.epistemic_classification == "OBSERVATION_CORRECTED"


def test_correction_preserves_original(db):
    service = ObservationService(db)
    original_data = {
        "metric_name": "temp",
        "metric_value": 100,
        "observed_at": "2026-10-13T10:00:00+00:00",
    }
    original = service.ingest(original_data)
    orig_id = original.id

    service.ingest_correction(
        orig_id,
        {"metric_name": "temp", "metric_value": 98.6, "observed_at": "2026-10-13T10:00:00+00:00"},
        reason="Sensor calibration",
    )

    fetched_orig = service.get(orig_id)
    assert fetched_orig.metric_value == 100
    assert fetched_orig.supersedes_observation_id is None
    assert fetched_orig.epistemic_classification == "UNVALIDATED_OBSERVATION"


def test_correction_requires_reason(db):
    service = ObservationService(db)
    original = service.ingest({
        "metric_name": "temp",
        "metric_value": 100,
        "observed_at": "2026-10-13T10:00:00+00:00",
    })

    correction = service.ingest_correction(
        original.id,
        {"metric_name": "temp", "metric_value": 98.6, "observed_at": "2026-10-13T10:00:00+00:00"},
        reason=" ",  # Invalid empty/whitespace reason
    )
    assert correction is None


def test_no_update_method():
    service_methods = dir(ObservationService)
    assert "update" not in service_methods
    assert "update_observation" not in service_methods


def test_no_delete_method():
    service_methods = dir(ObservationService)
    assert "delete" not in service_methods
    assert "delete_observation" not in service_methods


def test_no_auto_promotion(db):
    service = ObservationService(db)
    data = {
        "metric_name": "vital_stat",
        "metric_value": 99,
        "observed_at": "2026-10-13T10:00:00+00:00",
        "provenance": {"confidence": 0.99, "verified": True},
    }
    obs = service.ingest(data)
    assert obs.epistemic_classification == "UNVALIDATED_OBSERVATION"


def test_list_conflicts_does_not_resolve(db):
    service = ObservationService(db)
    obs1 = service.ingest({
        "metric_name": "speed",
        "metric_value": 100,
        "observed_at": "2026-10-13T10:00:00+00:00",
    })
    obs2 = service.ingest({
        "metric_name": "speed",
        "metric_value": 120,
        "observed_at": "2026-10-13T10:00:00+00:00",
    })

    conflicts = service.list_conflicts_for_metric("speed")
    assert len(conflicts) == 1
    pair1, pair2 = conflicts[0]
    assert pair1.id == obs1.id
    assert pair2.id == obs2.id

    # Check database records remain unresolved and unmutated
    fetched1 = service.get(obs1.id)
    fetched2 = service.get(obs2.id)
    assert fetched1.epistemic_classification == "UNVALIDATED_OBSERVATION"
    assert fetched2.epistemic_classification == "UNVALIDATED_OBSERVATION"


def test_list_conflicts_does_not_auto_mark(db):
    service = ObservationService(db)
    service.ingest({
        "metric_name": "pressure",
        "metric_value": 50,
        "observed_at": "2026-10-13T10:00:00+00:00",
    })
    service.ingest({
        "metric_name": "pressure",
        "metric_value": 75,
        "observed_at": "2026-10-13T10:00:00+00:00",
    })

    service.list_conflicts_for_metric("pressure")

    all_pressure = (
        db.query(Observation)
        .filter(Observation.metric_name == "pressure")
        .all()
    )
    for obs in all_pressure:
        assert obs.epistemic_classification == "UNVALIDATED_OBSERVATION"
