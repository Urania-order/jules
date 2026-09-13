import json
import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def queue_dirs(tmp_path, monkeypatch):
    """Fixture providing isolated queue directories for proposal testing."""
    jules_dir = tmp_path / ".jules" / "queue"
    pending = jules_dir / "pending"
    running = jules_dir / "running"
    completed = jules_dir / "completed"
    proposed = jules_dir / "proposed"

    pending.mkdir(parents=True, exist_ok=True)
    running.mkdir(parents=True, exist_ok=True)
    completed.mkdir(parents=True, exist_ok=True)
    proposed.mkdir(parents=True, exist_ok=True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))

    return {
        "root": tmp_path,
        "queue": jules_dir,
        "pending": pending,
        "running": running,
        "completed": completed,
        "proposed": proposed,
    }


def run_script(script_name, *args, env=None):
    script_path = PROJECT_ROOT / "scripts" / script_name
    cmd = ["bash", str(script_path), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_propose_creates_json(queue_dirs):
    res = run_script("jules-queue-propose.sh", "task-101", "Implement WebSocket metrics", "4")
    assert res.returncode == 0
    assert "Proposal:" in res.stdout

    proposal_files = list(queue_dirs["proposed"].glob("*.json"))
    assert len(proposal_files) == 1

    data = json.loads(proposal_files[0].read_text())
    assert data["source_task"] == "task-101"
    assert data["description"] == "Implement WebSocket metrics"
    assert data["priority"] == 4
    assert data["status"] == "proposed"
    assert data["proposed_by"] == "jules"
    assert "created_at" in data


def test_propose_missing_arguments(queue_dirs):
    res = run_script("jules-queue-propose.sh")
    assert res.returncode != 0
    assert "Usage:" in res.stdout or "Usage:" in res.stderr


def test_review_list_empty(queue_dirs):
    res = run_script("jules-queue-review.sh", "list")
    assert res.returncode == 0
    assert "No proposals." in res.stdout


def test_review_list_with_proposals(queue_dirs):
    run_script("jules-queue-propose.sh", "task-101", "Proposal One", "5")
    run_script("jules-queue-propose.sh", "task-102", "Proposal Two", "2")

    res = run_script("jules-queue-review.sh", "list")
    assert res.returncode == 0
    assert "Found 2 proposal(s):" in res.stdout
    assert "Proposal One" in res.stdout
    assert "Proposal Two" in res.stdout


def test_review_accept_proposal(queue_dirs):
    res_prop = run_script("jules-queue-propose.sh", "task-200", "Add export report endpoint", "3")
    assert res_prop.returncode == 0

    proposal_files = list(queue_dirs["proposed"].glob("*.json"))
    assert len(proposal_files) == 1
    proposal_id = proposal_files[0].stem

    res_accept = run_script("jules-queue-review.sh", "accept", proposal_id)
    assert res_accept.returncode == 0
    assert f"✅ Accepted: {proposal_id}" in res_accept.stdout

    # Original proposal should be removed
    assert len(list(queue_dirs["proposed"].glob("*.json"))) == 0

    # Pending task should be created
    pending_files = list(queue_dirs["pending"].glob("*.json"))
    assert len(pending_files) == 1

    pending_data = json.loads(pending_files[0].read_text())
    assert pending_data["request"] == "Add export report endpoint"
    assert pending_data["priority"] == 3
    assert pending_data["status"] == "pending"
    assert pending_data["proposed_by"] == "jules"
    assert pending_data["source_task"] == "task-200"


def test_review_accept_nonexistent(queue_dirs):
    res = run_script("jules-queue-review.sh", "accept", "proposal-nonexistent")
    assert res.returncode != 0
    assert "Not found:" in res.stdout or "Not found:" in res.stderr


def test_review_reject_proposal(queue_dirs):
    res_prop = run_script("jules-queue-propose.sh", "task-300", "Bad proposal", "1")
    assert res_prop.returncode == 0

    proposal_files = list(queue_dirs["proposed"].glob("*.json"))
    assert len(proposal_files) == 1
    proposal_id = proposal_files[0].stem

    res_reject = run_script("jules-queue-review.sh", "reject", proposal_id)
    assert res_reject.returncode == 0
    assert f"❌ Rejected: {proposal_id}" in res_reject.stdout

    assert len(list(queue_dirs["proposed"].glob("*.json"))) == 0
    assert len(list(queue_dirs["pending"].glob("*.json"))) == 0


def test_review_accept_all(queue_dirs):
    run_script("jules-queue-propose.sh", "task-400", "Prop A", "3")
    run_script("jules-queue-propose.sh", "task-400", "Prop B", "4")

    assert len(list(queue_dirs["proposed"].glob("*.json"))) == 2

    res = run_script("jules-queue-review.sh", "accept-all")
    assert res.returncode == 0

    assert len(list(queue_dirs["proposed"].glob("*.json"))) == 0
    assert len(list(queue_dirs["pending"].glob("*.json"))) == 2


def test_review_reject_all(queue_dirs):
    run_script("jules-queue-propose.sh", "task-500", "Prop X", "1")
    run_script("jules-queue-propose.sh", "task-500", "Prop Y", "2")

    assert len(list(queue_dirs["proposed"].glob("*.json"))) == 2

    res = run_script("jules-queue-review.sh", "reject-all")
    assert res.returncode == 0

    assert len(list(queue_dirs["proposed"].glob("*.json"))) == 0
    assert len(list(queue_dirs["pending"].glob("*.json"))) == 0


def test_review_invalid_action(queue_dirs):
    res = run_script("jules-queue-review.sh", "invalid-action")
    assert res.returncode != 0
    assert "Usage:" in res.stdout or "Usage:" in res.stderr
