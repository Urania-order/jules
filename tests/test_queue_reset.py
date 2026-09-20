import pytest
import os
import json
from pathlib import Path
from fastapi.testclient import TestClient
from smos.api.main import app
from smos.core.queue import QueueManager
from smos.core.task import Task, TaskStatus

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer dev-operator-token"}


@pytest.fixture
def queue_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
    qm = QueueManager(queue_dir=tmp_path / ".jules" / "queue")
    return qm, tmp_path


def test_queue_reset(queue_env):
    qm, tmp_path = queue_env

    # Create pending, running, completed tasks
    task_p = Task(id="task-p1", request="Pending task", status=TaskStatus.PENDING)
    task_r = Task(id="task-r1", request="Running task", status=TaskStatus.RUNNING)
    task_c = Task(id="task-c1", request="Completed task", status=TaskStatus.COMPLETED)

    qm.save_task(task_p)
    qm.save_task(task_r)
    qm.save_task(task_c)

    # Call reset for scope="pending"
    res1 = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "success"
    assert data1["moved"] == 1
    assert data1["cleared"]["pending"] == 1

    # Pending task is preserved in history (ERRATA-0027)
    assert qm.get_task("task-p1") is not None

    # Call reset for scope="all"
    res2 = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "success"
    assert data2["moved"] == 3
    assert data2["cleared"]["pending"] == 1
    assert data2["cleared"]["running"] == 1
    assert data2["cleared"]["completed"] == 1

    # All task IDs still present in history
    assert qm.get_task("task-p1") is not None
    assert qm.get_task("task-r1") is not None
    assert qm.get_task("task-c1") is not None


