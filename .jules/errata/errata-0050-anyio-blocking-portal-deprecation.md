# ERRATA-0050: anyio.abc.BlockingPortal DeprecationWarning (third-party)

## Severity
INFO — third-party warning; NOT our code; not actionable within Co-SMOS

## Symptom (2026-10-09, TASK 37 verification)

    /Users/vagra/jules/.venv/lib/python3.11/site-packages/starlette/testclient.py:53
        DeprecationWarning: The anyio.abc.BlockingPortal alias is
        deprecated, use anyio.from_thread.BlockingPortal instead.

Occurrences: 4 in test output.

## Cause

starlette.testclient.py uses anyio.abc.BlockingPortal, which anyio
deprecated in favour of anyio.from_thread.BlockingPortal.

Third-party; not in Co-SMOS codebase.

## Impact

- 4 DeprecationWarning occurrences per test run
- Does NOT affect runtime
- NO action possible in Co-SMOS code
- Will resolve when starlette updates its import

## Recommended action (out of Co-SMOS scope)

Option 1 — Upgrade starlette when fixed version available.
Option 2 — Pin anyio to pre-deprecation version if needed.
Option 3 — Add pytest filterwarnings (cosmetic):

    [tool.pytest.ini_options]
    filterwarnings = [
        "ignore::DeprecationWarning:starlette.testclient",
    ]

Optional, cosmetic. Do NOT add pre-emptively.

## Related

- TASK 37 verification log
- starlette upstream issue tracker

## Status
INFO — third-party, not actionable within Co-SMOS
