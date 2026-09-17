# ERRATA-0020: No Reset button at task level

## Symptom
User tried to reset a single BLOCKED task from the task card in
Queue. Nothing happened. Only `RESET ALL QUEUES` from the Queue
column header worked.

## Cause
There is NO `/api/tasks/{id}/reset` endpoint.
There is NO task-level Reset button in the UI.
Only column-level reset buttons exist:
  - btn-reset-ready
  - btn-reset-running
  - btn-reset-review
  - btn-reset-blocked
  - btn-reset-completed
  - btn-reset-all

Users may confuse column-level Reset with task-level Reset.

## Fix
Not implemented yet. Options:
1. Add POST /api/tasks/{id}/reset (archive single task + remove)
2. Add Reset button in Task Detail modal
3. Make column-level Reset more obvious (label change)

## Prevention
- Document that Reset is column-scoped, not task-scoped.
- If task-level reset is desired, create a separate task.

## Related
- Задача 1 (Reset + Archive + WHY)
- Column-level reset works correctly
