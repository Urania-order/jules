# ERRATA-0023: "Sequence" vs "Sequences" UX confusion + 2 bugs

## Symptom (3 issues)

### Issue 1 — Duplicate-looking navbar entries
Navbar shows BOTH:
- "Sequence"  (singular) — `data-view="sequence"`  (line 883)
- "Sequences" (plural)   — `data-view="sequences"` (line 887)

Two different features with near-identical names:
- `Sequence`  -> Command Sequence View  (renderSequence(),  line 2144, view line 1134)
- `Sequences` -> Recording & Replay     (renderSequences(), line 2875, view line 1298)

### Issue 2 — "[Invalid Date]" in Command Sequence View
Line 2157:
    const timeStr = new Date(task.created_at).toLocaleTimeString();

When `task.created_at` is undefined/null/unparseable, JS returns "Invalid Date".

### Issue 3 — Full prompt rendered in card
Line 2167:
    ${escapeHTML(task.request || task.title)}

`task.request` contains the ENTIRE prompt (thousands of chars).
No truncation -> unreadable list.

## Fix (exact line replacements)

### Line 2157
BEFORE:
    const timeStr = new Date(task.created_at).toLocaleTimeString();

AFTER:
    const rawDate = task.created_at;
    const parsed = rawDate ? new Date(rawDate) : null;
    const timeStr = (parsed && !isNaN(parsed)) ? parsed.toLocaleTimeString() : (rawDate || 'N/A');

### Line 2167
BEFORE:
    <span style="color: var(--text-secondary); margin-left: auto;">${escapeHTML(task.request || task.title)}</span>

AFTER:
    <span style="color: var(--text-secondary); margin-left: auto;" title="${escapeHTML(task.request || task.title || '')}">${escapeHTML((task.title || task.request || '').substring(0, 120))}${(task.title || task.request || '').length > 120 ? '…' : ''}</span>

### Issue 1 — Navbar labels
BEFORE:
    <button class="nav-btn" data-view="sequence">Sequence</button>
    <button class="nav-btn" data-view="sequences">Sequences</button>

AFTER:
    <button class="nav-btn" data-view="sequence">Commands</button>
    <button class="nav-btn" data-view="sequences">Recordings</button>

(data-view values unchanged -> JS handlers unaffected)

## Prevention
- Dates: parse defensively (`isNaN(new Date(x))`), never trust raw.
- Long text: always truncate in list views; use `title=` for full.
- Naming: avoid singular/plural pairs for different features.

## Related
- Command Sequence View  (line 1134, renderSequence  line 2144)
- Recording & Replay     (line 1298, renderSequences line 2875)
- Co-SMOS v1.1 Reset Center (ERRATA-0022)
