# ERRATA-0042: init_db() not called on uvicorn startup — tables missing

## Severity
MEDIUM — first-time users hit "no such table: X" errors

## Symptom (2026-09-23, TASK 04 verification)
$ DATABASE_URL="sqlite:///./smos.db" python3 -c "... constraint ..."
sqlite3.OperationalError: no such table: constraints

But init_db.py IS correct:
- line 12: from smos.models.constraint import Constraint, ConstraintType, ConstraintStatus
- init_db() calls Base.metadata.create_all()
- if __name__ == "__main__": init_db()

## Cause
- init_db() runs ONLY when invoked as: python3 -m smos.core.init_db
- uvicorn startup does NOT call init_db()
- smos/api/main.py lifespan does NOT call init_db()
- New installs have no tables

## Impact
- New dev: first DB call fails with "no such table"
- Manual step required but undocumented

## Workaround (VERIFIED 2026-09-23)
    cd ~/jules
    source .venv/bin/activate
    DATABASE_URL="sqlite:///./smos.db" python3 -m smos.core.init_db
    # Output: Database tables created.
    # Result: 49 tables in smos.db (including constraints, contexts, phenomena)

## Fix (v1.4)
1. In smos/api/main.py lifespan:
    @contextlib.asynccontextmanager
    async def lifespan(app):
        from smos.core.init_db import init_db
        init_db()   # idempotent (create_all safe)
        ...
2. Or: scripts/co-smos.sh → call init_db before uvicorn
3. Document in README: "First run: python3 -m smos.core.init_db"

## Related
- TASK 04 (Constraint model)
- ERRATA-0041 (DATABASE_URL default = PostgreSQL)

## Status
OPEN — needs v1.4
