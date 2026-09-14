# ERRATA-0004: macOS date -Iseconds not supported

- Date: 2026-09-14
- Discovered in: task-20260914-165322
- Severity: LOW
- Category: macOS 10.13 Intel (environment)

## Symptom

    date: illegal option -- I
    usage: date [-jnRu] [-d dst] [-r seconds] ...

## Root cause

macOS 10.13 uses BSD date, not GNU date.
date -Iseconds is GNU-only.

## Fix

Use portable format:

    date -u +"%Y-%m-%dT%H:%M:%SZ"

## Rule for future

Never use GNU-specific date options in scripts.
Use portable date -u +"%Y-%m-%dT%H:%M:%SZ".

## Check before task

- [ ] Scripts use date -u +"%Y-%m-%dT%H:%M:%SZ"?
- [ ] No date -Iseconds?
- [ ] No date -I?
