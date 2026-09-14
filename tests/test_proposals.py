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
    assert "No active proposals." in res.stdout


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
    assert f"Deferred: {proposal_id}" in res_reject.stdout

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


def test_review_list_filter_by_priority(queue_dirs):
    run_script("jules-queue-propose.sh", "task-101", "High priority proposal", "10")
    run_script("jules-queue-propose.sh", "task-102", "Low priority proposal", "1")
    run_script("jules-queue-propose.sh", "task-103", "Normal priority proposal", "5")

    # Filter by exact priority string "high" (or 10)
    res_high = run_script("jules-queue-review.sh", "--priority", "high", "list")
    assert res_high.returncode == 0
    assert "Found 1 proposal(s)" in res_high.stdout
    assert "High priority proposal" in res_high.stdout
    assert "Low priority proposal" not in res_high.stdout

    # Filter by priority integer "1"
    res_low = run_script("jules-queue-review.sh", "-p", "1", "list")
    assert res_low.returncode == 0
    assert "Found 1 proposal(s)" in res_low.stdout
    assert "Low priority proposal" in res_low.stdout

    # Filter by min-priority 5
    res_min = run_script("jules-queue-review.sh", "--min-priority", "5", "list")
    assert res_min.returncode == 0
    assert "Found 2 proposal(s)" in res_min.stdout
    assert "High priority proposal" in res_min.stdout
    assert "Normal priority proposal" in res_min.stdout
    assert "Low priority proposal" not in res_min.stdout


def test_review_list_filter_by_source_task(queue_dirs):
    run_script("jules-queue-propose.sh", "task-alpha-100", "Alpha proposal", "3")
    run_script("jules-queue-propose.sh", "task-beta-200", "Beta proposal", "3")

    # Filter by source task substring
    res_alpha = run_script("jules-queue-review.sh", "--source-task", "task-alpha", "list")
    assert res_alpha.returncode == 0
    assert "Found 1 proposal(s)" in res_alpha.stdout
    assert "Alpha proposal" in res_alpha.stdout
    assert "Beta proposal" not in res_alpha.stdout

    # Filter by combined source task and priority
    res_comb = run_script("jules-queue-review.sh", "-s", "beta", "-p", "3", "list")
    assert res_comb.returncode == 0
    assert "Found 1 proposal(s)" in res_comb.stdout
    assert "Beta proposal" in res_comb.stdout


def test_review_deferred_filter(queue_dirs):
    # Propose and reject to move to deferred
    run_script("jules-queue-propose.sh", "task-def-1", "Deferred High", "10")
    run_script("jules-queue-propose.sh", "task-def-2", "Deferred Low", "1")

    p_files = list(queue_dirs["proposed"].glob("*.json"))
    for pf in p_files:
        p_data = json.loads(pf.read_text())
        run_script("jules-queue-review.sh", "reject", p_data["id"])

    # Test filtering deferred list
    res_def_high = run_script("jules-queue-review.sh", "--priority", "10", "deferred")
    assert res_def_high.returncode == 0
    assert "Found 1 deferred proposal(s)" in res_def_high.stdout
    assert "Deferred High" in res_def_high.stdout
    assert "Deferred Low" not in res_def_high.stdout


def test_propose_with_ttl_and_expire(queue_dirs):
    # Propose task with 3 day TTL
    res_prop = run_script("jules-queue-propose.sh", "task-600", "TTL proposal", "3", "3")
    assert res_prop.returncode == 0

    proposal_files = list(queue_dirs["proposed"].glob("*.json"))
    assert len(proposal_files) == 1
    p_file = proposal_files[0]

    data = json.loads(p_file.read_text())
    assert "expires_at" in data
    assert data["ttl_days"] == 3

    # Fast-forward created_at & expires_at in proposal file to past
    from datetime import datetime, timezone, timedelta
    past_dt = datetime.now(timezone.utc) - timedelta(days=5)
    data["created_at"] = past_dt.isoformat()
    data["expires_at"] = (past_dt + timedelta(days=3)).isoformat()
    p_file.write_text(json.dumps(data, indent=2))

    # Run expire command
    res_exp = run_script("jules-queue-review.sh", "expire")
    assert res_exp.returncode == 0
    assert "Expired" in res_exp.stdout

    # Proposed directory should now be empty
    assert len(list(queue_dirs["proposed"].glob("*.json"))) == 0

    # Deferred directory should contain expired proposal
    deferred_files = list(queue_dirs["completed"].parent.joinpath("deferred").glob("*.json"))
    assert len(deferred_files) == 1
    def_data = json.loads(deferred_files[0].read_text())
    assert def_data["status"] == "expired"
    assert "expired_at" in def_data
