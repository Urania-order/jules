# ERRATA-0007: numpy 2.x incompatible with macOS 10.13 Intel

- Date: 2026-09-14
- Discovered in: task-20260914-165322
- Severity: MEDIUM
- Category: macOS 10.13 Intel (environment)

## Symptom

    Illegal instruction: 4

When importing numpy.

## Root cause

numpy 2.x requires AVX2, FMA CPU instructions.
macOS 10.13 Intel Macs don't have them.

## Fix

Platform-specific dependency in pyproject.toml:

    "numpy>=2.4.6; sys_platform != 'darwin' or platform_machine != 'x86_64'",
    "numpy<2; sys_platform == 'darwin' and platform_machine == 'x86_64'",

## Rule for future

numpy 2.x -> Linux/Apple Silicon.
numpy 1.x -> macOS 10.13 Intel.

## Check before task

- [ ] pyproject.toml has platform markers?
- [ ] Local numpy version correct?
- [ ] CI numpy version correct?
