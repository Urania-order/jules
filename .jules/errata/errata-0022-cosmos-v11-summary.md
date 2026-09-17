# ERRATA-0022: Co-SMOS v1.1 — Reset Center summary

## Scope
Co-SMOS v1.1 added Reset Center with 5 features across 5 tasks.

## Delivered
- Задача 1: Column Reset + Archive + WHY
- Задача 2: Archive Export (CSV / MD / JSONL)
- Задача 3: Archive Undo (Selected + Filter by status/date)
- Задача 4: Scheduled Reset (cron)
- Задача 5: Reset Audit Log

## Endpoints added
- POST   /api/queue/reset-column
- GET    /api/queue/archive/export?format=csv|md|jsonl
- GET    /api/queue/archive
- POST   /api/queue/archive/undo
- POST   /api/queue/archive/undo-filter
- GET    /api/queue/reset/schedules
- POST   /api/queue/reset/schedules
- PATCH  /api/queue/reset/schedules/{id}
- DELETE /api/queue/reset/schedules/{id}
- GET    /api/queue/reset/audit?limit=50

## Storage (all gitignored)
- .jules/queue/reset-YYYYMMDD-HHMMSS.jsonl   (archive)
- .jules/reset_schedules.json                (cron schedules)
- .jules/history/reset_audit.jsonl           (audit log)

## Frontend
Reset Center panel with tabs:
- Columns   — existing reset buttons
- Archive   — list with checkboxes + Shift+Click range
- Undo      — filters + Undo Selected / Undo All Matched
- Scheduled — cron cards
- Audit     — last 50 entries

## ERRATA fixed during v1.1
- 0019 — Jules session Description generic (task title as first line)
- 0020 — No task-level reset (documented as feature gap)
- 0021 — Must activate .venv before pytest

## Tests
- 220 -> 225 passed after Задача 4
- 225 -> 232 passed after Задача 5 (audit)
- verify-cosmos-v11.sh: 33/33 checks passed

## Verification
./scripts/verify-cosmos-v11.sh

## Status
Co-SMOS v1.1 COMPLETE
