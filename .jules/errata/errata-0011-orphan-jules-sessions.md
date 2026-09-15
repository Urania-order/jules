# ERRATA-0011: Orphan Jules sessions (no artifacts in repo)

## Historical note
This errata documents a pattern observed on 2026-09-14/15.
It was recorded retroactively on 2026-09-15.

## Symptom
A Jules session reports STATUS: SUCCESS with a full report
(e.g. task-20260914-213202 — API Integration Test Task,
115 tests passing, 100% route coverage), but:

- no commit in git history
- no task record in .co-smos/state.json
- no files in tests/ or smos/
- no ADR in .jules/history/
- no log in .jules/results/

The session result was never pulled into the local repository.

## Cause
Possible reasons:
1. `jules remote pull --session <id> --apply` was never run.
2. Session expired in Jules VM before pull.
3. Result was empty ("No diff found in the remote VM")
   and was not recorded.
4. Task was dispatched but the orchestrator did not track
   its completion (no state.json update).

## Fix
1. Always run `jules remote pull --session <id> --apply`
   after the session reaches Completed.
2. Always update .co-smos/state.json (active_task -> last_task
   + history) after pull.
3. If pull returns "No diff", record the no-op explicitly
   (see ERRATA-0009).
4. If session is no longer available, record the loss as errata
   and note that the work must be redone if needed.

## Prevention
- jules-task.sh MUST record session_id in state.json at start.
- jules-complete.sh MUST pull + update state + commit + push.
- Any "SUCCESS" report without a corresponding commit in main
  is a defect and MUST be recorded.
- Verify with:

    git log --all | grep <task_id>
    ls .jules/tasks/<task_id>.md

  If neither exists — the task is orphaned.

## Example
task-20260914-213202 (API Integration Test Task, session unknown)
- Reported: 115 tests passing, ADR-0008, tests/test_federation_api.py,
  tests/test_domain_api.py
- Reality: none of these exist in the repository.

## Related
- ERRATA-0009: no-diff sessions.
- scripts/jules-complete.sh (commit deffb6e) was created to
  atomically prevent this class of failures.
