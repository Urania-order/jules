# Co-SMOS — Orchestrator State

Updated: 2026-09-18

## Completed
- Co-SMOS v1.1   — Reset Center (Задачі 1-5) ✅
- Co-SMOS v1.1.1 — Sequence UX fix (Задача 6) ✅
- Co-SMOS v1.1.2 — Truncate all views (Задача 7) ✅
- Co-SMOS v1.1.3 — safeDate + layout (Задача 8) ✅
- Co-SMOS v1.1.4 — Fix history overwrite + navbar RESET (Задача 10) ✅
- ERRATA 0019-0029 ✅

## In Progress
- Задача 9: Fix Undo tab buttons (Option C — ERRATA-0026)
  - task ID: TBD
  - Remove "Undo Selected" from Undo tab
  - Rename "Undo All Matched" → "Undo Filtered"
  - After Completed: ./scripts/jules-complete.sh --task <ID>

## Pending (after Задача 9)
- Задача 11: Schedule UX safety (ERRATA-0028 Issue 1-2)
  * enabled: false by default
  * next_run preview
  * warning banner

## Schedule state
- "Nightly Reset" — ✅ DISABLED

## Scripts
- scripts/test.sh                   pytest + auto .venv
- scripts/verify.sh                 universal (--task N / --all / --tests)

## verify.sh — 35/35 passed (Задачі 1-8, 10)

## Last commits (main)
- 28d12a6 chore: add universal scripts/verify.sh
- 0e1f43b docs: add ERRATA-0029 — FIXED 0027 + 0028 Issue 3 (#61)
- 35f7759 chore: record Co-SMOS artifacts for task-20260918-055754
- 076f8ea feat: apply Jules result for task-20260918-055754 (history fix + navbar)

## Tests
~240 passed (after Задача 10)

## ERRATA
- 0019 (FIXED)
- 0020 (OPEN — task-level reset)
- 0021 (FIXED)
- 0022 (INFO)
- 0023 (FIXED via Задача 6)
- 0024 (FIXED via Задача 7)
- 0025 (FIXED via Задача 8)
- 0026 (FIX via Задача 9 — Option C)
- 0027 (FIXED via Задача 10)
- 0028 (PARTIAL — Issue 3 fixed; Issue 1-2 via Задача 11)
- 0029 (INFO — fix log)

## Next options
A. Задача 11 — Schedule UX safety (ERRATA-0028 Issue 1-2)
B. v1.2 — Web Terminal (task + post-complete + tests from UI)
C. v1.2 — Task-level Reset (ERRATA-0020)
D. Stop — v1.1.4 done

## Environment
- Project venv: ~/jules/.venv  (source .venv/bin/activate)
- Node: ~/.nvm/versions/node/v16.20.2/bin
- GitHub/Google APIs: curl works, ping does NOT

## How to start a new chat
1. Paste this file content.
2. Run: jules remote list --session | head -5
3. Continue from "Next options".
