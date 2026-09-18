# ERRATA-0026: "Undo Selected" in Undo tab — no checkboxes

## Symptom
In Reset Center → Undo tab:
- Filters work: "Matched: 7 tasks" ✅
- Click "↩️ Undo Selected"  → error "No archive tasks selected for undo." ❌
- Click "↩️ Undo All Matched" → works ✅

## Root cause
`triggerUndoSelected()` reads `.archive-select:checked` (checkboxes).
But `.archive-select` checkboxes exist ONLY in **Archive tab**.

In **Undo tab** there are NO checkboxes → selected.length === 0 → error.

## Correct semantics
- **Archive tab**: user selects checkboxes → "Undo Selected"
- **Undo tab**: user filters → "Undo Filtered" (undo those matching filter)

Currently Undo tab has "Undo Selected" — which cannot work.

## Fix (Option C — chosen)

### Undo tab
- REMOVE button "↩️ Undo Selected" (id="btn-undo-selected", line ~1061)
- RENAME "↩️ Undo All Matched" → "↩️ Undo Filtered" (id stays "btn-undo-all-matched")
- Same handler (triggerUndoAllMatched — calls undo-filter endpoint)
- Rationale: "Filtered" is clearer than "All Matched"

### Archive tab
- KEEP "↩️ Undo Selected" (id="btn-undo-selected-archive", line ~985)
- Works with checkboxes ✓

## UX result
| Tab | Button | Action |
|-----|--------|--------|
| Archive | Undo Selected | Undo checked items |
| Undo | Undo Filtered | Undo items matching filter |

Both work, no confusion.

## Rejected alternatives
- **Option A** (just remove "Undo Selected" from Undo tab, keep "Undo All Matched"):
  Leaves confusing name "All Matched". Renaming is better.
- **Option B** (keep both, rename one): duplicate functionality. Bad.

## Related
- Задача 3 (Undo implementation)
- ERRATA-0023/0024/0025 (frontend bugs)
- Задача 9 (fix)

## Status
OPEN — fix via Задача 9 (Option C)
