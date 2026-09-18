# Co-SMOS — Orchestrator State

Updated: 2026-09-18

## Completed
- Co-SMOS v1.1   — Reset Center (Задачі 1-5) ✅
- Co-SMOS v1.1.1 — Sequence UX fix (Задача 6) ✅
- Co-SMOS v1.1.2 — Truncate all views (Задача 7) ✅
- Co-SMOS v1.1.3 — safeDate + layout (Задача 8) ✅
- ERRATA 0019-0028 ✅

## In Progress
- Задача 10: task-20260918-055754
    * smos/core/queue_reset.py:318-320 — history append-only
    * frontend/index.html — remove navbar RESET QUEUES button
  - Log: .jules/results/task-20260918-055754.log
  - After Completed: ./scripts/jules-complete.sh --task task-20260918-055754

## Pending (after Задача 10)
- Задача 9:  Fix Undo Selected in Undo tab (ERRATA-0026)
- Задача 11: Schedule UX safety (ERRATA-0028)

## Schedule state
- "Nightly Reset" — ✅ DISABLED (fired 02:00:11, then disabled)

## Last commits (main)
- 0a6ddb1 chore: record task-20260918-055754 dispatch (history fix + navbar)
- 9b84ad2 docs: extend ERRATA-0028 — navbar RESET button removed (#60)
- 3f52126 docs: add ERRATA-0028 — Schedule fired unexpectedly (#59)
- 77d09ee docs: add ERRATA-0027 — state.json history overwritten (#58)

## Tests
235 passed (before Задача 10)

## ERRATA
- 0019 (FIXED)
- 0020 (OPEN)
- 0021 (FIXED)
- 0022 (INFO)
- 0023 (FIXED via Задача 6)
- 0024 (FIXED via Задача 7)
- 0025 (FIXED via Задача 8)
- 0026 (FIX via Задача 9 - pending)
- 0027 (FIX via Задача 10 - in progress)
- 0028 (FIX via Задача 10/11 - in progress)

## Next options
A. v1.2 — Web Terminal (task + post-complete + tests from UI)
B. v1.2 — Task-level Reset (ERRATA-0020)
C. Stop — v1.1.3 done

## Environment
- Project venv: ~/jules/.venv  (source .venv/bin/activate)
- Node: ~/.nvm/versions/node/v16.20.2/bin
- GitHub/Google APIs: curl works, ping does NOT

## How to start a new chat
1. Paste this file content.
2. Run: jules remote list --session | head -5
3. Continue from "Next options".
