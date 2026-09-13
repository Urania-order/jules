# ADR 0005: Proposal Status Metrics in Observatory

- **Status:** Accepted
- **Date:** 2026-09-14
- **Task ID:** task-20260914-021957

## Context

Co-SMOS uses consensus proposals (`Proposal` DB model) for decision-making and task proposals (`.jules/queue/proposed/`) for staging autonomous task proposals. Prior to this change, Observatory health reports monitored subsystem ecosystem health (ecology, value, commons, discovery, research) but lacked metrics on proposal status, approval rates, and queued task proposals.

## Decision

1. Added `get_proposal_metrics()` method to `ObservatoryService` that aggregates:
   - Total database consensus proposals.
   - Status breakdown (PENDING, APPROVED, REJECTED).
   - Approval rate for resolved proposals.
   - Count of staged task queue proposals (`.jules/queue/proposed/`).
2. Integrated `proposal_metrics` into `ObservatoryService.get_health_report()` under the `"proposal_metrics"` key.
3. Updated Markdown report export (`export_report_markdown()`) to include a dedicated `### Proposal Status Metrics` section.
4. Added FastAPI endpoint `GET /observatory/proposals` to expose proposal status metrics via API.

## Consequences

- Observatory reports now provide visibility into decision consensus and pending autonomous task proposals.
- System health reports gain quantifiable proposal resolution metrics without breaking backward compatibility of existing subsystem health metrics.
