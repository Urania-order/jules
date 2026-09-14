# Architectural Decision Record: ADR-0007 (Control Room v0.9 Inspection & Design)

- **Date:** 2026-09-14
- **Task ID:** task-20260914-165322
- **Title:** Co-SMOS Control Room v0.9 Architecture and Web Integration Map

## Context
Co-SMOS ecosystem relies on 15 shell scripts, FastAPI backend (`smos/api/main.py`), and file-based queue subsystems (`.jules/queue/{pending,running,completed,proposed,deferred}`).
To transition from a CLI-only orchestrator to a Web Control Room without breaking existing CLI scripts or allowing Frontend to execute raw shell commands directly, we design a layered architecture.

## System Subsystems Analyzed
1. **Shell Scripts (`scripts/`)**:
   - `jules-task.sh`, `jules-complete.sh`, `jules-queue-add.sh`, `jules-queue-runner.sh`, `jules-queue-propose.sh`, `jules-queue-review.sh`, `jules-queue-status.sh`, `jules-queue-clear.sh`, `validate.sh`, `jules-status.sh`, `jules-recover.sh`, `jules-replay.sh`, `jules-review.sh`.
   - Must remain fully functional and uncompromised.
2. **Queue Directories (`.jules/queue/`)**:
   - Stores task JSONs in `pending/`, `running/`, `completed/`, `proposed/`, `deferred/`.
3. **Core Subsystem (`smos/core/`)**:
   - Domain logic for tasks (`task.py`), queue management (`queue.py`), proposals lifecycle (`proposals.py`), events/history (`events.py`), and system state (`state.py`).
4. **Adapter Layer (`smos/adapters/jules_cli.py`)**:
   - `JulesCLIAdapter` wraps execution of shell scripts using safe `subprocess.run([...])` without `shell=True`.
5. **API Layer (`smos/api/main.py`)**:
   - REST API endpoints serving system status, tasks, queue, proposals, and events. Structured error responses with exit codes.
6. **Frontend Web Interface (`frontend/index.html`)**:
   - Vanilla HTML+CSS+JS single-page web app consuming the REST API. Auto-refresh, responsive layout, task creation, queue reordering (READY/PENDING), proposals management, events log, and task history view.

## Integration Map
```
[ Frontend Web UI ]
       │  (REST / JSON API)
       ▼
[ FastAPI (smos/api/main.py) ]
       │
       ├────────────────────────┐
       ▼                        ▼
[ Core Subsystems ]      [ Adapter Layer ]
  - task.py                (JulesCLIAdapter)
  - queue.py                    │
  - proposals.py                │ (subprocess.run without shell=True)
  - events.py                   ▼
  - state.py            [ Existing Shell Scripts ]
```

## Status & Lifecycle States
Tasks support the following canonical statuses:
- `PENDING`: Enqueued in `pending/`, waiting for execution.
- `READY`: Ready to be picked up or reordered in queue.
- `RUNNING`: Currently in `running/`.
- `REVIEW`: Awaiting review or completion verification.
- `ACCEPTED`: Proposal accepted or task marked accepted.
- `COMPLETED`: Finished and archived in `completed/`.
- `BLOCKED`: Dependency or execution blocked.
- `FAILED`: Failed with error/exit code.
- `CANCELLED`: Explicitly cancelled.
- `DEFERRED`: Moved to `deferred/` for later consideration.

## Consequences
- CLI workflows and scripts remain 100% backward compatible.
- Web UI cannot execute arbitrary shell commands; it communicates exclusively through structured API endpoints.
- Subprocess invocations use strict argument lists (`shell=False`) to avoid shell injection vulnerabilities.
