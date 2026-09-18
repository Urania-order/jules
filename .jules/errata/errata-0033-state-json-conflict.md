# ERRATA-0033: state.json patch conflict in jules remote pull --apply

## Severity
HIGH — blocks jules-complete.sh for all tasks

## Symptom
`jules-complete.sh` step [2/9] = error:
    Error: Failed to apply patch:
    error: patch failed: .co-smos/state.json:2
    error: .co-smos/state.json: patch does not apply

Result: task result="error", patch not applied.
Observed: v1.2.1, v1.2.3 (multiple times).

## Root cause
1. `.co-smos/state.json` was TRACKED in git
   (due to `!.co-smos/state.json` exception in .gitignore)
2. Dispatch (jules-task.sh) updates state.json with active_task
3. state.json is uncommitted → appears in working tree diff
4. Jules works on snapshot with modified state.json
5. Jules includes state.json in the patch it produces
6. `jules remote pull --apply` tries to apply the whole patch
7. state.json conflicts with HEAD (or local) → patch fails atomically
8. No way to exclude paths (`jules remote pull` has no --exclude)

## Fix (applied)
1. Removed `!.co-smos/state.json` exception from .gitignore
2. `git rm --cached .co-smos/state.json` — untrack
3. Commit: `fa39ad7 chore: untrack state.json`

Result: state.json is now untracked (ignored).
Jules no longer sees it in diff.
`jules remote pull --apply` no longer conflicts.

## Prevention
1. All runtime state (.co-smos/state.json, .jules/queue/*) must be:
   - Untracked (in .gitignore, no ! exception)
   - Never committed
2. Add to AGENTS.md: "Runtime files must not be tracked"
3. If `jules remote pull` gets --exclude in the future — use it.

## Related
- v1.2.1 conflict (task-20260918-225452) — first occurrence
- v1.2.3 conflict (task-20260919-010101) — second occurrence
- scripts/jules-complete.sh step [2/9]
- .gitignore line 25 + exception line 27 (removed)

## Status
FIXED (fa39ad7)
