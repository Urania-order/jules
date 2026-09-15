# Jules Errata Index

Known mistakes and rules to avoid them.

**Jules MUST check this file before every task.**

## Categories

### Frontend/API Integration

- ERRATA-0001 — Frontend API_BASE mismatch (HIGH)
- ERRATA-0002 — CORS middleware missing (HIGH)

### Testing

- ERRATA-0003 — Test edge cases ignored (MEDIUM)

### macOS 10.13 Intel (environment-specific)

- ERRATA-0004 — date -Iseconds not supported (LOW)
- ERRATA-0005 — git branch --show-current not supported (LOW)
- ERRATA-0006 — NVM PATH not in scripts (MEDIUM)
- ERRATA-0007 — numpy 2.x incompatible (MEDIUM)
- ERRATA-0008 — lancedb no wheel (LOW)

## Summary

| ID | Severity | Category | Status |
|----|----------|----------|--------|
| 0001 | HIGH | Frontend/API | FIXED |
| 0002 | HIGH | Frontend/API | FIXED |
| 0003 | MEDIUM | Testing | FIXED |
| 0004 | LOW | macOS | FIXED |
| 0005 | LOW | macOS | FIXED |
| 0006 | MEDIUM | macOS | FIXED |
| 0007 | MEDIUM | macOS | FIXED |
| 0008 | LOW | macOS | FIXED |

## Usage

Before starting a task:

1. Read this INDEX
2. Read relevant errata files
3. Check your plan against known mistakes
4. If about to repeat a mistake — STOP and use the documented fix

After completing a task:

1. If you made a NEW mistake — create a new errata file
2. Update this INDEX
3. Commit

- [ERRATA-0009](errata-0009-no-diff-remote-vm.md) — Jules returns "No diff found in the remote VM"

- [ERRATA-0012](errata-0012-jules-ignores-queue-ban.md) — Jules still modifies .jules/queue/ despite Do NOT modify
