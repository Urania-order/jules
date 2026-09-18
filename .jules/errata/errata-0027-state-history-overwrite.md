# ERRATA-0027: state.json history overwritten by Reset

## Severity
HIGH — data loss in state.json

## Symptom
After scheduled "Nightly Reset" fired (02:00:11), 7 completed tasks
were removed from `.co-smos/state.json["history"]`.

After later Undo All Matched (05:25:43), history contains ONLY
7 new pending tasks (no session_id, no result).

## Cause — exact location

smos/core/queue_reset.py:318-320
    if isinstance(state_data.get("history"), list):
        state_data["history"] = [
            t for t in state_data["history"]
            if not (isinstance(t, dict) and t.get("id") in removed_task_ids)
        ]

`history` is supposed to be AUDIT LOG (append-only).
But reset FILTERS it, removing any task whose id was in the reset scope.

## Correct pattern (compare)
scripts/jules-complete.sh:265
    state["history"].append(completed)   ← append-only ✅

## Impact
- Co-SMOS v1.1 history (Задачі 1-8) LOST from state.json
- No audit of past applied tasks
- Format changed: old tasks had session_id, result, timestamps

## Fix (proposed)
1. Remove the filter at lines 318-320.
   History must NEVER be filtered by reset.
2. If deduplication is needed (same id re-added), handle at
   append time in jules-complete.sh, not at reset time.
3. Optionally APPEND a reset event:
       state_data["history"].append({
         "action": "reset",
         "timestamp": now,
         "scope": scope,
         "moved": total_moved,
       })
4. Add test: after reset, history length >= previous length
5. Add test: after reset, completed tasks still present

## Workaround (immediate)
git checkout -- .co-smos/state.json   # restore previous state

## Related
- Задача 1 (Reset + Archive + WHY)
- smos/core/queue_reset.py:318-320
- ERRATA-0028 (schedule fired unexpectedly)

## Status
OPEN — needs Задача 10
