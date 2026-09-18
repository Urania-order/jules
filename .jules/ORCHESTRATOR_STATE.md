# Co-SMOS — Orchestrator State

Updated: 2026-09-18

## Completed
- Co-SMOS v1.1   — Reset Center (Задачі 1-5) ✅
- Co-SMOS v1.1.1 — Sequence UX fix (Задача 6) ✅
- Co-SMOS v1.1.2 — Truncate all views (Задача 7) ✅
- Co-SMOS v1.1.3 — safeDate + layout (Задача 8) ✅
- Co-SMOS v1.1.4 — Fix history + navbar RESET (Задача 10) ✅
- Co-SMOS v1.1.5 — Fix Undo tab buttons (Задача 9, Option C) ✅
- ERRATA 0019-0029 ✅

## Pending
- Задача 11: Schedule UX safety (ERRATA-0028 Issue 1-2)
  * enabled: false by default
  * "Next run" preview
  * warning banner

## Schedule state
- "Nightly Reset" — ✅ DISABLED

## Scripts
- scripts/test.sh          pytest + auto .venv
- scripts/verify.sh        universal (--task N / --all / --tests) — 38/38 ✅
- scripts/run-task.sh      dispatch → wait → complete → verify (one command)
- scripts/jules-task.sh    dispatcher
- scripts/jules-complete.sh pull + apply + push

## Usage (automation)
    ./scripts/run-task.sh /tmp/task-11.txt --verify 11

## Last commits (main)
- eac4b7a chore: update verify.sh (Task 9 applied) + add run-task.sh
- 33c873a chore: record task-20260918-181721 dispatch (Undo UX fix)
- b4ad15e chore: record task-20260918-181721 dispatch (Undo UX fix)
- 67e3050 Merge branch 'main' ...
- 28d12a6 chore: add universal scripts/verify.sh

## Tests
~240 passed

## ERRATA
- 0019 (FIXED)
- 0020 (OPEN — task-level reset, v1.2 feature)
- 0021 (FIXED)
- 0022 (INFO)
- 0023 (FIXED via Задача 6)
- 0024 (FIXED via Задача 7)
- 0025 (FIXED via Задача 8)
- 0026 (FIXED via Задача 9 — Option C)
- 0027 (FIXED via Задача 10)
- 0028 (PARTIAL — Issue 3 fixed; Issue 1-2 pending Задача 11)
- 0029 (INFO — fix log)

## Next options
A. Задача 11 — Schedule UX safety (ERRATA-0028 Issue 1-2)
B. v1.2 — Web Terminal (task + post-complete + tests from UI)
C. v1.2 — Task-level Reset (ERRATA-0020)
D. Stop — v1.1.5 done

## Environment
- Project venv: ~/jules/.venv  (source .venv/bin/activate)
- Node: ~/.nvm/versions/node/v16.20.2/bin
- GitHub/Google APIs: curl works, ping does NOT
- git pull uses rebase (pull.rebase=true) — no more merge editors

## How to start a new chat
1. Paste this file content.
2. Run: jules remote list --session | head -5
3. Continue from "Next options".
