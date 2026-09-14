# ADR 0006: Proposal Expiration and TTL Mechanism

- **Status:** Accepted
- **Date:** 2026-09-14
- **Task ID:** task-20260914-034220

## Context

In Co-SMOS, proposals exist at both the database consensus level (`Proposal` SQLAlchemy model) and the autonomous task staging level (`.jules/queue/proposed/`). Previously, proposals had no automatic expiration or time-to-live (TTL) mechanism. Over time, unreviewed or stale proposals would remain in `PENDING` status indefinitely, creating noise in consensus monitoring and queue management.

## Decision

1. **Database Layer (`Proposal` Model & `CognitiveService`)**:
   - Added an optional `expires_at` column (`DateTime(timezone=True)`) to the `Proposal` model (`smos/models/consensus.py`).
   - Extended proposal status enum to include `EXPIRED`.
   - Added `expire_aged_proposals(default_ttl_days=7)` method to `CognitiveService` (`smos/services/cognitive_service.py`), which checks pending proposals and transitions those past their explicit `expires_at` or default age threshold to `EXPIRED`.

2. **Task Queue Scripts (`jules-queue-propose.sh` & `jules-queue-review.sh`)**:
   - Extended `jules-queue-propose.sh` to support optional TTL in days (`./scripts/jules-queue-propose.sh <task-id> <description> [priority] [ttl-days]`), storing `expires_at` and `ttl_days` in the proposal JSON metadata.
   - Extended `jules-queue-review.sh` to add an `expire` command (`./scripts/jules-queue-review.sh expire [ttl-days]`) that scans `.jules/queue/proposed/`, identifies proposals past their TTL/age, sets status to `expired`, adds `expired_at`, and moves them to `.jules/queue/deferred/`.

3. **Observatory Monitoring Integration (`ObservatoryService`)**:
   - Updated `ObservatoryService.get_proposal_metrics()` and Markdown reports (`smos/services/observatory_service.py`) to aggregate and display `expired_proposals` count for DB proposals and `queue_expired_tasks` for queued task proposals.

## Consequences

- Stale consensus and task queue proposals are systematically expired, preventing accumulated clutter.
- Human reviewers gain visibility into expired proposals in both database metrics and deferred queue storage.
- Backward compatibility is maintained as TTL parameters remain optional.
