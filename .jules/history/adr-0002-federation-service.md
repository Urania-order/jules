# Architectural Decision Record: ADR-0002
- **Date:** 2026-09-12
- **Task ID:** task-20260912-230132
- **Title:** Implementation of FederationService and Knowledge Sovereignty Subsystem

## Context
To enable anti-fragile, multi-node distributed knowledge networks in Co-SMOS as specified in `FEDERATION.md`, the ecosystem requires a dedicated service to handle multi-instance registration, subscription filtering by epistemic consensus levels, non-destructive cross-node knowledge synchronization, provenance retention, and sovereignty principle enforcement.

## Decisions Made
1. **Created Federated Models in `smos/models/ecology.py`**:
   - Added `FederatedNode` (stores remote node metadata, trust score, sovereignty level, consensus priority, status).
   - Added `FederatedSubscription` (stores cluster/topic subscriptions and epistemic consensus filters).

2. **Implemented `FederationService` in `smos/services/federation_service.py`**:
   - Implemented node registration, status querying, and subscription operations.
   - Implemented `export_knowledge_payload` and `sync_knowledge_from_node` to export/import memory nodes while preserving `ProvenanceRecord` structures and tagging origin node metadata.
   - Implemented `evaluate_sovereignty_policy` and `check_sovereignty_principles`.
   - Implemented the `Observable` interface (`get_health_metrics`, `get_evolution_summary`) to report federation health metrics.

3. **Integrated `FederationService` with API & Observatory**:
   - Registered `FederationService` as an observable subsystem in `ObservatoryService` within `smos/api/main.py`.
   - Added FastAPI endpoints (`/federation/node`, `/federation/nodes`, `/federation/sync`, `/federation/sovereignty/{node_id}`).
   - Delegated sovereignty policy checks in `SovereigntyService` to `FederationService`.

4. **Added Comprehensive Testing**:
   - Created `tests/test_federation_service.py` testing registration, subscriptions, knowledge payload sync with provenance retention, sovereignty evaluation, and Observable health metrics.

## Consequences
- Multi-instance Co-SMOS nodes can now register, subscribe to clusters, and synchronize knowledge while preserving epistemic boundaries and provenance history.
- ObservatoryService now monitors federation health metrics alongside ecology, value ecology, commons, and discovery subsystems.
