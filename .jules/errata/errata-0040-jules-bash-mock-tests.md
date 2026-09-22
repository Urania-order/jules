# ERRATA-0040: Jules writes non-working mock tests for bash scripts

## Severity
MEDIUM — recurring; tests fail; commit skipped; manual cleanup needed

## Symptom (recurring)
Jules tasks that modify bash scripts (run-task.sh, jules-complete.sh)
ask for tests. Jules writes pytest tests with mock/subprocess, but:

- tests fail (assert mismatch)
- tests hang (infinite subprocess wait)
- tests do not set up required fixtures:
    .jules/results/<TASK_ID>.log (for fallback a)
    .jules/tasks/<TASK_ID>.md with ## Request (for fallback c)

## Observed instances
- v1.2.8 (task-20260920-073119): 3 tests hang
- v1.2.9 (task-20260920-093029): 3 tests fail
- v1.3.2 (task-20260922-200334): 2 tests fail

## Root cause
1. Bash scripts are hard to unit-test from Python
2. Jules mock does not replicate real filesystem state:
   - .jules/results/<TASK_ID>.log is not created in test tmp_path
   - .jules/tasks/<TASK_ID>.md with ## Request is not created
3. Mock jules CLI may not intercept jules-task.sh subprocess
4. Tests assume mock behavior but not actual script behavior

## Fix (process)
1. For bash-only changes: DO NOT ask for Python pytest tests
   Instead:
   - bash -n (syntax)
   - run with --help or --dry-run
   - manual smoke test
2. Or: extract testable logic into Python module
3. Or: mark bash integration tests as @pytest.mark.integration
   (skip by default)

## ТЗ guidance
When task asks for bash script change:

    TESTS:
    - bash -n (syntax check)
    - optional: run with --help
    Do NOT ask for pytest mock tests for shell scripts.

## Related
- v1.2.8, v1.2.9, v1.3.2
- v1.3.2 removed tests/test_run_task_errata39.py

## Status
OPEN — process guidance needed
