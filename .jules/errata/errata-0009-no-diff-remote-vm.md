# ERRATA-0009: Jules returns "No diff found in the remote VM"

## Symptom
`jules remote pull --session <id> --apply` returns:
"No diff found in the remote VM."

Jules session status is "Completed", but no code changes were made.

## Cause
Possible reasons:
1. Task was an audit/analysis, not an implementation task.
2. Task request lacked explicit acceptance criteria.
3. Jules found nothing to change and exited successfully.
4. Jules misunderstood the scope and did nothing.

## Fix
1. Verify the task request contains a clear, actionable change.
2. Add explicit acceptance criteria to the request.
3. After "No diff" — check the session log and task record
   to confirm whether the no-op was intentional.
4. Update state.json to mark the task as completed with
   result="no code changes".

## Prevention
- Always include acceptance criteria in the task request.
- Prefer implementation tasks over open-ended "analyze" tasks.
- If task is an audit, expect no diff — mark it explicitly.
- Record no-op sessions in history with reason.
