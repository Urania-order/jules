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
- `scripts/` — Orchestration scripts (8 scripts)
- `smos/` — Co-SMOS application
- `tests/` — pytest suite (52 tests)
- `AGENTS.md` — Jules instructions (22 sections)
- `pyproject.toml` — Python dependencies (uv)

## Quick start

1. `jules login --no-launch-browser` — login to Jules
2. `uv sync` — install dependencies
3. `./scripts/jules-status.sh` — check current state
4. `./scripts/jules-task.sh "Add a new service for ..."` — dispatch task
5. `./scripts/jules-complete.sh <task-id> <session-id> feat/my-feature` — finalize

## Orchestration scripts

| Script | Purpose |
|--------|---------|
| `jules-task.sh` | Dispatch a new task to Jules |
| `jules-status.sh` | Show current state |
| `jules-replay.sh <task-id>` | Replay full history |
| `jules-review.sh <task-id>` | Review task readiness |
| `jules-recover.sh` | Reset stuck task |
| `jules-complete.sh` | Full completion automation |
| `validate.sh` | Validate project structure |

## Testing

Run all tests:

`uv run pytest tests/ -q --ignore=tests/test_ecology_service.py --ignore=tests/test_value_service.py --ignore=tests/test_mcp.py`

The three ignored tests target pre-v0.9 APIs and mcp 1.x.

## CI

Every pull request triggers `.github/workflows/ci.yml`.

## License

See LICENSE.
