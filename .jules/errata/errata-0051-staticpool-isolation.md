# ERRATA-0051: Test DB isolation broken by StaticPool + no rollback

## Severity
HIGH — test results depend on execution order; leakage across tests

## Symptom (2026-10-11, TASK 41 verification + TASK 41 audit)

Full suite:
    FAILED tests/test_four_position_service.py::test_req_3_position_i_represents_present_exists
    assert [5, 25, 101, 2002] == [25, 101]

PDB revealed:
    sample_data["p_core"].id == 11
    Relations with source_id == 11 in DB:
        (5, [2002], 11, 12)   ← leaked from prior test
        (25, [101], 11, 12)   ← sample_data
        (27, [103], 11, 14)   ← sample_data
        (28, [104], 11, 15)   ← sample_data

## Root cause (CONFIRMED by TASK 41 audit)

tests/conftest.py:12-48:

    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # ← shared connection
    )

    db_module.Base.metadata.create_all(bind=_engine)   # ONCE at import

    @pytest.fixture(scope="function")
    def db():
        session = db_module.SessionLocal()
        try:
            yield session
        finally:
            session.close()   # ← NO rollback, NO cleanup

## Mechanism (confirmed)

1. StaticPool holds ONE underlying SQLite in-memory connection
   for the entire pytest process.
2. Tests call db.commit() → rows persist on shared connection.
3. session.close() does NOT roll back committed rows.
4. Auto-increment IDs continue across tests (process-global).
5. Committed rows from earlier tests leak into later tests.
6. When sample_data creates p_core, it receives an auto-increment
   id that may coincide with a phenomenon created by an earlier test.
7. FourPositionService.build_analysis(p_core.id) then matches
   BOTH the current test's relations AND relations from prior
   tests with the same source_id.

## Impact

- Test results depend on execution order
- False positives and false negatives possible
- Full suite can fail even when individual tests pass
- New tests may break unrelated existing tests

## NOT a defect

- FourPositionService combining r.id + r.evidence into
  pos_i["evidence"] IS intentional design
- Contract (four_position_contract.py:44) declares "evidence": [int]
- TASK 41 file is correct — it only revealed the issue
- evidence=[2002] in TASK 41 file is valid

## Recommended fix

Change conftest.py db() fixture to isolate per test:

    @pytest.fixture(scope="function")
    def db():
        connection = _engine.connect()
        transaction = connection.begin()
        session = db_module.SessionLocal(bind=connection)
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
            connection.close()

Alternative: drop_all + create_all per test (slower).

## Related

- TASK 41 audit (task-20261010-234127)
- TASK 41 verification (task-20261010-171436)
- TASK 40 (ADR-0009)
- All existing tests

## Status
OPEN — needs dedicated TASK for conftest fix
