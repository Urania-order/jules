# ERRATA-0025: "[Invalid Date]" in Queue + Recordings

## Symptom
After Задача 6 fixed renderSequence() (line 2157),
"[Invalid Date]" still appears in:

1. Queue Management — task card (line 1888):
       <span>Created: ${new Date(task.created_at).toLocaleTimeString()}</span>
   Screenshot: COMPLETED cards show "Created: Invalid Date"

2. Recording & Replay — sequence card (line 2906):
       <span>Created: ${new Date(seq.created_at).toLocaleTimeString()}</span>

## Cause
`task.created_at` / `seq.created_at` may be missing or unparseable
in old records. `new Date(...).toLocaleTimeString()` returns
"Invalid Date" without fallback.

Задача 6 fixed only renderSequence() (line 2157).
These 2 lines remained.

## Exact locations
    grep -n "new Date(task.created_at)\|new Date(.*created_at" frontend/index.html

Output:
    1888: Queue card         — new Date(task.created_at)
    2906: Recordings card    — new Date(seq.created_at)

## Fix (shared helper)
Add near truncateTask() (line 2801):

    function safeDate(s) {
      if (!s) return 'N/A';
      const d = new Date(s);
      return isNaN(d) ? String(s) : d.toLocaleString();
    }

Replace both lines:

Line 1888:
BEFORE:
    <span>Created: ${new Date(task.created_at).toLocaleTimeString()}</span>
AFTER:
    <span>Created: ${safeDate(task.created_at)}</span>

Line 2906:
BEFORE:
    <span>Created: ${new Date(seq.created_at).toLocaleTimeString()}</span>
AFTER:
    <span>Created: ${safeDate(seq.created_at)}</span>

## Also (Screenshot issue)
In Queue COMPLETED cards, badge "[COMPLETED]" and button "[View]"
overlap with the card text. Layout issue — z-index or flex-wrap.

Fix (CSS):
- Ensure .badge-COMPLETED and .task-view-btn don't overlap
- Card container: flex-wrap: wrap; gap: 0.5rem;
- Or move badge + button to a separate row

## Prevention
- Use safeDate() everywhere instead of raw new Date(...).toLocale*
- Add frontend contract test:
    * safeDate helper exists
    * no raw new Date(task.created_at) in view code

## Related
- ERRATA-0023 — Sequence UX + Invalid Date (fixed renderSequence)
- Задача 6 (task-20260918-032524)
- Задача 7 (task-20260918-040154) — truncateTask helper
- ERRATA-0024 — truncate all views
- This ERRATA — dates + Queue layout

## Status
OPEN — needs Задача 8
