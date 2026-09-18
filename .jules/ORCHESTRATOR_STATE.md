# Co-SMOS — Orchestrator State

Updated: 2026-09-18

## Completed
- Co-SMOS v1.1 — Reset Center (Задачі 1-5) ✅
- Co-SMOS v1.1.1 — Sequence UX fix (Задача 6) ✅
- ERRATA 0019-0024 ✅

## In Progress
- Задача 7: task-20260918-040154 — Truncate task.request in ALL views
  - Extends ERRATA-0023/0024 fix to Stages, Control Room, Batch
  - Adds shared truncateTask() helper
  - After Completed: ./scripts/jules-complete.sh --task task-20260918-040154

## Last commits (main)
- 1977812 docs: add ERRATA-0024 — Full prompt in Stages + Control Room (#55)
- e617bbf chore: record Co-SMOS artifacts for task-20260918-032524
- dbc62c6 feat: apply Jules result for task-20260918-032524 (Sequence UX)
- 1a6a0db chore: record Co-SMOS artifacts (DNS-failed attempt)
- 214bfba docs: add ORCHESTRATOR_STATE.md

## Tests
233 passed (before Задача 7)

## ERRATA
- 0019 Jules Description generic (FIXED)
- 0020 No task-level reset (OPEN — feature gap)
- 0021 .venv before pytest (FIXED)
- 0022 Co-SMOS v1.1 summary (INFO)
- 0023 Sequence vs Sequences UX + 2 bugs (FIXED via Задача 6)
- 0024 Full prompt in Stages + Control Room (FIX via Задача 7)

## Scripts
- scripts/test.sh                   pytest + auto .venv
- scripts/verify-cosmos-v11.sh      33 checks

## Задача 7 goal (verify after complete)
- truncateTask(s, n=120) helper exists
- No raw ${escapeHTML(task.request || task.title)} in views
- Applied in: #view-stages, #view-control-room, #view-batch, others

## Next options
A. Universal verify.sh (--task N / --all / --tests)
B. v1.2: Task-level Reset, refresh buttons, real cron, server-side scheduler
C. Stop — v1.1.2 done

## Environment
- Project venv: ~/jules/.venv  (source .venv/bin/activate)
- Node: ~/.nvm/versions/node/v16.20.2/bin
- GitHub/Google APIs: curl works, ping does NOT
- DNS timeout to *.googleapis.com happened once (transient)

## How to start a new chat
1. Paste this file content.
2. Run: jules remote list --session | head -5
3. Continue from "Next options".
