# ERRATA-0012: Jules still modifies .jules/queue/ despite Do NOT modify

## Symptom
Task task-20260915-205427 was explicitly instructed:

    Do NOT modify:
    - .co-smos/*
    - .jules/tasks/*
    - .jules/results/*
    - .jules/queue/*

The session report still shows:

    Updated
    .jules/queue/completed/task-20260915-175627-5890.json
    .jules/queue/pending/task-20260915-175625-9436.json
    and 4 more

Jules reported STATUS: SUCCESS with CHANGES: None, but the
session log shows .jules/queue/* files were updated in the VM.

## Cause
Hypotheses:
1. The prompt lists forbidden paths but does not explicitly
   say "if you are about to modify .jules/queue/, STOP".
2. Jules treats .jules/queue/ as runtime state, not as a
   file modification, and therefore considers updating it
   as part of its normal workflow.
3. The prompt block may be too passive — a bullet list is
   weaker than an imperative prohibition.
4. Jules may update the queue automatically as part of its
   orchestration, regardless of the prompt.

## Fix
1. Strengthen the prompt wording. Replace the passive list
   with an explicit imperative:

     You MUST NOT modify any file under:
     .co-smos/, .jules/tasks/, .jules/results/, .jules/queue/.
     If you find yourself about to modify any of these,
     STOP immediately and report the situation.
     Treat these directories as READ-ONLY.

2. After each pull, verify with:

     git diff --name-only

   that no file under .jules/queue/ was changed. If it was,
   record a new errata.

3. Add a post-pull check in jules-complete.sh:

     if git diff --name-only | grep -q '^\.jules/queue/'; then
       echo "WARNING: Jules modified .jules/queue/ despite ban"
     fi

4. Consider whether .jules/queue/ should be gitignored
   entirely (it is runtime state, not history).

## Prevention
- Use imperative, explicit language in the prompt.
- Verify after every pull that forbidden paths are untouched.
- Record any violation as a new errata.
- If violations persist, escalate: either
  (a) gitignore .jules/queue/ completely, or
  (b) accept that Jules will touch it and handle it
      in the orchestrator.

## Related
- ERRATA-0010: Jules modified .jules/queue/ before §16 existed.
- This errata shows the ban alone is not sufficient.
