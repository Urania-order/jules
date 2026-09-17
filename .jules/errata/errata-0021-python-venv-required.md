# ERRATA-0021: Must activate .venv before pytest

## Symptom
`pip install httpx` reports "Requirement already satisfied" (Python 3.12),
but `pytest tests/` fails with:
  RuntimeError: The starlette.testclient module requires the httpx package
  to be installed.

Classic "I installed it but pytest cannot see it".

## Cause
Multiple Python environments on the machine:
- Anaconda base:  /opt/anaconda3/bin/python (3.11)
- System Python:  /Library/Frameworks/Python.framework/.../3.12/bin/python
- Project venv:   /Users/vagra/jules/.venv  (python 3.11, has httpx + fastapi + pytest)

Without activating `.venv`:
  pip    -> Python 3.12     (httpx installed HERE)
  pytest -> Anaconda 3.11   (httpx NOT installed HERE)

Two different site-packages. `pip install` and `pytest` see different worlds.

## Fix (the one that works)
    cd ~/jules
    source .venv/bin/activate
    pytest tests/

Prompt shows `(smos)` — that means `.venv` is active.
All 220 tests pass (verified 2026-09-18).

## Why `pip install -r requirements.txt` fails
There is NO `requirements.txt` in this repo.
Dependencies are baked into `.venv` already.
Do NOT try to reinstall requirements — just activate `.venv`.

## Prevention
1. Add to AGENTS.md / README:
   "Before running pytest: `cd ~/jules && source .venv/bin/activate`"
2. Add `scripts/test.sh`:

       #!/usr/bin/env bash
       set -e
       cd "$(dirname "$0")/.."
       if [ -z "$VIRTUAL_ENV" ]; then
         echo "Activating .venv..."
         source .venv/bin/activate
       fi
       python -m pytest tests/ "$@"

3. Add sanity check to CI: fail if `which pytest` is not under `.venv`.
4. Never use bare `pip` / `pytest` without `.venv` activated.

## Related
- Задача 3 (Undo) — pytest blocked until `.venv` activated
- Задача 4 (Scheduled) — must activate `.venv` before pytest
- ERRATA-0019 — Jules session Description
- ERRATA-0020 — No task-level reset

## Status
RESOLVED — activate `.venv`, then `pytest tests/` passes 220/220.
