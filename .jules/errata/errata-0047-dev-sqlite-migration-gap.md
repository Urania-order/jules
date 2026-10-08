# ERRATA-0047: SQLAlchemy model change not reflected in existing dev SQLite

## Severity
MEDIUM — dev environment; existing smos.db schema drifts from model

## Symptom (2026-10-08, TASK 32 verification)
$ DATABASE_URL="sqlite:///./smos.db" python3 -c "..."
sqlite3.OperationalError: table recipes has no column named provenance
[SQL: INSERT INTO recipes (..., provenance) VALUES (...)]

## Cause
- TASK 32 added Recipe.provenance = Column(JSON, default=dict)
- Base.metadata.create_all() creates MISSING TABLES, NOT MISSING COLUMNS
- Existing smos.db has old recipes schema (no provenance column)
- Tests pass (in-memory SQLite / fresh DB)
- Local dev DB drifts silently

## Why we knew
TASK 32 STEP 0 item 2.9 anticipated this:
"create_all() is NOT a general migration mechanism for an
existing database. It works for SQLite dev/test."

Jules correctly documented the gap in FINAL REPORT, but the
dev migration was not automated.

## Impact
- Existing dev smos.db cannot be used for TASK 32 flows
- Human must manually ALTER TABLE or reset DB
- Recurring for every new Column() (TASK 28 SemanticIndexEntry
  worked because it was a NEW table — create_all creates tables)

## Workaround (immediate)
    cd ~/jules
    cp smos.db smos.db.bak.$(date +%s)
    DATABASE_URL="sqlite:///./smos.db" python3 -c "
    from sqlalchemy import text
    from smos.core.database import engine
    with engine.connect() as conn:
        result = conn.execute(text('PRAGMA table_info(recipes)'))
        cols = [row[1] for row in result]
        if 'provenance' not in cols:
            conn.execute(text('ALTER TABLE recipes ADD COLUMN provenance JSON'))
            conn.commit()
    "

Or (dev, no data to keep):
    rm smos.db
    DATABASE_URL="sqlite:///./smos.db" python3 -m smos.core.init_db

## Fix (future TASK)
1. Add scripts/migrate-dev-db.py:
   - Compare model columns vs actual DB columns
   - ALTER TABLE ADD COLUMN for missing columns (SQLite)
   - Document unsupported cases (renames, type changes)
2. Add scripts/setup-dev.sh that runs migration on startup
3. Consider Alembic for production PostgreSQL
4. Document in README: "run migrate-dev-db.py after git pull"

## Related
- TASK 32 (task-20261008-130309)
- TASK 28 (SemanticIndexEntry — worked because new table)

## Status
OPEN — needs future TASK
