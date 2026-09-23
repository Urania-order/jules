# ERRATA-0043: Jules writes tests that fail on his own code

## Severity
MEDIUM — CI fails; manual cleanup needed; recurring pattern

## Symptom (2026-09-23, v1.4)
- CI run 35868793937: FAILED
- tests/test_database_config.py::test_env_example_exists — AssertionError
- test asserts Path(".env.example").exists() but file does not exist
- Jules task (task-20260923-132246) added test, but not the file

## Observed instances (recurring)
- v1.2.9 (task-20260920-093029): 3 mock tests fail
- v1.3.2 (task-20260922-200334): 2 mock tests fail
- v1.4   (task-20260923-132246): test_env_example_exists — no .env.example

## Cause (hypothesis)
- Jules follows ТЗ test requirements, but not always artifact (files)
- Test-first approach: writes test, "forgets" to create the file
- Two patterns:
  * Bash mock tests (v1.2.9, v1.3.2) — mock issues
  * File existence test (v1.4) — file not created

## Impact
- CI fails; jules-complete.sh reports "CI FAILED"
- Manual fix needed (create file + commit + push)
- Extra ERRATA

## Fix (process)
1. ТЗ for new files: mention explicitly:
   - "create file X" AND
   - "test file X exists"
2. Review Jules diff: files + tests together before push
3. Pre-flight: run pytest locally before commit
4. jules-complete.sh: if CI fails → log + manual fix; OR auto-revert + retry

## Workaround
    cd ~/jules
    # Create missing file manually (e.g., .env.example)
    git add <file>
    git commit -m "fix: add <file> (missed by Jules)"
    git push origin main

## Related
- v1.2.9, v1.3.2, v1.4
- ERRATA-0040 (Jules bash mock tests)

## Status
OPEN — process guidance
