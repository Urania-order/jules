# Jules Co-SMOS — Agent Instructions

## 1. Project identity

Repository:

Urania-order/jules-codespace

Project role:

This repository is an experimental AI development environment
where GitHub Codespaces acts as the workspace and Jules acts
as an autonomous software engineering agent.

The long-term goal is to evolve this environment toward
Co-SMOS — a cooperative multi-agent development system.

---

# 2. Core principle

Jules is an autonomous implementation agent.

Codespace is the controlled development environment.

GitHub is the persistent source of truth.

Never treat temporary workspace state as the authoritative
project state.

---

# 3. Safety rules

Never modify `main` directly.

Every implementation task must work on a dedicated branch.

Never delete existing functionality unless explicitly requested.

Never replace an existing architecture merely because another
architecture appears simpler.

Preserve backward compatibility whenever reasonably possible.

Do not introduce secrets into source code.

Do not commit:

- API keys
- passwords
- tokens
- private credentials
- `.env` files containing secrets

---

# 4. Required workflow

For every non-trivial task use:

    ANALYZE
       ↓
    PLAN
       ↓
    IMPLEMENT
       ↓
    TEST
       ↓
    REVIEW
       ↓
    REPORT

Do not immediately start changing files before understanding
the existing project.

---

# 5. Analysis

Before modifying the project:

1. Inspect repository structure.
2. Inspect package configuration.
3. Inspect existing scripts.
4. Inspect existing tests.
5. Identify dependencies.
6. Identify possible compatibility problems.
7. Identify files that will be modified.

For non-trivial tasks create an analysis record in:

    .jules/tasks/

---

# 6. Planning

Before implementation describe:

- objective
- affected files
- architecture changes
- dependencies
- risks
- testing strategy

Avoid unnecessary dependencies.

Prefer existing project dependencies.

---

# 7. Implementation

Make the smallest coherent change that solves the task.

Keep modules focused.

Do not duplicate existing functionality.

Prefer reusable functions over large monolithic scripts.

Use clear names.

Add comments only where the reason is not obvious from code.

---

# 8. Testing

Before reporting completion:

1. Run existing tests.
2. Run linting if available.
3. Run build if available.
4. Test the modified functionality.

If a test cannot be executed, explicitly report why.

Never claim a test passed if it was not actually executed.

---

# 9. Failure handling

If implementation fails:

DO NOT hide the failure.

Record:

- error
- probable cause
- attempted solution
- current state
- recommended next action

Store the record in:

    .jules/results/

---

# 10. Git discipline

Use descriptive commits.

Preferred format:

    feat:
    fix:
    refactor:
    test:
    docs:
    chore:

Example:

    feat: add Jules task orchestration

Never rewrite history unless explicitly requested.

Never force-push.

---

# 11. Co-SMOS state

The file:

    .co-smos/state.json

contains the current orchestration state.

When an autonomous task starts, update:

    active_task

When it finishes:

    active_task = null
    last_task = completed task

Important decisions should be recorded in:

    .jules/history/

---

# 12. Task reproducibility

Every important task must be reproducible.

A task record should contain:

- task ID
- date/time
- original request
- branch
- files changed
- tests executed
- result
- important decisions

The goal is that a future agent can reconstruct
WHY a change was made, not merely WHAT was changed.

---

# 13. Autonomous behavior

Jules may:

- inspect files
- analyze architecture
- modify code
- add tests
- run tests
- create commits
- prepare pull requests

Jules must NOT:

- expose secrets
- destroy unrelated code
- silently change project goals
- claim success without verification

---

# 14. Communication style

Reports should be concise but technically precise.

Use:

    STATUS
    CHANGES
    TESTS
    RISKS
    NEXT STEP

---

# 15. Long-term architecture

The project is expected to evolve toward:

    Human
       ↓
    Co-SMOS
       ↓
    Task Router
       ↓
    ┌─────────────┬─────────────┐
    ↓             ↓             ↓
   Jules        other AI      tools
    ↓             ↓             ↓
    └─────────────┴─────────────┘
                  ↓
               GitHub
                  ↓
               Review

Do not prematurely implement the entire architecture.

Build it incrementally.

---

# 16. Project subsystems

This repository contains two layers.

## 16.1 Orchestration layer (Co-SMOS)

Files:

- `AGENTS.md` — this document
- `scripts/jules-task.sh` — task dispatcher
- `scripts/validate.sh` — project validator
- `.co-smos/state.json` — orchestrator state
- `.jules/tasks/` — task cards
- `.jules/results/` — session logs
- `.jules/history/` — ADRs and decisions

