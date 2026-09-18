# ERRATA-0028: Schedule "Nightly Reset" fired unexpectedly

## Severity
MEDIUM — UX / safety

## Symptom
User created a schedule via UI (Nightly Reset, cron "0 2 * * *",
scope "completed", enabled by default).
User did NOT intend for it to run automatically.

At 02:00:11 next night, the schedule actually fired:
- COMPLETED column cleared
- 7 tasks archived
- state.json history overwritten (see ERRATA-0027)

## Cause
1. UI defaults `enabled: true` when creating a schedule
2. No warning: "This schedule will run automatically at the cron time"
3. No dry-run / preview of "next run time"
4. User treated it as a template, not an active job

## Impact
- Surprise data manipulation at night
- Combined with ERRATA-0027 → history loss
- User trust in scheduling feature

## Fix (proposed)
### UI
- Default `enabled: false` for new schedules
- Show warning banner when `enabled: true`:
    "⚠ This schedule will run automatically. Next run: 2026-09-18 02:00"
- Add "Next run" preview field (computed from cron)
- Confirmation modal on enabling a schedule

### Backend
- Add `POST /api/queue/reset/schedules/preview` → returns next_run for cron
- On schedule create, log to audit: {"action": "schedule_created", ...}
- On schedule fire, log to audit: {"action": "scheduled_reset", "schedule_id": ..., ...}

### Safety
- For "destructive" scopes (all, completed), require explicit confirmation
- Optional: first run as dry-run

## Related
- ERRATA-0027 (state history overwritten by same reset)
- Задача 4 (Scheduled Reset implementation)

## Status
OPEN — needs Задача 11 (UX fix)

---

## Issue 3 — RESET QUEUES button in navbar (accidental data loss)

### Symptom
The navbar (top row) has a red "⚠ RESET QUEUES" button next to "⟳ SYNC".
It is too easy to click accidentally. It triggers reset scope=all
without a confirmation dialog. Users have wiped queues by mistake.

### Cause
The button was added for convenience but:
1. No confirmation modal (unlike Undo, which requires "UNDO" text)
2. Positioned next to SYNC (both are "action" buttons)
3. Scope=all is the most destructive option

### Fix (proposed)
- REMOVE the RESET QUEUES button from the navbar entirely.
- Keep RESET ALL QUEUES in Queue Management view (contextual, less accidental).
- Keep Reset Center → Columns buttons (fine-grained control).
- If a topbar shortcut is desired later, put it behind a menu with
  confirmation ("Type RESET to confirm").

### Status
FIX via Задача 10 (backend history fix + navbar button removal combined)