def test_queue_reset_requires_confirm(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-p2", request="Pending task", status=TaskStatus.PENDING)
    qm.save_task(task_p)

    # Missing or incorrect confirm string
    res = client.post("/api/queue/reset", json={"confirm": "NO", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 400
    data = res.json()
    assert data["status"] == "error"
    assert data["code"] == "INVALID_CONFIRMATION"

    # Pending task still in queue
    assert qm.get_task("task-p2") is not None


def test_queue_reset_archives_to_jsonl(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-jsonl-1", request="Archive test task", status=TaskStatus.READY, priority=4)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "ready"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    assert len(lines) == 1
    assert lines[0]["task_id"] == "task-jsonl-1"
    assert lines[0]["status"] in ("ready", "pending")
    assert lines[0]["request"] == "Archive test task"
    assert lines[0]["priority"] == 4
    assert "reset_at" in lines[0]
    assert lines[0]["restored"] is False


def test_queue_reset_writes_history_md(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-md-1", request="History md task", status=TaskStatus.RUNNING)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    history_dir = tmp_path / ".jules" / "history"
    md_files = list(history_dir.glob("reset-*.md"))
    assert len(md_files) == 1

    content = md_files[0].read_text()
    assert "# Queue Reset Report" in content
    assert "running" in content
    assert "task-md-1" in content


def test_queue_reset_preserves_why_block(queue_env):
    qm, tmp_path = queue_env
    task = Task(
        id="task-why-1",
        request="Task with why",
        status=TaskStatus.PENDING,
        source_task="src-task-99",
        proposed_by="operator"
    )
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    why = lines[0]["why"]
    assert why["source_task"] == "src-task-99"
    assert why["proposed_by"] == "operator"
    assert isinstance(why["history_transitions"], list)


def test_queue_reset_why_uses_existing_data_not_fabricated(queue_env):
    qm, tmp_path = queue_env
    # Task without source_task or proposed_by
    task = Task(id="task-no-why", request="Task without why", status=TaskStatus.PENDING)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    why = lines[0]["why"]
    assert why["source_task"] is None
    assert why["proposal_origin"] is None
    assert why["proposed_by"] in (None, "unknown")


def test_queue_reset_column_ready(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-col-ready", request="Ready col task", status=TaskStatus.READY)
    task_r = Task(id="task-col-running-keep", request="Running keep", status=TaskStatus.RUNNING)
    qm.save_task(task_p)
    qm.save_task(task_r)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "ready"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    # Task preserved in history (ERRATA-0027)
    assert qm.get_task("task-col-ready") is not None
    assert qm.get_task("task-col-running-keep").status == TaskStatus.RUNNING


def test_queue_reset_column_running(queue_env):
    qm, tmp_path = queue_env
    task_r = Task(id="task-col-run", request="Running col task", status=TaskStatus.RUNNING)
    qm.save_task(task_r)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    # Task preserved in history (ERRATA-0027)
    assert qm.get_task("task-col-run") is not None


def test_queue_reset_column_completed(queue_env):
    qm, tmp_path = queue_env
    task_c = Task(id="task-col-comp", request="Completed col task", status=TaskStatus.COMPLETED)
    qm.save_task(task_c)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "completed"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 1

    # Completed task cleared from archive/queue reset scope
    jsonl_files = list((tmp_path / ".jules" / "queue").glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1


def test_queue_reset_all(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-all-1", request="Pending all", status=TaskStatus.PENDING)
    task_r = Task(id="task-all-2", request="Running all", status=TaskStatus.RUNNING)
    task_c = Task(id="task-all-3", request="Completed all", status=TaskStatus.COMPLETED)
    qm.save_task(task_p)
    qm.save_task(task_r)
    qm.save_task(task_c)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["moved"] == 3


def test_reset_all_removes_from_state_json(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-s1", request="Pending task 1", status=TaskStatus.PENDING)
    task_r = Task(id="task-s2", request="Running task 2", status=TaskStatus.RUNNING)
    qm.save_task(task_p)
    qm.save_task(task_r)

    state_file = tmp_path / ".co-smos" / "state.json"
    assert state_file.exists()

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["moved"] == 2

    state_data = json.loads(state_file.read_text())
    assert state_data.get("active_task") is None
    # History preserved: task-s1, task-s2, and reset event
    history = state_data.get("history", [])
    assert len(history) == 3
    assert any(item.get("action") == "reset" for item in history if isinstance(item, dict))


def test_reset_completed_removes_deferred_and_cancelled(queue_env):
    qm, tmp_path = queue_env
    t_comp = Task(id="task-comp", request="Completed task", status=TaskStatus.COMPLETED)
    t_fail = Task(id="task-fail", request="Failed task", status=TaskStatus.FAILED)
    t_canc = Task(id="task-canc", request="Cancelled task", status=TaskStatus.CANCELLED)
    t_def = Task(id="task-def", request="Deferred task", status=TaskStatus.DEFERRED)
    t_pend = Task(id="task-pend", request="Pending task", status=TaskStatus.PENDING)

    qm.save_task(t_comp)
    qm.save_task(t_fail)
    qm.save_task(t_canc)
    qm.save_task(t_def)
    qm.save_task(t_pend)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "completed"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["moved"] == 3

    assert "task-pend" in [t.id for t in qm.list_queue_tasks()]


def test_reset_archives_to_jsonl(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-arch-1", request="Archiving test", status=TaskStatus.PENDING, priority=3)
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "pending"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    assert len(lines) == 1
    assert lines[0]["task_id"] == "task-arch-1"
    assert lines[0]["status"] == "pending"
    assert lines[0]["request"] == "Archiving test"
    assert lines[0]["priority"] == 3
    assert lines[0]["restored"] is False


def test_reset_preserves_why_from_state(queue_env):
    qm, tmp_path = queue_env
    task = Task(
        id="task-why-state",
        request="State why task",
        status=TaskStatus.RUNNING,
        source_task="src-task-100",
        proposed_by="admin",
        metadata={"proposal_origin": "origin-abc"}
    )
    qm.save_task(task)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    jsonl_files = list(queue_dir.glob("reset-*.jsonl"))
    assert len(jsonl_files) == 1

    lines = [json.loads(line) for line in jsonl_files[0].read_text().strip().split("\n") if line]
    why = lines[0]["why"]
    assert why["source_task"] == "src-task-100"
    assert why["proposed_by"] == "admin"
    assert why["proposal_origin"] == "origin-abc"


def test_reset_updates_state_json(queue_env):
    qm, tmp_path = queue_env
    task_r = Task(id="task-running-st", request="Running in state", status=TaskStatus.RUNNING)
    qm.save_task(task_r)

    state_file = tmp_path / ".co-smos" / "state.json"
    state_before = json.loads(state_file.read_text())
    assert state_before.get("active_task") is not None

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    state_after = json.loads(state_file.read_text())
    assert state_after.get("active_task") is None
    assert state_after.get("status") in ("idle", "online")


def test_reset_no_files_in_queue_dir(queue_env):
    qm, tmp_path = queue_env
    task_p = Task(id="task-nf-1", request="No files pending", status=TaskStatus.PENDING)
    task_r = Task(id="task-nf-2", request="No files running", status=TaskStatus.RUNNING)
    qm.save_task(task_p)
    qm.save_task(task_r)

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    queue_dir = tmp_path / ".jules" / "queue"
    for folder_name in ["pending", "running", "completed", "deferred"]:
        folder = queue_dir / folder_name
        json_files = list(folder.glob("*.json"))
        assert len(json_files) == 0, f"Found unexpected task json files in {folder_name}: {json_files}"


def test_archive_export_csv(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-exp-csv", request="Export CSV Task", status=TaskStatus.READY, priority=2)
    qm.save_task(task)

    client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "ready"}, headers=AUTH_HEADERS)

    res = client.get("/api/queue/archive/export?format=csv", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment; filename=\"reset-archive-" in res.headers["content-disposition"]
    assert ".csv\"" in res.headers["content-disposition"]

    content = res.text
    assert "task_id,status,request,priority,created_at,reset_at,scope,restored" in content
    assert "task-exp-csv" in content
    assert "Export CSV Task" in content


def test_archive_export_md(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-exp-md", request="Export MD Task", status=TaskStatus.RUNNING, source_task="src-10")
    qm.save_task(task)

    client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)

    res = client.get("/api/queue/archive/export?format=md", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert "text/markdown" in res.headers["content-type"]
    assert "attachment; filename=\"reset-archive-" in res.headers["content-disposition"]
    assert ".md\"" in res.headers["content-disposition"]

    content = res.text
    assert "# Queue Archive — Export" in content
    assert "## task-exp-md" in content
    assert "Export MD Task" in content
    assert "source_task: src-10" in content


def test_archive_export_jsonl(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-exp-jsonl", request="Export JSONL Task", status=TaskStatus.COMPLETED)
    qm.save_task(task)

    client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "completed"}, headers=AUTH_HEADERS)

    res = client.get("/api/queue/archive/export?format=jsonl", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert "attachment; filename=\"reset-archive-" in res.headers["content-disposition"]
    assert ".jsonl\"" in res.headers["content-disposition"]

    lines = [json.loads(line) for line in res.text.strip().split("\n") if line]
    assert len(lines) == 1
    assert lines[0]["task_id"] == "task-exp-jsonl"


def test_archive_export_empty(queue_env):
    qm, tmp_path = queue_env
    res = client.get("/api/queue/archive/export?format=csv", headers=AUTH_HEADERS)
    assert res.status_code == 404
    data = res.json()
    assert data["code"] == "ARCHIVE_EMPTY"


def test_archive_export_invalid_format(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-inv-fmt", request="Test Task", status=TaskStatus.READY)
    qm.save_task(task)
    client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "ready"}, headers=AUTH_HEADERS)

    res = client.get("/api/queue/archive/export?format=xml", headers=AUTH_HEADERS)
    assert res.status_code == 400
    data = res.json()
    assert data["code"] == "INVALID_FORMAT"


def test_archive_export_requires_operator(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-auth", request="Auth Test Task", status=TaskStatus.READY)
    qm.save_task(task)
    client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "ready"}, headers=AUTH_HEADERS)

    consultant_headers = {"Authorization": "Bearer dev-consultant-token"}
    res = client.get("/api/queue/archive/export?format=jsonl", headers=consultant_headers)
    assert res.status_code == 403


def test_archive_export_scope_filter(queue_env):
    qm, tmp_path = queue_env
    t_ready = Task(id="task-s-ready", request="Ready task", status=TaskStatus.READY)
    t_running = Task(id="task-s-run", request="Running task", status=TaskStatus.RUNNING)
    qm.save_task(t_ready)
    qm.save_task(t_running)

    client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "ready"}, headers=AUTH_HEADERS)
    client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "running"}, headers=AUTH_HEADERS)

    res = client.get("/api/queue/archive/export?format=jsonl&scope=ready", headers=AUTH_HEADERS)
    assert res.status_code == 200
    lines = [json.loads(line) for line in res.text.strip().split("\n") if line]
    assert len(lines) == 1
    assert lines[0]["task_id"] == "task-s-ready"


def test_schedule_crud(queue_env):
    _, tmp_path = queue_env

    # 1. Create schedule
    payload = {
        "name": "Nightly Reset",
        "cron": "0 2 * * *",
        "scope": "completed",
        "enabled": True
    }
    res = client.post("/api/queue/reset/schedules", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    sched = res.json()
    assert sched["name"] == "Nightly Reset"
    assert sched["cron"] == "0 2 * * *"
    assert sched["scope"] == "completed"
    assert sched["enabled"] is True
    sched_id = sched["id"]

    # 2. List schedules
    res_list = client.get("/api/queue/reset/schedules", headers=AUTH_HEADERS)
    assert res_list.status_code == 200
    schedules = res_list.json()
    assert len(schedules) == 1
    assert schedules[0]["id"] == sched_id

    # 3. Patch schedule
    patch_payload = {
        "name": "Updated Schedule",
        "cron": "30 3 * * 1-5",
        "enabled": False
    }
    res_patch = client.patch(f"/api/queue/reset/schedules/{sched_id}", json=patch_payload, headers=AUTH_HEADERS)
    assert res_patch.status_code == 200
    updated = res_patch.json()
    assert updated["name"] == "Updated Schedule"
    assert updated["cron"] == "30 3 * * 1-5"
    assert updated["enabled"] is False

    # 4. Delete schedule
    res_del = client.delete(f"/api/queue/reset/schedules/{sched_id}", headers=AUTH_HEADERS)
    assert res_del.status_code == 200

    res_list_after = client.get("/api/queue/reset/schedules", headers=AUTH_HEADERS)
    assert len(res_list_after.json()) == 0


def test_schedule_crud_auth_and_validation(queue_env):
    consultant_headers = {"Authorization": "Bearer dev-consultant-token"}

    # Unauthorized access check
    res_unauth = client.post("/api/queue/reset/schedules", json={"name": "X", "cron": "* * * * *", "scope": "all"}, headers=consultant_headers)
    assert res_unauth.status_code == 403

    # Invalid cron check
    res_inv_cron = client.post("/api/queue/reset/schedules", json={"name": "X", "cron": "invalid cron", "scope": "all"}, headers=AUTH_HEADERS)
    assert res_inv_cron.status_code == 400
    assert res_inv_cron.json()["code"] == "INVALID_SCHEDULE"

    # Invalid scope check
    res_inv_scope = client.post("/api/queue/reset/schedules", json={"name": "X", "cron": "* * * * *", "scope": "invalid_scope"}, headers=AUTH_HEADERS)
    assert res_inv_scope.status_code == 400


def test_schedule_storage(queue_env):
    from smos.core.queue_reset import ResetScheduleManager
    _, tmp_path = queue_env

    rsm = ResetScheduleManager()
    s1 = rsm.create_schedule(name="S1", cron="0 0 * * *", scope="all")
    
    storage_file = tmp_path / ".jules" / "reset_schedules.json"
    assert storage_file.exists()

    file_data = json.loads(storage_file.read_text())
    assert len(file_data) == 1
    assert file_data[0]["id"] == s1["id"]
    assert file_data[0]["name"] == "S1"


def test_schedule_runs_due(queue_env):
    from smos.core.queue_reset import ResetScheduleManager
    from datetime import datetime, timezone

    qm, tmp_path = queue_env
    task_c = Task(id="task-sched-1", request="Completed task to reset", status=TaskStatus.COMPLETED)
    qm.save_task(task_c)

    rsm = ResetScheduleManager()
    # Schedule set for 02:00 every day
    sched = rsm.create_schedule(name="Nightly Reset", cron="0 2 * * *", scope="completed")

    # Time that does not match (01:00)
    dt_not_due = datetime(2026, 9, 18, 1, 0, tzinfo=timezone.utc)
    ran_1 = rsm.check_and_run_due_schedules(now=dt_not_due)
    assert len(ran_1) == 0

    # Time that matches (02:00)
    dt_due = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)
    ran_2 = rsm.check_and_run_due_schedules(now=dt_due)
    assert len(ran_2) == 1
    assert ran_2[0]["schedule"]["id"] == sched["id"]
    assert ran_2[0]["reset_result"]["moved"] == 1

    # Ensure duplicate execution in same minute is skipped
    ran_3 = rsm.check_and_run_due_schedules(now=dt_due)
    assert len(ran_3) == 0


def test_schedule_audit(queue_env):
    from smos.core.queue_reset import ResetScheduleManager
    from datetime import datetime, timezone

    qm, tmp_path = queue_env
    task_p = Task(id="task-audit-1", request="Pending task for audit test", status=TaskStatus.PENDING)
    qm.save_task(task_p)

    rsm = ResetScheduleManager()
    sched = rsm.create_schedule(name="Minutely Reset", cron="* * * * *", scope="pending")

    dt = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    rsm.check_and_run_due_schedules(now=dt)

    audit_file = tmp_path / ".jules" / "history" / "reset_audit.jsonl"
    assert audit_file.exists()

    lines = [json.loads(line) for line in audit_file.read_text().strip().split("\n") if line]
    assert len(lines) == 1
    entry = lines[0]
    assert entry["action"] == "scheduled_reset"
    assert entry["scope"] == "pending"
    assert entry["schedule_id"] == sched["id"]
    assert entry["moved"] == 1
    assert "reset-" in entry["archive_file"]


def test_audit_log_written_on_reset(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-audit-reset", request="Task to reset and audit", status=TaskStatus.READY)
    qm.save_task(task)

    res = client.post("/api/queue/reset-column", json={"confirm": "RESET", "column": "ready"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    audit_file = tmp_path / ".jules" / "history" / "reset_audit.jsonl"
    assert audit_file.exists()

    lines = [json.loads(line) for line in audit_file.read_text().strip().split("\n") if line]
    assert len(lines) == 1
    entry = lines[0]
    assert entry["action"] == "reset-column"
    assert entry["scope"] == "ready"
    assert entry["moved"] == 1
    assert entry["restored"] == 0
    assert entry["by"] == "operator"
    assert entry["schedule_id"] is None
    assert "reset-" in entry["archive_file"]


def test_audit_log_written_on_undo(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-audit-undo", request="Task to reset then undo", status=TaskStatus.READY)
    qm.save_task(task)

    # 1. Reset
    reset_res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "ready"}, headers=AUTH_HEADERS)
    assert reset_res.status_code == 200

    # Get archive entry archive_id
    arch_res = client.get("/api/queue/archive", headers=AUTH_HEADERS)
    entries = arch_res.json()["entries"]
    assert len(entries) == 1
    aid = entries[0]["archive_id"]

    # 2. Undo selected
    undo_res = client.post("/api/queue/archive/undo", json={"archive_ids": [aid], "confirm": "UNDO"}, headers=AUTH_HEADERS)
    assert undo_res.status_code == 200

    audit_file = tmp_path / ".jules" / "history" / "reset_audit.jsonl"
    lines = [json.loads(line) for line in audit_file.read_text().strip().split("\n") if line]
    assert len(lines) == 2
    undo_entry = lines[1]
    assert undo_entry["action"] == "undo-selected"
    assert undo_entry["restored"] == 1
    assert undo_entry["by"] == "operator"

    # 3. Undo filter
    undo_flt_res = client.post("/api/queue/archive/undo-filter", json={"search": "nonexistent", "confirm": "UNDO"}, headers=AUTH_HEADERS)
    assert undo_flt_res.status_code == 200

    lines = [json.loads(line) for line in audit_file.read_text().strip().split("\n") if line]
    assert len(lines) == 3
    undo_flt_entry = lines[2]
    assert undo_flt_entry["action"] == "undo-filter"
    assert undo_flt_entry["restored"] == 0


def test_audit_log_written_on_scheduled(queue_env):
    from smos.core.queue_reset import ResetScheduleManager
    from datetime import datetime, timezone

    qm, tmp_path = queue_env
    task = Task(id="task-sched-audit", request="Scheduled audit task", status=TaskStatus.COMPLETED)
    qm.save_task(task)

    rsm = ResetScheduleManager()
    sched = rsm.create_schedule(name="Audit Schedule", cron="* * * * *", scope="completed")

    dt = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    rsm.check_and_run_due_schedules(now=dt)

    audit_file = tmp_path / ".jules" / "history" / "reset_audit.jsonl"
    lines = [json.loads(line) for line in audit_file.read_text().strip().split("\n") if line]
    assert len(lines) == 1
    entry = lines[0]
    assert entry["action"] == "scheduled_reset"
    assert entry["schedule_id"] == sched["id"]
    assert entry["moved"] == 1


def test_audit_endpoint_returns_entries(queue_env):
    from smos.core.queue_reset import write_audit_entry

    write_audit_entry(
        action="reset-column",
        scope="all",
        moved=5,
        restored=0,
        by="admin",
        schedule_id=None,
        archive_file=".jules/queue/reset-20260918-120000.jsonl",
        timestamp="2026-09-18T12:00:00+00:00"
    )

    res = client.get("/api/queue/reset/audit", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "entries" in data
    assert len(data["entries"]) == 1
    assert data["entries"][0]["action"] == "reset-column"
    assert data["entries"][0]["moved"] == 5
    assert data["entries"][0]["by"] == "admin"


def test_audit_endpoint_limit(queue_env):
    from smos.core.queue_reset import write_audit_entry

    for i in range(10):
        write_audit_entry(
            action="reset-column",
            scope="ready",
            moved=i,
            timestamp=f"2026-09-18T12:00:{i:02d}+00:00"
        )

    res = client.get("/api/queue/reset/audit?limit=3", headers=AUTH_HEADERS)
    assert res.status_code == 200
    entries = res.json()["entries"]
    assert len(entries) == 3
    # Sorted DESC by timestamp
    assert entries[0]["timestamp"] == "2026-09-18T12:00:09+00:00"


def test_audit_endpoint_empty_ok(queue_env):
    res = client.get("/api/queue/reset/audit", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json() == {"entries": []}


def test_audit_requires_operator(queue_env):
    consultant_headers = {"Authorization": "Bearer dev-consultant-token"}
    res = client.get("/api/queue/reset/audit", headers=consultant_headers)
    assert res.status_code == 403


def test_reset_preserves_history(queue_env):
    qm, tmp_path = queue_env
    task1 = Task(id="task-h1", request="Task 1", status=TaskStatus.COMPLETED)
    task2 = Task(id="task-h2", request="Task 2", status=TaskStatus.COMPLETED)
    qm.save_task(task1)
    qm.save_task(task2)

    state_file = tmp_path / ".co-smos" / "state.json"
    state_before = json.loads(state_file.read_text())
    history_before = state_before.get("history", [])
    assert len(history_before) >= 2

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    state_after = json.loads(state_file.read_text())
    history_after = state_after.get("history", [])
    assert len(history_after) >= len(history_before)
    task_ids_after = [t.get("id") for t in history_after if isinstance(t, dict) and "id" in t]
    assert "task-h1" in task_ids_after
    assert "task-h2" in task_ids_after


def test_reset_appends_event(queue_env):
    qm, tmp_path = queue_env
    task = Task(id="task-ev1", request="Task for event test", status=TaskStatus.READY)
    qm.save_task(task)

    state_file = tmp_path / ".co-smos" / "state.json"
    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    state_after = json.loads(state_file.read_text())
    history = state_after.get("history", [])
    assert len(history) > 0
    last_entry = history[-1]
    assert isinstance(last_entry, dict)
    assert last_entry.get("action") == "reset"
    assert last_entry.get("scope") == "all"
    assert last_entry.get("moved") == 1
    assert "timestamp" in last_entry


def test_reset_does_not_crash_on_empty_history(queue_env):
    qm, tmp_path = queue_env
    state_file = tmp_path / ".co-smos" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"history": [], "tasks": []}))

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    state_after = json.loads(state_file.read_text())
    assert isinstance(state_after.get("history"), list)
    assert len(state_after["history"]) == 1
    assert state_after["history"][0]["action"] == "reset"


def test_reset_does_not_crash_on_missing_history(queue_env):
    qm, tmp_path = queue_env
    state_file = tmp_path / ".co-smos" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"status": "online"}))

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "all"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    state_after = json.loads(state_file.read_text())
    assert isinstance(state_after.get("history"), list)
    assert len(state_after["history"]) == 1
    assert state_after["history"][0]["action"] == "reset"


def test_reset_clears_active_task_if_matching(queue_env):
    qm, tmp_path = queue_env
    task_r = Task(id="task-active-1", request="Running active task", status=TaskStatus.RUNNING)
    qm.save_task(task_r)

    state_file = tmp_path / ".co-smos" / "state.json"
    state_before = json.loads(state_file.read_text())
    assert state_before.get("active_task") is not None
    assert state_before["active_task"].get("id") == "task-active-1"

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "running"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    state_after = json.loads(state_file.read_text())
    assert state_after.get("active_task") is None


def test_reset_clears_last_task_if_matching(queue_env):
    qm, tmp_path = queue_env
    task_c = Task(id="task-last-1", request="Completed last task", status=TaskStatus.COMPLETED)
    qm.save_task(task_c)

    state_file = tmp_path / ".co-smos" / "state.json"
    state_before = json.loads(state_file.read_text())
    assert state_before.get("last_task") is not None
    assert state_before["last_task"].get("id") == "task-last-1"

    res = client.post("/api/queue/reset", json={"confirm": "RESET", "scope": "completed"}, headers=AUTH_HEADERS)
    assert res.status_code == 200

    state_after = json.loads(state_file.read_text())
    assert state_after.get("last_task") is None
