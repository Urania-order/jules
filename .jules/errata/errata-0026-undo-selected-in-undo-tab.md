# ERRATA-0026: "Undo Selected" in Undo tab — no checkboxes

## Symptom
In Reset Center → Undo tab:
- Filters work: "Matched: 7 tasks" ✅
- Click "↩️ Undo Selected"  → error "No archive tasks selected for undo." ❌
- Click "↩️ Undo All Matched" → works ✅

## Exact locations
Line 985:  Archive tab  → <button id="btn-undo-selected-archive" onclick="triggerUndoSelected()">
Line 1061: Undo tab     → <button id="btn-undo-selected"         onclick="triggerUndoSelected()">
Line 1062: Undo tab     → <button id="btn-undo-all-matched"      onclick="triggerUndoAllMatched()">

Line 3339: function triggerUndoSelected() {
             const selected = document.querySelectorAll('.archive-select:checked');
             if (selected.length === 0) {
               showError('No archive tasks selected for undo.');
               return;
             }
             ...
           }

## Cause
`.archive-select` checkboxes exist ONLY in Archive tab.
In Undo tab there are NO checkboxes → selected.length === 0 → error.

"Undo Selected" in Undo tab is conceptually wrong:
"Selected" implies checkboxes (Archive tab).

User expects "Undo Selected" in Undo tab to mean
"Undo the tasks matched by the filter".

## Fix (proposed)

### Option A — Remove "Undo Selected" from Undo tab
Delete line 1061 button. Keep only "↩️ Undo All Matched".

### Option B — Rename + repurpose
Line 1061:
BEFORE: <button ... onclick="triggerUndoSelected()">↩️ Undo Selected</button>
AFTER:  <button ... onclick="triggerUndoAllMatched()">↩️ Undo Filtered</button>

Line 1062:
KEEP:   <button ... onclick="triggerUndoAllMatched()">↩️ Undo All Matched</button>

But then both buttons do the same. So Option A is cleaner.

### Option C — New handler for Undo tab
Add `triggerUndoFiltered()` that calls `/api/queue/archive/undo-filter`
with current filter values.

## Recommended
Option A:
- Archive tab: [↩️ Undo Selected]  (uses checkboxes)
- Undo tab:    [↩️ Undo All Matched]  (uses filter)

Remove line 1061.

## Related
- Задача 3 (Undo implementation)
- ERRATA-0023/0024/0025 (frontend bugs)
