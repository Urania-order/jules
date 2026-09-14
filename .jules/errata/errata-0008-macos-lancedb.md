# ERRATA-0008: lancedb no wheel for macOS 10.13 Intel

- Date: 2026-09-14
- Discovered in: task-20260914-165322
- Severity: LOW
- Category: macOS 10.13 Intel (environment)

## Symptom

    error: Distribution lancedb==0.38.0 can't be installed
    because it doesn't have a source distribution or wheel for
    the current platform

## Root cause

lancedb only has wheels for:

- manylinux_2_28_aarch64
- manylinux_2_28_x86_64
- macosx_11_0_arm64
- win_amd64

No wheel for macosx_10_13_x86_64.

## Fix

Remove lancedb from local pyproject.toml (keep for CI).
Or — install manually without it.

## Rule for future

For macOS 10.13 Intel — avoid lancedb.
For CI (Ubuntu) — lancedb works.

## Check before task

- [ ] pyproject.toml has lancedb?
- [ ] If yes — platform marker for macOS?
