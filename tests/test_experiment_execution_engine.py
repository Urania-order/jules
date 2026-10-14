"""Engine tests for Controlled Experiment Execution Engine (TASK L-04)."""

import pytest
from smos.models.experiment_run import ExperimentRun, ExperimentRunStatus
from smos.models.observation import Observation
from smos.services.experiment_execution_engine import (
    ExecutorRegistry,
    ExperimentExecutionEngine,
)
from smos.services.experiment_run_service import ExperimentRunService
from smos.services.observation_service import ObservationService


@pytest.fixture
def valid_blueprint():
    return {
        "blueprint_id": "sensor_tool_v1",
        "version": "1.0.0",
        "research_context": {
            "research_project_id": "proj_1",
            "phenomenon_id": 100,
            "assumption_refs": ["hyp_1"],
            "prediction_refs": [200],
        },
        "specification": {
            "title": "Sensor Tool Blueprint",
            "description": "Simulated sensor measurement tool",
            "tool_type": "DATA_COLLECTION",
            "parameters": [
                {
                    "name": "voltage",
                    "type": "float",
                    "required": True,
                    "min": 0.0,
                    "max": 12.0,
                },
                {
                    "name": "samples",
                    "type": "int",
                    "required": False,
                    "default": 5,
                },
            ],
            "expected_outputs": [
                {
                    "name": "voltage_reading",
                    "type": "float",
                    "unit": "volts",
                }
            ],
        },
    }


def fake_successful_executor(parameters, context):
    v = parameters.get("voltage", 5.0)
    return {
        "status": "SUCCEEDED",
        "structured_output": {"mean_voltage": v},
        "measurements": [
            {
                "metric_name": "voltage_reading",
                "metric_value": v,
                "metric_unit": "volts",
            }
        ],
    }


def fake_empty_executor(parameters, context):
    return {
        "status": "SUCCEEDED",
        "structured_output": {"note": "No measurements produced"},
        "measurements": [],
    }


def fake_exception_executor(parameters, context):
    raise RuntimeError("Hardware connection failed")


def fake_failing_executor(parameters, context):
    return {
        "status": "FAILED",
        "error_message": "Sensor hardware unresponsive",
    }


def fake_malformed_output_executor(parameters, context):
    return "invalid non-dict output"


# REGISTRY TESTS

def test_registry_register_resolve():
    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_successful_executor)
    assert registry.is_registered("sensor_tool_v1") is True
    assert registry.resolve("sensor_tool_v1") == fake_successful_executor
    assert registry.list_executors() == ["sensor_tool_v1"]


def test_registry_reject_unknown():
    registry = ExecutorRegistry()
    assert registry.resolve("unknown_tool") is None


def test_registry_reject_duplicate():
    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_successful_executor)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("sensor_tool_v1", fake_successful_executor)


def test_registry_unregister():
    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_successful_executor)
    assert registry.unregister("sensor_tool_v1") is True
    assert registry.is_registered("sensor_tool_v1") is False


# ENGINE EXECUTION TESTS

def test_engine_execute_eligible_approved_run(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_successful_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint if bp_id == "sensor_tool_v1" else None,
    )

    request = {
        "experiment_run_id": run.id,
        "parameters": {"voltage": 10.5},
        "executed_by": "operator_a",
    }

    result = engine.execute_run(request)

    assert result["status"] == "SUCCEEDED"
    assert result["experiment_run_id"] == run.id
    assert result["executor_id"] == "sensor_tool_v1"
    assert len(result["observation_refs"]) == 1

    # Verify run updated to COMPLETED
    updated_run = run_service.get(run.id)
    assert updated_run.status == ExperimentRunStatus.COMPLETED.value
    assert len(updated_run.observation_refs) == 1
    assert updated_run.observation_refs == result["observation_refs"]

    # Verify Observation in DB
    obs_id = result["observation_refs"][0]
    obs = db.query(Observation).filter(Observation.id == obs_id).first()
    assert obs is not None
    assert obs.metric_name == "voltage_reading"
    assert obs.metric_value == 10.5
    # NOTE 2 verification: experiment_run_id is String reference str(run.id)
    assert obs.experiment_run_id == str(run.id)
    assert obs.prediction_refs == [200]
    assert obs.phenomenon_refs == [100]


