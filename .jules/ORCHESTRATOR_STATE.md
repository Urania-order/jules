# Co-SMOS — Orchestrator State

Updated: 2026-09-18

## Completed
- Co-SMOS v1.1   — Reset Center (Задачі 1-5) ✅
- Co-SMOS v1.1.1 — Sequence UX fix (Задача 6) ✅
- Co-SMOS v1.1.2 — Truncate all views (Задача 7) ✅
- ERRATA 0019-0025 ✅

## In Progress
- Задача 8: task-20260918-044038 — safeDate helper + Queue layout fix
  - Extends: line 1888 (Queue) + line 2906 (Recordings) date fallback
  - Also: COMPLETED badge/button overlap in Queue card
  - Adds shared safeDate() helper near truncateTask() (line 2801)
  - After Completed: ./scripts/jules-complete.sh --task task-20260918-044038

## Last commits (main)
- c82bc51 chore: record Co-SMOS artifacts for task-20260918-040154
- a716166 feat: apply Jules result for task-20260918-040154 (truncate all)
- 8b8de0e docs: update ORCHESTRATOR_STATE.md
- 346b8c3 chore: record task-20260918-040154 dispatch (Truncate all views)
- 1977812 docs: add ERRATA-0024 — Full prompt in Stages + Control Room (#55)

## Tests
234 passed (before Задача 8)

## ERRATA
- 0019 Jules Description generic (FIXED)
- 0020 No task-level reset (OPEN — feature gap)
- 0021 .venv before pytest (FIXED)
- 0022 Co-SMOS v1.1 summary (INFO)
- 0023 Sequence vs Sequences UX + 2 bugs (FIXED via Задача 6)
- 0024 Full prompt in Stages + Control Room (FIXED via Задача 7)
- 0025 [Invalid Date] in Queue + Recordings + layout (FIX via Задача 8)

## Shared helpers in frontend/index.html
- truncateTask(s, n=120) — line 2801
- safeDate(s)             — TBD (Задача 8)

## Scripts
- scripts/test.sh                   pytest + auto .venv
- scripts/verify-cosmos-v11.sh      33 checks

## Next options (after Задача 8)
A. Universal verify.sh (--task N / --all / --tests) — 15 min
B. v1.2: Task-level Reset (ERRATA-0020), refresh buttons, real cron, server-side scheduler
C. Stop — v1.1.3 done

## Environment
- Project venv: ~/jules/.venv  (source .venv/bin/activate)
- Node: ~/.nvm/versions/node/v16.20.2/bin
- GitHub/Google APIs: curl works, ping does NOT
- DNS/SSL timeouts to GitHub/Google happened 3x (transient)

## How to start a new chat
1. Paste this file content.
2. Run: jules remote list --session | head -5
3. Continue from "Next options".
