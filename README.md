# jules — Co-SMOS development environment

Experimental AI development environment where **GitHub Codespaces**
acts as the workspace and **Jules** (Google's AI agent) acts as an
autonomous software engineering agent.

This repository is the **working** copy. For the template, see
[Urania-order/jules-codespace](https://github.com/Urania-order/jules-codespace).

## What is Co-SMOS?

Co-SMOS (Cooperative Semantic Memory Operating System) is a living
ecosystem for the cooperative evolution of knowledge between humans
and AI.

## Control Room v0.9

Co-SMOS Control Room v0.9 provides a Web Control Room interface over FastAPI:

```bash
# Start Co-SMOS Web Control Room (default port 8080)
./scripts/co-smos.sh
```

Navigate to `http://localhost:8080` to access the Control Room UI.

### Web Control Room Features
- **Dashboard & System Status**: Live statistics and active queue runner triggers.
- **Queue Management**: Drag-and-drop reordering for pending/ready tasks.
- **Proposals Review**: Human review interface to accept, defer, or reject proposals.
- **Task Details & History**: View task state history and state transition logs.
- **Event Stream**: Live system-wide event logging.

## Structure

- `.devcontainer/` — Codespace configuration
- `.github/workflows/` — CI (validate + pytest)
- `.jules/` — Task artifacts
- `.co-smos/` — Orchestrator state (local, gitignored)
- `frontend/` — Co-SMOS Web Control Room single-page web app
- `scripts/` — Orchestration, queue, proposals, and control room launcher scripts (15 scripts)
- `smos/` — Co-SMOS application core, services, adapters, and REST API
- `tests/` — pytest suite (90+ tests)
- `AGENTS.md` — Jules instructions (25 sections)
- `pyproject.toml` — Python dependencies (uv)

## Quick start

1. `jules login --no-launch-browser` — login to Jules
2. `uv sync` — install dependencies
3. `./scripts/co-smos.sh` — start Web Control Room on port 8080
4. `./scripts/jules-status.sh` — check current state
5. `./scripts/jules-task.sh "Add a new service for ..."` — dispatch task
6. `./scripts/jules-complete.sh <task-id> <session-id> feat/my-feature` — finalize

## Local Development Setup

### First time
```bash
git clone <repo-url> jules
cd jules
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m smos.core.init_db
uvicorn smos.api.main:app --host 0.0.0.0 --port 8080
```

init_db is also called automatically on startup (idempotent).

### PostgreSQL (production)
Edit .env: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smos`
Ensure PostgreSQL is running; run: `createdb smos`

## Task Queue

The task queue allows autonomous processing of tasks by the Codespace agent.

- `.jules/queue/pending/` — pending tasks waiting for execution
- `.jules/queue/running/` — current task and active session ID
- `.jules/queue/completed/` — archived execution history
- `.jules/queue/proposed/` — proposals created by Jules awaiting human review
- `.jules/queue/deferred/` — deferred tasks and proposals

### Queue Usage

```bash
# Add a task to queue with optional priority (default: 5 or normal)
./scripts/jules-queue-add.sh "Refactor memory service" high

# View current queue status
./scripts/jules-queue-status.sh

# Run pending tasks in queue
./scripts/jules-queue-runner.sh --loop

# Clear completed or all queued tasks
./scripts/jules-queue-clear.sh --completed
```

### Task Proposals

Jules proposes 3-5 next steps after completing a task. Proposals remain in `.jules/queue/proposed/` until reviewed by a human operator.

```bash
# Propose a follow-up task
./scripts/jules-queue-propose.sh <source-task-id> "Task description" [priority]

# List proposed tasks (with optional --priority / -p or --source-task / -s filter options)
./scripts/jules-queue-review.sh list
./scripts/jules-queue-review.sh --priority high list
./scripts/jules-queue-review.sh --source-task task-101 list

# Accept proposal (moves it to pending queue)
./scripts/jules-queue-review.sh accept <proposal-id>

# Defer proposal (moves proposal to deferred queue)
./scripts/jules-queue-review.sh defer <proposal-id>

# Reject proposal (removes proposal)
./scripts/jules-queue-review.sh reject <proposal-id>

# Accept or reject all proposals
./scripts/jules-queue-review.sh accept-all
./scripts/jules-queue-review.sh reject-all
```

## Seeding Data

Seed the Co-SMOS database with realistic initial data:

```bash
# Seed database
uv run python scripts/seed_data.py

# Drop and recreate tables before seeding
uv run python scripts/seed_data.py --reset
```

## Orchestration scripts

| Script | Purpose |
|--------|---------|
| `co-smos.sh` | Launch Web Control Room server |
| `jules-task.sh` | Dispatch a new task to Jules |
| `jules-status.sh` | Show current state |
| `jules-replay.sh <task-id>` | Replay full history |
| `jules-review.sh <task-id>` | Review task readiness |
| `jules-recover.sh` | Reset stuck task |
| `jules-complete.sh` | Full completion automation |
| `jules-queue-add.sh` | Add a task to the queue |
| `jules-queue-status.sh` | Show queue status |
| `jules-queue-runner.sh` | Process pending queue tasks |
| `jules-queue-clear.sh` | Clear queue entries |
| `jules-queue-propose.sh` | Propose a new task follow-up |
| `jules-queue-review.sh` | Review, accept, defer, or reject proposals |
| `seed_data.py` | Seed Co-SMOS database with realistic data |
| `validate.sh` | Validate project structure |

## Testing

Run all tests:

`uv run pytest tests/ -v --ignore=tests/test_ecology_service.py --ignore=tests/test_value_service.py --ignore=tests/test_mcp.py`

The three ignored tests target pre-v0.9 APIs and mcp 1.x.

## CI

Every pull request triggers `.github/workflows/ci.yml`.

## License

See LICENSE.
