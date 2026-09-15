# ADR 0008: Control Room API Integration Test Isolation & Edge Case Verification

## Context

The Co-SMOS Web Control Room FastAPI application (`smos/api/main.py`) provides endpoints for system status, task queue management, lifecycle state transitions, proposal modifications/actions, and event tracking.

During integration testing, API endpoints executing CLI operations (via `JulesCLIAdapter`) or managing filesystem state (`QueueManager`, `ProposalManager`) read and write runtime files under `.jules/queue/`. Without proper test environment isolation, test execution mutated persistent project task/proposal queues. Furthermore, testing state-changing API endpoints required explicit verification of both success status codes and expected error responses for non-existent or invalid resources (adhering to ERRATA-0003).

## Decision

1. **Test Queue Isolation**:
   In `tests/test_control_room_api.py`, created a pytest fixture `queue_dirs` using `tmp_path` and `monkeypatch`.
   The fixture sets up temporary isolated `.jules/queue` subdirectories (`pending`, `running`, `completed`) and copies scripts to a temporary `scripts/` directory, while setting `JULES_PROJECT_ROOT` to `tmp_path`. This prevents API integration tests from modifying actual queue files in `.jules/queue/`.

2. **Integration Test Coverage**:
   Expanded `tests/test_control_room_api.py` to cover:
   - Task creation and retrieval (`POST /api/queue`, `GET /api/tasks`, `GET /api/tasks/{id}`).
   - Task lifecycle transitions (`POST /api/tasks/{id}/start`, `POST /api/tasks/{id}/cancel`, `GET /api/tasks/{id}/history`).
   - Task modification (`PATCH /api/tasks/{id}`) including title, priority, and valid status updates as well as error response for `INVALID_STATUS`.
   - Resource non-existence edge cases (`404 TASK_NOT_FOUND` and `404 PROPOSAL_NOT_FOUND`).
   - Queue reordering (`POST /api/queue/reorder`) and queue execution (`POST /api/queue/run`).
   - Proposal listing, modification (`POST /api/proposals/{id}/modify`), and action handling (`POST /api/proposals/{id}/defer`).
   - System events query endpoint (`GET /api/events`).

## Consequences

- Integration tests for FastAPI Control Room API endpoints run deterministically and fast without polluting repository queue state.
- Edge case handling (400 and 404 status codes) is verified for all state-changing and item retrieval endpoints.
- Backward compatibility with legacy service endpoints and test suite requirements is maintained.