This layer is managed by humans and the orchestrator.
Jules MUST NOT modify it (see §17).

## 16.2 Application layer (smos/)

Files:

- `smos/api/` — FastAPI application
- `smos/core/` — database, interfaces, MCP server, security
- `smos/models/` — SQLAlchemy models
- `smos/services/` — domain services
- `tests/` — pytest test suite
- `pyproject.toml`, `uv.lock` — dependencies

This is where Jules does its work.

### Core interfaces

All subsystems implement one or both of:

- `Evolvable` — entities with a lifecycle
- `Observable` — subsystems that report health metrics

### Key services

- `EcologyEngine` — cluster resonance, propagation, pollination
- `ValueEcologyService` — energy, potential, resonance, diffusion
- `DiscoverySystem` — backward discovery, analogies
- `CommonsService` — Human-AI collaboration layer
- `ObservatoryService` — ecosystem health and quarterly reports

### Legacy modules

Older service names were consolidated in v0.9:

| Legacy | Current |
|--------|---------|
| `ecology_service` | `ecology_engine` |
| `knowledge_ecology_engine` | `ecology_engine` |
| `value_service` | `value_ecology_service` |
| `value_physics_engine` | `value_ecology_service` |
| `discovery_service` | `discovery_system` |

Do not reintroduce legacy names.

---

# 17. Forbidden paths

Jules MUST NOT modify:

- `.co-smos/` — orchestrator state
- `.jules/tasks/` — task cards created by `jules-task.sh`
- `.jules/results/` — session logs created by `jules-task.sh`
- `.jules/history/` — existing ADRs

These paths are managed by the orchestrator and human reviewers.

If a task appears to require changing these files, STOP and report
the conflict instead of modifying them.

Allowed:

- Jules may CREATE a new ADR file in `.jules/history/` when a
  significant architectural decision is made (e.g. `adr-0002-*.md`).
  Jules MUST NOT modify existing ADRs.

---

# 18. Required checks before reporting

Before reporting completion, Jules MUST run:

    ./scripts/validate.sh
    uv run pytest tests/ -v \
        --ignore=tests/test_ecology_service.py \
        --ignore=tests/test_value_service.py \
        --ignore=tests/test_mcp.py

The `--ignore` list exists because these three tests target
pre-v0.9 APIs that no longer exist. They are kept for historical
reference and may be rewritten in the future.

If validation or tests fail:

- DO NOT report success
- Record the failure in `.jules/results/` (append to the session log)
- Report the failure in the STATUS section

Never claim a test passed if it was not actually executed.

---

# 19. Continuous integration

Every pull request triggers a GitHub Actions workflow
(`.github/workflows/ci.yml`).

The workflow runs:

1. `uv sync`
2. `bash scripts/validate.sh`
3. `uv run pytest tests/ -v` (with the same ignore list)

If CI fails, the PR cannot be merged until it passes.

Jules should assume that any change will be validated by CI and
must not merge or bypass checks.

---

# 20. Test conventions

Tests use an in-memory SQLite database provided by
`tests/conftest.py`. The fixture:

- patches `smos.core.database.engine` and `SessionLocal`
- creates all tables via `Base.metadata.create_all`
- provides a `db` fixture for per-test sessions

Because SQLite does not support `pgvector`, the `Vector` column
type is patched to a JSON-serialized `TypeDecorator` when
`DATABASE_URL` starts with `sqlite`.

Consequences:

- Semantic search (`l2_distance`) is not available in tests.
  `api/main.py::search_memory` falls back to text search under SQLite.
- Tests must not depend on pgvector-specific behaviour.

When adding new models:

- Import them in `tests/conftest.py` so `Base.metadata` sees them.
- Use `JSON` (not `Vector`) unless the column is truly a vector.
- Prefer `session.get(Model, id)` over `session.query(Model).get(id)`.

When adding new services:

- Place them in `smos/services/`.
- Add a corresponding `tests/test_<name>.py`.
- If the service observes ecosystem state, implement `Observable`.
- If the service manages lifecycles, implement `Evolvable`.

---

# 21. Contribution flow

Standard flow for a non-trivial change:

1. `./scripts/jules-task.sh "<task>"`
2. Jules works on branch `jules/<task-id>`
3. Jules runs §18 checks
4. Jules reports using §14 format
5. Human reviews the branch and opens a PR
6. CI runs on the PR (§19)
7. Human merges when CI is green

Jules never pushes to `main` directly.

---

# 22. Task automation with jules-complete.sh

After Jules completes a task, use `jules-complete.sh` to automate
the entire completion workflow:

    ./scripts/jules-complete.sh <task-id> <session-id> <branch-name>

