# ERRATA-0018: `git init -b main` fails on git < 2.28

## Symptom
tests/test_jules_complete_flow.py — 8 tests fail with:
  subprocess.CalledProcessError: Command
  '['git', 'init', '-b', 'main']' returned non-zero exit status 129.
  error: unknown switch `b'

## Cause
`git init -b <branch>` was added in git 2.28 (July 2020).
On older git (2.14 in our environment), the -b flag is unknown.

## Fix
Use a two-step init:
  git init
  git checkout -b main

## Prevention
- When writing tests that init a git repo, use the two-step form.
- Check git version in test setup.
- Related: ERRATA-0005 (git branch --show-current).

## Related
- ERRATA-0005: git branch --show-current not supported.
