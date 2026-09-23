# ERRATA-0044: test_jules_complete_removes_stale_lock flaky in CI

## Severity
MEDIUM — CI fails intermittently; local passes

## Symptom (2026-09-24, TASK 07 / task-20260923-192923)
- CI: FAILED tests/test_jules_complete_flow.py::test_jules_complete_removes_stale_lock
- 1 failed, 418 passed
- Local (pytest test_jules_complete_flow.py -v):
    419 passed (including stale_lock test)
- Re-run alone: passes
- Flaky (race condition, order-dependent)

## Cause (hypothesis)
- Mock-based test (see ERRATA-0040: Jules bash mock tests)
- Test relies on mocking git/jules CLI; environment differs in CI
- May depend on test execution order
- v1.3.1 introduced safe_git_commit; test verifies stale lock removal

## Impact
- CI fails intermittently → jules-complete.sh reports "CI FAILED"
- Manual fix: commit TASK 07 (patch applied, local tests pass)
- Flaky tests erode trust in CI

## Fix (v1.5)
1. Investigate test_jules_complete_flow.py::test_jules_complete_removes_stale_lock
   - Is it order-dependent? (use pytest-randomly or --forked)
   - Does it assume specific git state?
2. Make test deterministic:
   - Isolate git repo per test (tmp_path)
   - Clean .git/index.lock before test
   - Mock git commit / push to be deterministic
3. Mark as @pytest.mark.flaky(reruns=3) if truly non-deterministic
4. Or: run pytest with --forked (pytest-forked) for isolation

## Workaround
- Locally: passes (419/419)
- CI: may fail on that test only
- Commit patch manually (as in TASK 07)

## Related
- v1.3.1 (introduced safe_git_commit + stale lock detection)
- ERRATA-0040 (Jules bash mock tests)
- ERRATA-0043 (Jules tests fail on own code)

## Status
OPEN — needs v1.5
