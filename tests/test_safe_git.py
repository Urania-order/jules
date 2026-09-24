import os
import shutil
import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def setup_git_env(tmp_path, monkeypatch):
    """Sets up a test git repo environment for testing safe-git.sh."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "agent@example.com"], cwd=tmp_path, check=True)

    scripts_dir = tmp_path / "scripts"
    mock_bin = tmp_path / "mock_bin"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    mock_bin.mkdir(parents=True, exist_ok=True)

    shutil.copy(PROJECT_ROOT / "scripts" / "safe-git.sh", scripts_dir / "safe-git.sh")
    (scripts_dir / "safe-git.sh").chmod(0o755)

    (tmp_path / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_path, check=True)

    monkeypatch.chdir(tmp_path)
    return {
        "root": tmp_path,
        "scripts": scripts_dir,
        "mock_bin": mock_bin,
    }


def run_bash_cmd(env_info, bash_cmd, env_vars=None):
    env = dict(os.environ)
    if env_info.get("mock_bin"):
        env["PATH"] = f"{env_info['mock_bin']}:{env.get('PATH', '')}"
    if env_vars:
        env.update(env_vars)

    cmd = f"source scripts/safe-git.sh && {bash_cmd}"
    return subprocess.run(
        ["/bin/bash", "-c", cmd],
        capture_output=True,
        text=True,
        env=env,
        cwd=env_info["root"],
    )


def test_remove_stale_git_lock_removes_when_no_git_process(setup_git_env):
    lock_file = setup_git_env["root"] / ".git" / "index.lock"
    lock_file.write_text("stale lock")

    res = run_bash_cmd(setup_git_env, "remove_stale_git_lock")
    assert res.returncode == 0
    assert not lock_file.exists()


def test_remove_stale_git_lock_keeps_when_git_process_running(setup_git_env):
    lock_file = setup_git_env["root"] / ".git" / "index.lock"
    lock_file.write_text("active lock")

    # Command wrapper that overrides 'command' builtin so command -v lsof fails, forcing fallback to pgrep
    cmd = 'command() { if [ "$1" = "-v" ] && [ "$2" = "lsof" ]; then return 1; fi; builtin command "$@"; }; pgrep() { return 0; }; remove_stale_git_lock'
    res = run_bash_cmd(setup_git_env, cmd)
    assert res.returncode == 0
    assert lock_file.exists()


def test_remove_stale_git_lock_with_lsof_holding_lock(setup_git_env):
    lock_file = setup_git_env["root"] / ".git" / "index.lock"
    lock_file.write_text("active lock")

    cmd = 'lsof() { return 0; }; remove_stale_git_lock'
    res = run_bash_cmd(setup_git_env, cmd)
    assert res.returncode == 0
    assert lock_file.exists()


def test_safe_git_checkout_retries_on_lock(setup_git_env):
    tmp_path = setup_git_env["root"]
    lock_file = tmp_path / ".git" / "index.lock"
    lock_file.write_text("stale lock")

    subprocess.run(["git", "branch", "feature"], cwd=tmp_path, check=True)

    res = run_bash_cmd(setup_git_env, "safe_git_checkout feature")
    assert res.returncode == 0
    assert not lock_file.exists()

    branch_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=tmp_path, capture_output=True, text=True)
    assert branch_res.stdout.strip() == "feature"


def test_safe_git_pull_retries_on_lock(setup_git_env):
    tmp_path = setup_git_env["root"]
    lock_file = tmp_path / ".git" / "index.lock"
    lock_file.write_text("stale lock")

    res = run_bash_cmd(setup_git_env, "safe_git_pull origin main")
    assert not lock_file.exists()


def test_safe_git_checkout_fails_after_3_attempts(setup_git_env):
    tmp_path = setup_git_env["root"]

    mock_git = setup_git_env["mock_bin"] / "git"
    mock_git.write_text("""#!/usr/bin/env bash
if [ "$1" = "checkout" ]; then
    echo "Fatal: checkout failed" >&2
    exit 1
fi
exec /usr/bin/git "$@"
""")
    mock_git.chmod(0o755)

    res = run_bash_cmd(setup_git_env, "safe_git_checkout non-existent-branch")
    assert res.returncode == 1
    assert "checkout attempt 1 failed" in res.stderr
    assert "checkout attempt 2 failed" in res.stderr
    assert "checkout attempt 3 failed" in res.stderr
    assert "checkout failed after 3 attempts" in res.stderr


def test_safe_git_stash_push_pop_safe(setup_git_env):
    tmp_path = setup_git_env["root"]
    (tmp_path / "README.md").write_text("# Test Repo modified\n")

    lock_file = tmp_path / ".git" / "index.lock"
    lock_file.write_text("stale lock")

    res_push = run_bash_cmd(setup_git_env, "safe_git_stash_push -u -m 'test stash'")
    assert res_push.returncode == 0
    assert not lock_file.exists()
    assert (tmp_path / "README.md").read_text() == "# Test Repo\n"

    lock_file.write_text("stale lock")
    res_pop = run_bash_cmd(setup_git_env, "safe_git_stash_pop")
    assert res_pop.returncode == 0
    assert not lock_file.exists()
    assert (tmp_path / "README.md").read_text() == "# Test Repo modified\n"
