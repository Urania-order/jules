"""Tests for ExperimentRun service (TASK L-03)."""

import pytest
from smos.models.experiment_run import ExperimentRun, ExperimentRunStatus
from smos.services.experiment_run_service import ExperimentRunService


def test_propose_creates_run_with_status_proposed(db):
    service = ExperimentRunService(db)
    payload = {
        "tool_blueprint_id": "bp_sensor_10",
        "blueprint_version": "1.0.0",
        "actual_parameters": {"freq": 100},
    }
    run = service.propose(payload, created_by="operator_01")

    assert run is not None
    assert run.id is not None
    assert run.status == ExperimentRunStatus.PROPOSED.value
    assert run.tool_blueprint_id == "bp_sensor_10"
    assert run.blueprint_version == "1.0.0"
    assert run.created_by == "operator_01"
    assert run.proposed_at is not None


def test_propose_computes_status_history_entry(db):
    service = ExperimentRunService(db)
    payload = {
        "tool_blueprint_id": "bp_sensor_10",
        "proposal_reason": "Testing sensor calibration",
    }
    run = service.propose(payload, created_by="operator_01")

    assert len(run.status_history) == 1
    entry = run.status_history[0]
    assert entry["status"] == "PROPOSED"
    assert entry["by"] == "operator_01"
    assert entry["reason"] == "Testing sensor calibration"
    assert "at" in entry


