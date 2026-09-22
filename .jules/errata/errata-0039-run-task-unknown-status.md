# ERRATA-0039: run-task.sh reports "unknown" for valid session

## Severity
MEDIUM — run-task.sh waits 12+ min, never detects Completed

## Symptom (2026-09-22, TASK 03 / task-20260922-191951)
- run-task.sh [3/5] Wait for Completed:
    [+0s] unknown
    ...
    [+750s] unknown
- Jules session Completed after 12 min
- run-task.sh never detects Completed

## Root cause (two bugs)

### Bug 1 — TASK_MATCH not in Description
- TASK_MATCH = "20260922-191951" (date part of task_id)
- jules remote list --session shows: ID, Description (first 60 chars), Repo, Last active, Status
- Description = "Co-SMOS — TASK 03 — CONTEXT MODEL..." (NOT task_id)
- grep -F "20260922-191951" → 0 matches

### Bug 2 — Fallback DESC from wrong file section
- Fallback: DESC=$(head -c 40 "$TASK_FILE" | tr -d '\n')
- TASK_FILE = .jules/tasks/task-<TASK_ID>.md
- Its structure:
    # Jules Task

    ## Task ID

    task-20260922-191951

    ## Created
    ...
    ## Request
    Co-SMOS — TASK 03 — CONTEXT MODEL    ← ACTUAL prompt
- head -c 40 grabs "# Jules Task\n\n## Task ID\n\ntask-20260922-" (metadata, not prompt)
- tr -d '\n' does NOT remove internal newlines (only trailing)
- grep -F "$DESC" → 0 matches

## Fix (v1.3.2)
1. Extract TASK_DESC from task file ## Request section:
    DESC=$(awk '/^## Request/{flag=1;next}/^## /{flag=0}flag' "$TASK_FILE" | head -1 | head -c 40)
2. Or: use session_id from task log:
    SESSION_ID=$(grep -oE 'ID: [0-9]+' .jules/results/$TASK_ID.log | head -1 | awk '{print $2}')
    jules remote list --session | grep "$SESSION_ID"
3. Never report "unknown" without trying all fallbacks
4. If unknown after 60s, print warning and log

## Workaround
- Manual: ./scripts/jules-complete.sh --task task-...
- Or: grep session_id from .jules/results/task-<TASK_ID>.log

## Related
- v1.2.9 (introduced TASK_MATCH fix — incomplete)
- TASK 03 (task-20260922-191951)

## Status
OPEN — needs v1.3.2
