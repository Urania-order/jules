# Architectural Decision Record: ADR-0002
- **Date:** 2026-09-12
- **Task ID:** task-20260912-230201
- **Title:** ResearchService Portal Management with Observable and Evolvable Support

## Context
Research Portals serve as the bridge between knowledge ecology and tangible resources, facilitating collective sponsorship of research hypotheses and living clusters. Prior to this enhancement, `ResearchService` provided minimal functionality (`open_portal` and `sponsor_research`) without full portal lifecycle management, status filtering, outcome tracking, or metric observability.

## Decisions Made
1. **Implement `Evolvable` and `Observable` Core Interfaces**:
   - `ResearchService` implements `Evolvable` to handle lifecycle state transitions (`OPEN` -> `FUNDED` -> `COMPLETED`/`CLOSED`).
   - `ResearchService` implements `Observable` to expose subsystem health metrics (active portals, funded portals, total sponsorship funds, etc.) and evolution summaries for ecosystem monitoring.
2. **Enhanced Portal Lifecycle & Management**:
   - Added `get_portal`, `list_portals` (with status filtering), `record_outcome`, `close_portal`, `advance_lifecycle`, and `get_lifecycle_state`.
   - Supported explicit funding thresholds and sponsorship tracking.
3. **API & MCP Tool Extensions**:
   - Extended FastAPI endpoints in `smos/api/main.py` and MCP server tools in `smos/core/mcp_server.py` to support listing portals, recording outcomes, and checking health metrics.
4. **SQLAlchemy 2.0 Compliance**:
   - Replaced legacy `session.query(Model).get(id)` with modern `session.get(Model, id)`.

## Consequences
- Research portals can now be queried, sponsored, progressed through lifecycles, and closed with documented outcomes.
- ObservatoryService and ecosystem monitors can observe research funding metrics alongside ecology and value metrics.
- Backward compatibility with existing callers of `open_portal` and `sponsor_research` is preserved.
