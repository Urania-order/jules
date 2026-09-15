# ERRATA-0013: Jules marks deliberate no-op sessions as Failed

## Symptom
Session 4836481793525787595 (task-20260915-205427) was a
deliberate no-op test:

  "Test: verify Do NOT modify block propagates.
   Do not edit any files. Report status only."

Jules complied and reported STATUS: SUCCESS with CHANGES: None.

However, `jules remote list --session` shows:

  4836481793525787595  ...  Status: Failed

Meanwhile, .co-smos/state.json correctly records:

  result: "no-op"

## Cause
Jules CLI appears to mark a session as Failed when the remote
VM produces no diff (no files changed). It cannot distinguish
between:
  (a) a deliberate no-op (task instructed "do not edit files")
  (b) a genuine failure that produced no output

## Fix
1. Do not treat Jules session status "Failed" as authoritative.
2. Trust .co-smos/state.json `result` field instead:
   - "applied"   — patch was applied
   - "no-op"     — no diff, deliberate or benign
   - "error"     — pull reported a real error
3. jules-complete.sh already classifies results independently
   of Jules session status.

## Prevention
- When reading session status, check whether the task was
  explicitly a no-op.
- Prefer .co-smos/state.json over Jules session status.
- Record this behavior so future agents do not panic.

## Related
- ERRATA-0009: "No diff found in the remote VM"
- Both describe the same class of no-op sessions.
