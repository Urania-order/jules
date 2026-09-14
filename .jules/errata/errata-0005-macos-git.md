# ERRATA-0005: git branch --show-current not supported

- Date: 2026-09-14
- Discovered in: task-20260914-165322
- Severity: LOW
- Category: macOS 10.13 Intel (environment)

## Symptom

    error: unknown option `show-current'

## Root cause

macOS 10.13 ships Git 2.17.
git branch --show-current added in Git 2.22.

## Fix

Use portable command:

    git rev-parse --abbrev-ref HEAD

## Rule for future

Never use git branch --show-current in scripts.
Use git rev-parse --abbrev-ref HEAD.

## Check before task

- [ ] Scripts use git rev-parse --abbrev-ref HEAD?
- [ ] No git branch --show-current?