Example:

    ./scripts/jules-complete.sh task-20260912-202630 10793142310330324252 feat/observatory-api

The script performs 8 steps:

1. Pull result from Jules (`jules remote pull --apply`)
2. Update `.co-smos/state.json` (active_task → last_task + history)
3. Review task (`jules-review.sh`)
4. Validate project (`validate.sh`)
5. Run tests (`pytest` with ignore list)
6. Create branch, commit changes
7. Push and create PR
8. Wait for CI, prompt to merge

## 22.1 When to use it

Use `jules-complete.sh` for **every** task completed by Jules.
It replaces 8 manual steps with a single command.

## 22.2 CI wait behavior

The script polls `gh pr checks` every 15 seconds, up to 300 seconds
(5 minutes). Three outcomes:

- **passed** — prompts `Merge PR? [y/N]`
- **failed** — exits with error, PR left open
- **timeout** — exits cleanly, PR left open

## 22.3 Manual fallback

If `jules-complete.sh` fails at any step, you can run the steps manually:

    jules remote pull --session <id> --apply
    python3 -c "..."  # update state.json
    ./scripts/jules-review.sh <task-id>
    ./scripts/validate.sh
    uv run pytest tests/ -q --ignore=tests/test_ecology_service.py \
      --ignore=tests/test_value_service.py --ignore=tests/test_mcp.py
    git checkout -b <branch> && git add -A && git commit -m "..."
    git push -u origin <branch>
    gh pr create --fill
    gh pr checks && gh pr merge --squash --admin --delete-branch

---

# 23. Autonomous Task Queue

The Codespace agent processes tasks autonomously via the task queue subsystem.

## 23.1 Queue Structure

- `.jules/queue/pending/` — tasks waiting for execution (sorted by priority and creation time)
- `.jules/queue/running/` — task currently being executed along with its session metadata
- `.jules/queue/completed/` — archived execution records (successful and failed tasks)

## 23.2 Management Scripts

- `scripts/jules-queue-add.sh <task-description> [priority]` — enqueues a new task. Priority can be an integer or text (`high`=10, `normal`=5, `low`=1).
- `scripts/jules-queue-status.sh` — displays the state of pending, running, and completed queues.
- `scripts/jules-queue-runner.sh [--once|--loop] [--dry-run]` — executes queued tasks ordered by highest priority.
- `scripts/jules-queue-clear.sh [--completed|--all]` — clears archived or all task files from the queue.

---

# 24. Task proposals

After completing a task, Jules SHOULD propose 3-5 next steps.

## 24.1 How to propose

Use:

    ./scripts/jules-queue-propose.sh <task-id> "<description>" [priority]

Proposals are stored in `.jules/queue/proposed/` and DO NOT run automatically.

## 24.2 What to propose

Good proposals:
- Related to the completed task
- Small, well-defined (1-2 hours of work)
- Have clear acceptance criteria
- Extend the system in a coherent direction

Bad proposals:
- Vague ("improve everything")
- Huge ("rewrite the entire system")
- Unrelated to the current work
- Duplicate existing functionality

## 24.3 Human review

    ./scripts/jules-queue-review.sh list
    ./scripts/jules-queue-review.sh accept <proposal-id>
    ./scripts/jules-queue-review.sh reject <proposal-id>

Accepted proposals move to `.jules/queue/pending/` and are processed by
the queue runner.

## 24.4 Limits

- Maximum 5 proposals per task
- Priority range: 1-5 (default: 3)

---

# 27. Errata system — avoid repeating mistakes

Before starting any task, Jules MUST:

1. Read .jules/errata/INDEX.md
2. Read relevant errata files
3. Check the plan against known mistakes
4. If about to repeat a mistake — STOP and use documented fix

## 27.1 When to create errata

Create new errata file when:

- You made a mistake that was fixed
- The mistake is likely to repeat
- The fix is documented

DO NOT create errata for:

- One-time typos
- Environment-specific issues that won't repeat
- Trivial errors

## 27.2 After completing a task

If you made a NEW mistake:

1. Create .jules/errata/errata-XXXX-slug.md
2. Update .jules/errata/INDEX.md
3. Commit both files

## 27.3 Before reporting STATUS

In final report, add section:

    ERRATA CHECK
    - Read INDEX.md: yes
    - Relevant errata: ERRATA-0001, ERRATA-0002
    - Checked my plan against them: yes
    - New mistakes made: none / ERRATA-0009

## 27.4 Rules

- Errata is APPEND-ONLY (never delete)
- INDEX.md updated on every new errata
- Each errata has unique ID
- IDs are sequential (0001, 0002, ...)