def test_engine_execute_empty_measurements(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_empty_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 5.0}})

    assert result["status"] == "SUCCEEDED"
    assert result["observation_refs"] == []

    updated_run = run_service.get(run.id)
    assert updated_run.status == ExperimentRunStatus.COMPLETED.value


def test_engine_reject_proposed_run(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_successful_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 5.0}})

    assert result["status"] == "FAILED"
    assert "ineligible status 'PROPOSED'" in result["error_message"]

    # Run remains PROPOSED
    assert run_service.get(run.id).status == ExperimentRunStatus.PROPOSED.value


def test_engine_reject_unknown_executor(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    registry = ExecutorRegistry()  # Empty registry

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 5.0}})

    assert result["status"] == "FAILED"
    assert "No executor registered" in result["error_message"]


def test_engine_reject_invalid_parameters(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_successful_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    # voltage exceeds max 12.0
    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 50.0}})

    assert result["status"] == "FAILED"
    assert "above maximum 12.0" in result["error_message"]
    assert run_service.get(run.id).status == ExperimentRunStatus.APPROVED.value


def test_engine_failure_path_executor_exception(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_exception_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 5.0}})

    assert result["status"] == "FAILED"
    assert "Hardware connection failed" in result["error_message"]

    # Verify run transitioned to FAILED and status_history recorded it
    updated_run = run_service.get(run.id)
    assert updated_run.status == ExperimentRunStatus.FAILED.value
    assert any(h["status"] == "FAILED" for h in updated_run.status_history)

    # Verify NO observation created
    obs_count = db.query(Observation).filter(Observation.experiment_run_id == str(run.id)).count()
    assert obs_count == 0


def test_engine_failure_path_executor_returns_error(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_failing_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 5.0}})

    assert result["status"] == "FAILED"
    assert "Sensor hardware unresponsive" in result["error_message"]
    assert run_service.get(run.id).status == ExperimentRunStatus.FAILED.value


def test_engine_failure_path_partial_observation_ingestion(db, valid_blueprint, monkeypatch):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    def multi_meas_executor(parameters, context):
        return {
            "status": "SUCCEEDED",
            "measurements": [
                {"metric_name": "m1", "metric_value": 1.0},
                {"metric_name": "m2", "metric_value": None},  # invalid metric_value -> causes ingest failure
            ],
        }

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", multi_meas_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 5.0}})

    assert result["status"] == "FAILED"
    assert len(result["observation_refs"]) == 1
    assert result["partial_persistence"] is True
    assert "Observation ingestion failed" in result["error_message"]

    # Verify run state is EXECUTED (not completed)
    updated_run = run_service.get(run.id)
    assert updated_run.status == ExperimentRunStatus.EXECUTED.value


def test_no_epistemic_promotion_or_evaluation(db, valid_blueprint):
    run_service = ExperimentRunService(db)
    run = run_service.propose({"tool_blueprint_id": "sensor_tool_v1"})
    run_service.approve(run.id, approved_by="operator_a")

    registry = ExecutorRegistry()
    registry.register("sensor_tool_v1", fake_successful_executor)

    engine = ExperimentExecutionEngine(
        db,
        registry=registry,
        blueprint_provider=lambda bp_id: valid_blueprint,
    )

    result = engine.execute_run({"experiment_run_id": run.id, "parameters": {"voltage": 5.0}})

    assert "epistemic_status" not in result
    assert "evidence" not in result
    assert "actual_outcome" not in result

    obs = db.query(Observation).filter(Observation.id == result["observation_refs"][0]).first()
    assert obs.epistemic_classification == "UNVALIDATED_OBSERVATION"
