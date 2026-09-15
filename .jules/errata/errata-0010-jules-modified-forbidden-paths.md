# ERRATA-0010: Jules modified .jules/queue/ before §16 existed

## Historical note
This errata documents an event that occurred on 2026-09-14,
before AGENTS.md §16 (Forbidden paths) was introduced.
It was recorded retroactively on 2026-09-15 to preserve
the lesson and to justify the §16 rule.

## Symptom
In task task-20260914-213202 (API Integration Test Task),
Jules updated multiple files under:

  .jules/queue/completed/
  .jules/queue/pending/
  .jules/queue/deferred/

Example from the session report:

  Updated
  .jules/queue/completed/task-20260914-140637-3859.json
  .jules/queue/completed/task-20260914-183311-3449.json
  .jules/queue/pending/task-20260914-140637-3859.json
  and 2 more

## Cause
At the time, .jules/queue/ was NOT explicitly forbidden.
AGENTS.md had no §16 Forbidden paths.
jules-task.sh did not include "Do NOT modify:" in the prompt.

## Fix
1. Added AGENTS.md §16 Forbidden paths (commit 35fd053).
2. Added "Do NOT modify:" block to scripts/jules-task.sh
   (commit 4fc2edd).
3. Later strengthened the wording to imperative form
   (commit 093f66b, PR #35, see ERRATA-0012).

## Prevention
- §16 must remain in AGENTS.md.
- jules-task.sh must always include the FORBIDDEN PATHS block.
- Any future task that touches forbidden paths is a process
  defect and MUST be recorded as a new errata.
- Orchestrator state (.co-smos/, .jules/tasks/, .jules/results/,
  .jules/queue/) is owned by the orchestrator, not by Jules.

## Related
- ERRATA-0012: shows the ban alone was not sufficient.