def test_approve_transitions_to_approved(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")

    approved_run = service.approve(run.id, approved_by="admin_01", reason="Pre-flight checks passed")

    assert approved_run is not None
    assert approved_run.status == ExperimentRunStatus.APPROVED.value
    assert approved_run.approved_by == "admin_01"
    assert approved_run.approved_at is not None


def test_approve_appends_status_history(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01", reason="Approved")

    updated_run = service.get(run.id)
    assert len(updated_run.status_history) == 2
    assert updated_run.status_history[0]["status"] == "PROPOSED"
    assert updated_run.status_history[1]["status"] == "APPROVED"
    assert updated_run.status_history[1]["by"] == "admin_01"


def test_approve_from_invalid_status_rejected(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id)

    # Attempt approve when status is EXECUTED
    res = service.approve(run.id, approved_by="admin_02")
    assert res is None

    current = service.get(run.id)
    assert current.status == ExperimentRunStatus.EXECUTED.value


def test_execute_transitions_to_executed(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")

    executed_run = service.execute(
        run.id,
        actual_parameters={"speed": 50},
        execution_conditions={"temp": 20},
        executed_by="runner_01",
    )

    assert executed_run is not None
    assert executed_run.status == ExperimentRunStatus.EXECUTED.value
    assert executed_run.executed_at is not None
    assert executed_run.actual_parameters["speed"] == 50
    assert executed_run.execution_conditions["temp"] == 20


def test_execute_from_invalid_status_rejected(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")

    # PROPOSED directly to EXECUTED is forbidden
    res = service.execute(run.id)
    assert res is None

    current = service.get(run.id)
    assert current.status == ExperimentRunStatus.PROPOSED.value


def test_execute_records_actual_parameters(db):
    service = ExperimentRunService(db)
    run = service.propose(
        {"tool_blueprint_id": "bp_01", "actual_parameters": {"initial": True}},
        created_by="user1",
    )
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id, actual_parameters={"runtime_override": 42})

    updated = service.get(run.id)
    assert updated.actual_parameters["initial"] is True
    assert updated.actual_parameters["runtime_override"] == 42


def test_complete_transitions_to_completed(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id)

    completed_run = service.complete(run.id, completed_by="runner_01")

    assert completed_run is not None
    assert completed_run.status == ExperimentRunStatus.COMPLETED.value
    assert completed_run.completed_at is not None


def test_complete_links_observation_refs(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01", "observation_refs": [10]}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id)

    completed = service.complete(run.id, observation_refs=[20, 30])

    assert completed.observation_refs == [10, 20, 30]


def test_complete_from_invalid_status_rejected(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")

    # APPROVED directly to COMPLETED is forbidden
    res = service.complete(run.id)
    assert res is None

    current = service.get(run.id)
    assert current.status == ExperimentRunStatus.APPROVED.value


def test_fail_transitions_to_failed(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id)

    failed_run = service.fail(run.id, reason="Timeout during execution", failed_by="runner_01")

    assert failed_run is not None
    assert failed_run.status == ExperimentRunStatus.FAILED.value
    assert failed_run.status_history[-1]["reason"] == "Timeout during execution"


def test_cancel_from_proposed(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")

    cancelled = service.cancel(run.id, reason="Budget exceeded", cancelled_by="user1")

    assert cancelled is not None
    assert cancelled.status == ExperimentRunStatus.CANCELLED.value


def test_cancel_from_approved(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")

    cancelled = service.cancel(run.id, reason="No longer needed", cancelled_by="admin_01")

    assert cancelled is not None
    assert cancelled.status == ExperimentRunStatus.CANCELLED.value


def test_cancel_from_executed_rejected(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id)

    res = service.cancel(run.id, reason="Cancel in progress")
    assert res is None

    current = service.get(run.id)
    assert current.status == ExperimentRunStatus.EXECUTED.value


def test_complete_does_not_evaluate(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id)
    completed = service.complete(run.id, observation_refs=[101])

    d = completed.to_dict()
    assert "evaluation" not in d
    assert "epistemic_status" not in d
    assert "actual_outcome" not in d


def test_execute_does_not_run_experiment(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    executed = service.execute(run.id)

    # Executing merely updates the lifecycle state, without side-effects or external process calls
    assert executed.status == ExperimentRunStatus.EXECUTED.value


def test_no_update_method(db):
    service = ExperimentRunService(db)
    assert not hasattr(service, "update")
    assert not hasattr(service, "update_run")


def test_no_delete_method(db):
    service = ExperimentRunService(db)
    assert not hasattr(service, "delete")
    assert not hasattr(service, "delete_run")


def test_no_auto_promotion(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01")
    service.execute(run.id)
    completed = service.complete(run.id, observation_refs=[1, 2, 3])

    run_dict = completed.to_dict()

    # Observation refs remain raw IDs; no promote calls, no evidence creation
    assert run_dict["observation_refs"] == [1, 2, 3]
    assert "epistemic_status" not in run_dict


def test_get_by_id(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")

    fetched = service.get(run.id)
    assert fetched is not None
    assert fetched.id == run.id

    assert service.get(999999) is None


def test_list_by_status(db):
    service = ExperimentRunService(db)
    run1 = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    run2 = service.propose({"tool_blueprint_id": "bp_02"}, created_by="user1")

    service.approve(run1.id, approved_by="admin_01")

    proposed_list = service.list_by_status("PROPOSED")
    approved_list = service.list_by_status("APPROVED")

    assert len(proposed_list) == 1
    assert proposed_list[0].id == run2.id

    assert len(approved_list) == 1
    assert approved_list[0].id == run1.id


def test_list_by_blueprint(db):
    service = ExperimentRunService(db)
    run1 = service.propose({"tool_blueprint_id": "bp_alpha"}, created_by="user1")
    run2 = service.propose({"tool_blueprint_id": "bp_alpha"}, created_by="user2")
    run3 = service.propose({"tool_blueprint_id": "bp_beta"}, created_by="user1")

    alpha_runs = service.list_by_blueprint("bp_alpha")
    beta_runs = service.list_by_blueprint("bp_beta")

    assert len(alpha_runs) == 2
    assert {r.id for r in alpha_runs} == {run1.id, run2.id}

    assert len(beta_runs) == 1
    assert beta_runs[0].id == run3.id


def test_status_history_append_only(db):
    service = ExperimentRunService(db)
    run = service.propose({"tool_blueprint_id": "bp_01"}, created_by="user1")
    service.approve(run.id, approved_by="admin_01", reason="Approve step")
    service.execute(run.id, executed_by="runner_01")
    service.complete(run.id, observation_refs=[5], completed_by="runner_01")

    final_run = service.get(run.id)
    history = final_run.status_history

    assert len(history) == 4
    statuses = [h["status"] for h in history]
    assert statuses == ["PROPOSED", "APPROVED", "EXECUTED", "COMPLETED"]
