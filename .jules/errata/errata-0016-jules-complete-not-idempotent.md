# ERRATA-0016: jules-complete.sh is not idempotent

## Symptom
Running jules-complete.sh twice on the same task:

First run:
  [2/7] ✓ Patch applied successfully
  Result: applied

Second run:
  [2/7] Error: Failed to apply patch:
        error: patch failed: frontend/index.html:753
        error: smos/core/scheduler.py: already exists
  Result: error

The second run overwrote the state.json result from
"applied" to "error", even though the code was already
successfully applied.

## Cause
jules-complete.sh always calls jules remote pull --session <id> --apply.
When the patch is already applied, git apply fails, and the
script records result="error" without checking whether the
task was already completed.

## Fix
Add an idempotency check before pulling:
- If state.json history has the task_id with result
  "applied" or "no-op", exit early.
- If last_task.id matches and result is applied/no-op,
  exit early.

## Prevention
- Treat jules-complete.sh as idempotent.
- Do not run it twice on the same task.
- If you need to re-pull, delete the task entry from
  state.json first.

## Related
- ERRATA-0015: Post-pull check misses untracked files.
