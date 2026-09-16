# ERRATA-0017: test_cli_adapter.py writes to real .jules/queue/

## Symptom
Running pytest created untracked task-*.json files in the
REAL .jules/queue/pending/ directory:

  ?? .jules/queue/pending/task-20260916-174758-8829.json
  ?? .jules/queue/pending/task-20260916-190943-7876.json
  ?? .jules/queue/pending/task-20260916-191641-7346.json

These files appeared even though jules-complete.sh had already
run and cleaned the queue. The source was the test suite.

## Cause
tests/test_cli_adapter.py::test_cli_adapter_add_task accepted
tmp_path and monkeypatch but did NOT use them:

    def test_cli_adapter_add_task(tmp_path, monkeypatch):
        scripts_dir = Path("scripts")        # relative, real repo
        adapter = JulesCLIAdapter(scripts_dir=scripts_dir)
        res = adapter.add_task("Test task from unit test", priority=3)

adapter.add_task() invokes scripts/jules-queue-add.sh, which
reads JULES_PROJECT_ROOT (defaulting to ".") and writes
.jules/queue/pending/task-*.json into the real repo.

## Fix
tests/test_cli_adapter.py was updated (commit 8223f1b) to:
- monkeypatch.chdir(tmp_path)
- monkeypatch.setenv("JULES_PROJECT_ROOT", str(tmp_path))
- create tmp_path/.jules/queue/{pending,running,completed}
- use scripts_dir = PROJECT_ROOT / "scripts" (absolute)
- assert the JSON file is created in tmp_path, not in the real repo

A new test was added:
    test_cli_adapter_does_not_touch_real_queue
which captures git status before/after and asserts equality.

## Prevention
- Any test that invokes jules-queue-add.sh or adapter.add_task
  MUST set JULES_PROJECT_ROOT to tmp_path.
- Add a conftest autouse fixture that isolates JULES_PROJECT_ROOT
  for the entire test session (candidate for v1.1).
- Periodically check:
    git status --short | grep '^.jules/queue/pending'

## Related
- ERRATA-0015: Post-pull check misses untracked forbidden files.
- ERRATA-0016: jules-complete.sh is not idempotent.
