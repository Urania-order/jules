# Architectural Decision Record: ADR-0004
- **Date:** 2026-09-14
- **Task ID:** task-20260914-012908
- **Title:** Autonomous Task Proposal and Human Review System

## Context
As Co-SMOS evolves toward a cooperative multi-agent development environment, autonomous agents (Jules) need a structured mechanism to propose logical follow-up tasks, bug fixes, or enhancements based on completed tasks. However, to prevent runaway task creation or unintended modifications, proposals must be staged for human review rather than being automatically executed.

## Decisions Made
1. **Directory Structure (`.jules/queue/proposed/`)**:
   - Added `.jules/queue/proposed/` directory alongside `pending`, `running`, and `completed`.
   - Stored proposals as JSON files containing metadata (`id`, `proposed_by`, `source_task`, `description`, `priority`, `status`, `created_at`).

2. **Proposal Management Scripts**:
   - `scripts/jules-queue-propose.sh`: Enables Jules to create structured task proposals tied to a source task ID with configurable priority (1-5, default 3).
   - `scripts/jules-queue-review.sh`: Provides human operators commands to list (`list`), accept (`accept <id>`, `accept-all`), or reject (`reject <id>`, `reject-all`) proposals. Accepting a proposal converts it into a pending queue task (`.jules/queue/pending/task-*.json`).

3. **Validation & Integration**:
   - Integrated `.jules/queue/proposed/` and proposal scripts into `scripts/validate.sh`.
   - Updated system documentation in `AGENTS.md` (§24) and `README.md`.

## Consequences
- Jules can suggest focused, high-value follow-up steps after completing tasks.
- Human operators retain full oversight and governance over task enqueueing.
- The task queue pipeline gains end-to-end support for proposed -> pending -> running -> completed lifecycles.
