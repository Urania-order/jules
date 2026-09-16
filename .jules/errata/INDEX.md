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

### Process / Orchestration

- ERRATA-0017 — test_cli_adapter.py writes to real .jules/queue/ (MEDIUM)
- ERRATA-0016 — jules-complete.sh is not idempotent (MEDIUM)
- ERRATA-0015 — Post-pull check misses untracked forbidden files (MEDIUM)
- ERRATA-0014 — jules-queue-runner.sh can auto-start tasks (MEDIUM)
- ERRATA-0013 — Jules marks deliberate no-op sessions as Failed (LOW)
- ERRATA-0009 — Jules returns "No diff found in the remote VM" (MEDIUM)
- ERRATA-0010 — Jules modified .jules/queue/ before §16 existed (MEDIUM)
- ERRATA-0011 — Orphan Jules sessions: reported SUCCESS, no artifacts (HIGH)
- ERRATA-0012 — Jules still modifies .jules/queue/ despite Do NOT modify (MEDIUM)

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
| 0009 | MEDIUM | Process | MITIGATED (documented, jules-complete.sh handles) |
| 0010 | MEDIUM | Process | MITIGATED (§16 + FORBIDDEN PATHS) |
| 0011 | HIGH | Process | MITIGATED (jules-complete.sh introduced) |
| 0012 | MEDIUM | Process | MITIGATED (imperative wording + post-pull check) |
| 0013 | LOW | Process | DOCUMENTED |
| 0014 | MEDIUM | Process | MITIGATED |
| 0015 | MEDIUM | Process | MITIGATED (auto-move in jules-complete.sh) |
| 0016 | MEDIUM | Process | MITIGATED (idempotency check) |
| 0017 | MEDIUM | Process | FIXED (test isolation, commit 8223f1b) |

## Files

- [ERRATA-0001](errata-0001-port-mismatch.md) — Frontend API_BASE mismatch
- [ERRATA-0002](errata-0002-cors-incomplete.md) — CORS middleware missing
- [ERRATA-0003](errata-0003-test-edge-cases.md) — Test edge cases ignored
- [ERRATA-0004](errata-0004-macos-date.md) — date -Iseconds not supported
- [ERRATA-0005](errata-0005-macos-git.md) — git branch --show-current not supported
- [ERRATA-0006](errata-0006-macos-path.md) — NVM PATH not in scripts
- [ERRATA-0007](errata-0007-macos-numpy.md) — numpy 2.x incompatible
- [ERRATA-0008](errata-0008-macos-lancedb.md) — lancedb no wheel
- [ERRATA-0009](errata-0009-no-diff-remote-vm.md) — Jules returns "No diff found in the remote VM"
- [ERRATA-0010](errata-0010-jules-modified-forbidden-paths.md) — Jules modified .jules/queue/ before §16 existed
- [ERRATA-0011](errata-0011-orphan-jules-sessions.md) — Orphan Jules sessions: reported SUCCESS, no artifacts in repo
- [ERRATA-0012](errata-0012-jules-ignores-queue-ban.md) — Jules still modifies .jules/queue/ despite Do NOT modify
- [ERRATA-0013](errata-0013-jules-marks-noop-as-failed.md) — Jules marks deliberate no-op sessions as Failed
- [ERRATA-0014](errata-0014-queue-runner-autostart.md) — jules-queue-runner.sh can auto-start tasks
- [ERRATA-0015](errata-0015-untracked-forbidden.md) — Post-pull check misses untracked forbidden files
- [ERRATA-0016](errata-0016-jules-complete-not-idempotent.md) — jules-complete.sh is not idempotent
- [ERRATA-0017](errata-0017-test-writes-real-queue.md) — test_cli_adapter.py writes to real .jules/queue/

## Usage

Before starting a task:

1. Read this INDEX
2. Read relevant errata files
3. Check your plan against known mistakes
4. If about to repeat a mistake — STOP and use the documented fix

After completing a task:

1. If you made a NEW mistake — create a new errata file
2. Update this INDEX (categories, summary table, files list)
3. Commit
