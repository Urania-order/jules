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

## Structure

- `.devcontainer/` — Codespace configuration
- `.github/workflows/` — CI (validate + pytest)
- `.jules/` — Task artifacts
- `.co-smos/` — Orchestrator state (local, gitignored)
- `scripts/` — Orchestration and queue scripts (11 scripts)
- `smos/` — Co-SMOS application
- `tests/` — pytest suite (58 tests)
- `AGENTS.md` — Jules instructions (23 sections)
- `pyproject.toml` — Python dependencies (uv)

## Quick start

1. `jules login --no-launch-browser` — login to Jules
2. `uv sync` — install dependencies
3. `./scripts/jules-status.sh` — check current state
4. `./scripts/jules-task.sh "Add a new service for ..."` — dispatch task
5. `./scripts/jules-complete.sh <task-id> <session-id> feat/my-feature` — finalize

## Task Queue

The task queue allows autonomous processing of tasks by the Codespace agent.

- `.jules/queue/pending/` — pending tasks waiting for execution
- `.jules/queue/running/` — current task and active session ID
- `.jules/queue/completed/` — archived execution history

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
| `seed_data.py` | Seed Co-SMOS database with realistic data |
| `validate.sh` | Validate project structure |

## Testing

Run all tests:

`uv run pytest tests/ -q --ignore=tests/test_ecology_service.py --ignore=tests/test_value_service.py --ignore=tests/test_mcp.py`

The three ignored tests target pre-v0.9 APIs and mcp 1.x.

## CI

Every pull request triggers `.github/workflows/ci.yml`.

## License

See LICENSE.
