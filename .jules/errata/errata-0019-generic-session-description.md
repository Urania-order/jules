# ERRATA-0019: Jules session Description shows generic text

## Symptom
Almost all sessions in `jules remote list --session` showed:
  You are working inside the repository:https://github.com/Ur…
instead of the task title.

## Cause
`jules remote new` has no --description flag.
Jules uses the FIRST LINE of the prompt as Description.
jules-task.sh started prompt with "You are working inside..."

## Fix
Commit 13a037a: extract TASK_TITLE, place it as first line
of JULES_PROMPT.

## Prevention
- Always put task title as first line of prompt.
- Do not rely on --description (does not exist).
- Verify in TUI after jules-task.sh.
