# ERRATA-0024: Full prompt rendered in Stages + Control Room

## Symptom
After ERRATA-0023 fixed Commands view (truncate to 120 chars),
the SAME bug still exists in OTHER views:

### View 1 — Stages (Stage Tracking Panel)
`#view-stages` renders full `task.request` (thousands of chars).

### View 2 — Control Room (Active Queue Execution)
`#view-control-room` → "Active Queue Execution" section shows
full `task.request`.

### View 3 — Create New Task modal (input field)
Placeholder / input shows full prompt — minor, input field.

## Cause
The same pattern as ERRATA-0023, but in different render functions:

Line ~2136:
    <div ...>Task: ${escapeHTML(task.request || task.title)} (${task.id})</div>

Line ~2191:
    <div class="task-title">${escapeHTML(task.request || task.title)}</div>

Both render `task.request` without truncation.

## Fix (proposed)
Same pattern as ERRATA-0023 fix:

BEFORE:
    ${escapeHTML(task.request || task.title)}

AFTER:
    ${escapeHTML((task.title || task.request || '').substring(0, 120))}${(task.title || task.request || '').length > 120 ? '…' : ''}

Add `title=` attribute for hover tooltip with full text.

## Views to check
- #view-stages               (Stage Tracking Panel)
- #view-control-room         (Active Queue Execution)
- #view-queue                (Queue — if it renders task.request)
- #view-batch                (Batch Tasks Selector — line 2191)
- #view-sequence (Commands)  — ALREADY FIXED (Задача 6)

## Prevention
- Create a shared JS helper:
    function truncateTask(s, n=120) {
      s = s || '';
      return s.length > n ? s.substring(0, n) + '…' : s;
    }
- Use it in ALL views that render `task.request`.
- Add frontend contract test: "no render function uses raw task.request without truncation"

## Related
- ERRATA-0023 (Sequence UX + 2 bugs) — partially fixed
- Задача 6 (task-20260918-032524) — fixed Commands only
- This ERRATA covers the rest of the views.
