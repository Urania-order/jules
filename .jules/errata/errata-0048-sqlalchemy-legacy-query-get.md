# ERRATA-0048: SQLAlchemy legacy Query.get() deprecated

## Severity
LOW — dev/test warnings; production runs unaffected; future
SQLAlchemy 3.0 will remove Query.get()

## Environment

    SQLAlchemy 2.0.52
    Poetry-managed venv (pyproject.toml)

## Symptom (2026-10-08, TASK 33-34 verification)

    LegacyAPIWarning: The Query.get() method is considered legacy
    as of the 1.x series of SQLAlchemy and becomes a legacy
    construct in 2.0. The method is now available as Session.get()
    (deprecated since: 2.0)

Observed count: 8 LegacyAPIWarning occurrences in test output.
Underlying occurrences: 17 code sites (some tests do not trigger
all sites; pytest reports unique locations).

## Cause

Codebase uses SQLAlchemy 1.x style:

    self.db.query(Model).get(id)

SQLAlchemy 2.0 deprecated `Query.get()` in favour of:

    self.db.get(Model, id)

## Affected files (17 exact occurrences)

### Services (13)

    smos/services/evolution_service.py:30, 81, 96, 118
    smos/services/recipe_service.py:69, 84
    smos/services/ecology_engine.py:15, 20
    smos/services/value_ecology_service.py:21
    smos/services/timeline_service.py:39
    smos/services/execution_service.py:21
    smos/services/community_service.py:18
    smos/services/coevolution_service.py:37

### Tests (4)

    tests/test_context_exposure.py:241, 242, 255
    tests/test_multi_role_resonance.py:218

## Impact

- 8 LegacyAPIWarning occurrences on every test run
- Does NOT affect runtime on SQLAlchemy 2.0 (deprecated, still works)
- Will BREAK when SQLAlchemy 3.0 removes Query.get()
- Adds noise to CI logs
- Masks other warnings

## Recommended fix (future dedicated TASK)

### Simple replacement

    # Before:
    self.db.query(Model).get(id)

    # After:
    self.db.get(Model, id)

Applicable for all 17 occurrences (simple `.get(id)` at
end of `.query(Model)` chain).

### Verification steps

1. Replace 17 occurrences:
   - 13 in services
   - 4 in tests
2. Run `./scripts/test.sh`
3. Confirm 8 LegacyAPIWarning -> 0
4. Run full suite: all tests pass

### Optional: pytest filter (temporary, while migration in progress)

Add to pyproject.toml `[tool.pytest.ini_options]`:

    filterwarnings = [
        "ignore::sqlalchemy.exc.LegacyAPIWarning",
    ]

This suppresses warnings during the migration. Do NOT use as
permanent solution — the deprecated API will be removed in
SQLAlchemy 3.0.

### Bonus (same TASK, if clean)

While fixing `.get()`, check for other SQLAlchemy 1.x patterns:

    grep -rn "\.query(.*)\." smos/ tests/ --include="*.py" | \
      grep -v "__pycache__" | \
      grep -v "\.filter\|\.first\|\.all\|\.count\|\.delete\|\.update"

## Why not fixed during TASK 28-35

- Semantic layer (TASK 28-35) is READ-ONLY with respect to
  canonical services.
- TASK 35 explicitly forbids modifying TASK 01-34 files.
- Cross-cutting change touches 8 services + 2 test files;
  needs its own TASK with dedicated regression tests.

## Related

- TASK 28-34 verification logs
- SQLAlchemy 2.0 migration guide:
  https://docs.sqlalchemy.org/en/20/changelog/migration_20.html

## Status
OPEN — needs future dedicated TASK
