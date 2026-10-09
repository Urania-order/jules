# ERRATA-0049: SQLAlchemy legacy declarative_base() import deprecated

## Severity
LOW — dev/test warnings; production runs unaffected; will
resolve with import migration

## Environment

    SQLAlchemy 2.0.52
    Poetry-managed venv (pyproject.toml)

## Symptom (2026-10-09, TASK 37 verification)

    /Users/vagra/jules/smos/core/database.py:21
        MovedIn20Warning: The ``declarative_base()`` function is now
        available as sqlalchemy.orm.declarative_base().
        (deprecated since: 2.0)
        Base = declarative_base()

Observed count: 1 MovedIn20Warning occurrence in test output.

## Cause

Codebase uses SQLAlchemy 1.x import style:

    from sqlalchemy.ext.declarative import declarative_base

SQLAlchemy 2.0 moved `declarative_base` to:

    from sqlalchemy.orm import declarative_base

## Affected files (1 exact occurrence)

    smos/core/database.py:7   (import)
    smos/core/database.py:21  (usage - unchanged)

## Impact

- 1 MovedIn20Warning per test run
- Does NOT affect runtime on SQLAlchemy 2.0 (deprecated, still works)
- Will BREAK when SQLAlchemy 3.0 removes the legacy import path
- Adds noise to CI logs

## Recommended fix

### Simple replacement

    # Before:
    from sqlalchemy.ext.declarative import declarative_base

    # After:
    from sqlalchemy.orm import declarative_base

The `Base = declarative_base()` call is UNCHANGED.

### Verification steps

1. Replace the import line (1 line).
2. Run `./scripts/test.sh`
3. Confirm MovedIn20Warning -> 0
4. All tests pass

## Related

- ERRATA-0048 (SQLAlchemy legacy Query.get()) — CLOSED TASK 37
- TASK 38 (this fix)
- SQLAlchemy 2.0 migration guide:
  https://docs.sqlalchemy.org/en/20/changelog/migration_20.html

## Status
CLOSED — fixed in TASK 38 (task-20261009-XXXXXX)
