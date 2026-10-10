# ADR 0009: Analysis Trace & Replay Contract Audit

## Context

TASK 39 verified the end-to-end research pipeline across Co-SMOS domain services (`PhenomenonService`, `ContextService`, `ConstraintService`, `PotentialService`, `DomainRelationService`, `FourPositionService`, `EmergenceAnalysisService`, `BlockageAnalysisService`, and `PredictionService`). Following this verification, TASK 40 executes a formal contract audit of analysis trace and replay capabilities.

The audit evaluates whether an entire research run (composed of multiple analytical steps across different services) can be linked by a shared correlation identifier, whether historical replay vs. current-state rerun can be executed and distinguished, whether analytical services possess clean reproducible contracts, how data types (immutable facts, mutable data, derived signals) are segregated, and what minimal structural changes are required if full historical replay is not currently possible.

---

## Audit Findings (STEP 0 Audit Results)

### 2.1 DomainEvent — Full Audit
* Source files: `smos/models/domain_event.py`, `smos/services/domain_event_service.py`
* **Model Fields**:
  - `id`: `Integer`, primary key, indexed.
  - `actor_type`: `String`, nullable (`"user"`, `"cosmonaut"`, `"llm"`, `"system"`).
  - `actor_id`: `Integer`, nullable.
  - `entity_type`: `String`, non-nullable, indexed (`"phenomenon"`, `"context"`, `"constraint"`, `"potential_phenomenon"`, `"domain_relation"`, `"prediction"`, `"resonance"`, etc.).
  - `entity_id`: `Integer`, non-nullable, indexed.
  - `event_type`: `Enum(DomainEventType)` (`CREATED`, `UPDATED`, `DELETED`, `LINKED`, `UNLINKED`, `STATE_CHANGED`).
  - `created_at`: `DateTime(timezone=True)`, default `func.now()`, indexed.
  - `context_ids`: `JSON`, list of context IDs.
  - `evidence_ids`: `JSON`, list of evidence IDs.
  - `changes`: `JSON`, dict (`{field: {old, new}}`).
  - `provenance`: `JSON`, dict.
* **`record()` Signature**:
  `record(entity_type, entity_id, event_type, actor_type=None, actor_id=None, context_ids=None, evidence_ids=None, changes=None, provenance=None) -> DomainEvent`
* **`reconstruct_entity()` Behavior**:
  Fetches all events for `(entity_type, entity_id)` sorted chronologically (`created_at.asc(), id.asc()`). Returns a dictionary with `entity_type`, `entity_id`, `event_count`, `created_at`, `updated_at`, `events`, and a read-only reconstruction note.
* **`reconstruct_lifecycle()` Behavior**:
  Returns `list_for_entity(entity_type, entity_id)` serialized as `to_dict()` dictionaries in chronological order.
* **`list_for_entity()` Behavior**:
  Queries `DomainEvent` filtered by `entity_type` and `entity_id`, ordered by `created_at.asc(), id.asc()`, with `offset` and `limit`.
* **`list_recent()` Behavior**:
  Queries `DomainEvent` ordered by `created_at.desc(), id.desc()`, capped by `limit` (default 50).

### 2.2 Who Writes DomainEvents Today
* Audit command: `grep -rn "DomainEventService\|event_service\.record" smos/`
* **Caller**: `PhenomenonService` (`smos/services/phenomenon_service.py`)
  - `create()` -> records `CREATED` for entity_type `"phenomenon"`.
  - `update()` -> records `UPDATED` (or `STATE_CHANGED` if `epistemic_status` changed) for entity_type `"phenomenon"`.
  - `link_context()` -> records `LINKED` for entity_type `"phenomenon"`.
  - `delete()` -> records `DELETED` for entity_type `"phenomenon"`.
* Note: `PhenomenonService` acts as the initial POC integration for `DomainEventService`.

### 2.3 Which Services Do NOT Write DomainEvents
* **Canonical Entity CRUD Services**: `ContextService`, `ConstraintService`, `PotentialService`, `DomainRelationService` do not currently accept or invoke `DomainEventService.record()`.
* **Analytical / Projection / Analysis Services**: `FourPositionService`, `ConvergentResonanceService`, `RoleProjectionService`, `EmergenceAnalysisService`, `BlockageAnalysisService` are read-only analytical/projection layers and do NOT write `DomainEvent` records or persist run outputs.
* **Lifecycle / Experience Services**: `PredictionService` (attaches outcome and evaluates predictions), `ContextExposureService`, `RecipeService`, `EvolutionService` do not record `DomainEvent` entries during lifecycle transitions.

### 2.4 Trace ID / Analysis ID / Correlation ID
* Audit command: `grep -rn "trace_id\|analysis_id\|correlation_id" smos/`
* Result: 0 matches across `smos/`. No cross-service correlation identifier or trace ID exists in data models, function signatures, or domain events.

### 2.5 Input Snapshot / Versioning
* Critical Question: If canonical input entities or domain relations change after an analysis run, can the analysis be replayed with original inputs?
* Finding: **No.** Canonical entities (`Phenomenon`, `Context`, `Constraint`, `PotentialPhenomenon`, `DomainRelation`) use mutable rows in SQLite/PostgreSQL without temporal entity versioning (no `version_id` or `valid_from`/`valid_to` timestamps). Analytical outputs (e.g. `FourPositionService.build_analysis()`, `EmergenceAnalysisService.analyze_emergence()`) query current DB table states dynamically using entity IDs. If an entity's fields or incident relations are updated or soft/hard-deleted, re-executing the service function produces the current state result, not the historical result. Storing entity IDs alone without point-in-time input snapshots or immutable entity versioning is insufficient for historical replay.

### 2.6 Analytical Service Invocation Contracts
1. **`FourPositionService.build_analysis(phenomenon_id, include_semantic=False)`**
   - Pure/State-changing: Pure (read-only).
   - Inputs: `phenomenon_id: int`, `include_semantic: bool`.
   - Side effects: None.
   - Depends on current DB state: Yes (queries `Phenomenon` and incident `DomainRelation` rows).
   - Reproducible: Yes, given fixed DB state.
   - Re-invocation safe: Yes (idempotent, read-only).
2. **`ConvergentResonanceService.detect(include_semantic=False)`**
   - Pure/State-changing: Pure (read-only).
   - Inputs: `include_semantic: bool`, optional filters (`min_agents`, `overlap_threshold`).
   - Side effects: None.
   - Depends on current DB state: Yes (queries `ContextExposure` rows).
   - Reproducible: Yes, given fixed DB state.
   - Re-invocation safe: Yes (idempotent, read-only).
3. **`RoleProjectionService.PhenomenonPerspective(phenomenon_id)`**
   - Pure/State-changing: Pure (read-only).
   - Inputs: `phenomenon_id: int`.
   - Side effects: None.
   - Depends on current DB state: Yes (queries incident `DomainRelation` rows).
   - Reproducible: Yes, given fixed DB state.
   - Re-invocation safe: Yes (idempotent, read-only).
4. **`EmergenceAnalysisService.analyze_emergence(phenomenon_id)`**
   - Pure/State-changing: Pure (read-only).
   - Inputs: `phenomenon_id: int`.
   - Side effects: None.
   - Depends on current DB state: Yes (queries incident `DomainRelation` and `PotentialPhenomenon` rows).
   - Reproducible: Yes, given fixed DB state.
   - Re-invocation safe: Yes (idempotent, read-only).
5. **`BlockageAnalysisService.analyze_blockage(phenomenon_id)`**
   - Pure/State-changing: Pure (read-only).
   - Inputs: `phenomenon_id: int`.
   - Side effects: None.
   - Depends on current DB state: Yes (queries `Constraint` and multi-hop `DomainRelation` rows).
   - Reproducible: Yes, given fixed DB state.
   - Re-invocation safe: Yes (idempotent, read-only).
6. **`PredictionService.create_prediction(...)`**
   - Pure/State-changing: State-changing (creates `Prediction` DB row).
   - Inputs: `expected_state`, `prediction_time`, `expected_at`, `source_hypothesis_type`, `source_hypothesis_id`, `conditions`, `confidence`, `provenance`.
   - Side effects: Persists new `Prediction` row with `EpistemicStatus.PREDICTED`.
   - Depends on current DB state: No (inserts new record).
   - Reproducible: N/A (factory operation).
   - Re-invocation safe: Generates new ID per call.
7. **`PredictionService.attach_outcome(prediction_id, actual_outcome)`**
   - Pure/State-changing: State-changing by design (updates `actual_outcome` on existing `Prediction`).
   - Inputs: `prediction_id: int`, `actual_outcome: str`.
   - Side effects: Updates row, sets `prediction_time`.
   - Depends on current DB state: Yes.
   - Re-invocation safe: Overwrites `actual_outcome` on target row.
8. **`PredictionService.evaluate(prediction_id, evaluation)`**
   - Pure/State-changing: State-changing by design (updates `evaluation` dict on existing `Prediction`).
   - Inputs: `prediction_id: int`, `evaluation: dict`.
   - Side effects: Updates row evaluation payload.
   - Depends on current DB state: Yes.
   - Re-invocation safe: Overwrites `evaluation` payload on target row.

### 2.7 Immutable vs Mutable vs Derived
* **Immutable Historical Facts**:
  - `DomainEvent` (`smos/models/domain_event.py`): Append-only entity change event log.
  - `ContextExposure` (`smos/models/context_exposure.py`): Immutable snapshot of agent reasoning context exposure and conclusion.
* **Mutable Data**:
  - Canonical Domain Entities (`Phenomenon`, `Context`, `Constraint`, `PotentialPhenomenon`) and `DomainRelation` (`smos/models/domain_relation.py`): Rows support in-place `UPDATE` and `DELETE` without historical table versioning.
  - `Prediction` (`smos/models/prediction.py`): Fields `actual_outcome` and `evaluation` are updated in-place during lifecycle progression.
* **Derived Semantic Signals**:
  - `SemanticIndexEntry` (`smos/models/semantic_index.py`): Derived, non-canonical vector representations created via `SemanticSearchService` / `HashFallbackAdapter`.
  - `provenance["semantic_candidates"]`: Candidate lists attached to top-level analytical payloads (`FourPositionService`, `ConvergentResonanceService`, `RoleProjectionService`, `RecipeService`, `PredictionService`) that act strictly as candidate generation signals without constituting evidence or altering canonical epistemic status.

### 2.8 Input Change → Historical Integrity
* Audit of existing tests:
  - `tests/test_prediction.py` verifies attaching outcome and evaluation to a `Prediction`.
  - `tests/test_four_position_service.py` and `tests/test_four_position_verification.py` verify read-only analysis construction from current DB state.
  - `tests/test_research_scenario_e2e.py` verifies the complete research pipeline.
* **Identified Gap**: No test currently verifies that modifying or deleting a `Phenomenon` or `DomainRelation` after creating a `Prediction` or running a `FourPosition` analysis preserves the original analysis result. Because analytical outputs are generated dynamically on-the-fly and not saved as immutable analysis records, any change to underlying entities directly alters subsequent analysis outputs.

### 2.9 Semantic Candidates and Provenance
* `semantic_candidates` are stored exclusively inside the top-level `provenance` dictionary (e.g. `provenance["semantic_candidates"]`).
* Confirmed across source code (`smos/services/four_position_service.py`, `smos/services/convergent_resonance_service.py`, `smos/services/role_projection_service.py`, `smos/services/prediction_service.py`, `smos/services/recipe_service.py`):
  - `semantic_candidates` are **NEVER** treated as evidence.
  - `semantic_candidates` are **NEVER** promoted to canonical `DomainRelation` edges or canonical entities.
  - They serve strictly as non-evidence, candidate-generation signals.

### 2.10 Existing Tests and API
* `tests/test_domain_event.py`: 15 tests.
* `tests/test_api_domain_events.py`: 8 tests.
* `tests/test_lifecycle_reconstruction.py`: 6 tests.
* API endpoints for domain events (`smos/api/main.py`):
  - `GET /api/domain-events`
  - `GET /api/domain-events/{entity_type}/{entity_id}`
  - `POST /api/domain-events/reconstruct/{entity_type}/{entity_id}`
* Replay Endpoints: Currently **ZERO** endpoints support execution replay or rerun. Reconstruct endpoints only return chronological `DomainEvent` audit logs.

### 2.11 Two Replay Modes Audit
* **Historical Replay** (Execution of an analysis using its original inputs and state snapshot to reproduce the exact original result):
  - Status: **Not supported**. Original input snapshots and correlation identifiers are not persisted during analysis execution.
* **Current-State Rerun** (Re-execution of analysis logic against current canonical DB state):
  - Status: **Supported**. Analytical service functions (`build_analysis`, `analyze_emergence`, `analyze_blockage`, `detect`) can be invoked at any time against current DB state.
* **Difference Explainable**:
  - Status: **No**. Because historical outputs are not persisted with input snapshots, the system cannot diff or explain discrepancies between historical run results and current-state reruns.

### 2.12 AGENTS.md Rules Audit
* Source: `AGENTS.md` §16, §17, §27.
* Text regarding `.jules/history/`:
  - §16.1: "`.jules/history/` — ADRs and decisions"
  - §17: "Jules MUST NOT modify: ... `.jules/history/` — existing ADRs"
  - §17 Allowed: "Jules may CREATE a new ADR file in `.jules/history/` when a significant architectural decision is made (e.g. `adr-0002-*.md`). Jules MUST NOT modify existing ADRs."
* Confirmation: Creating a single new ADR file in `.jules/history/` is explicitly authorized.

### 2.13 ADR Format Audit
* Latest ADR examined: `.jules/history/adr-0008-api-integration-testing.md`.
* Exact structure used:
  ```markdown
  # ADR NNNN: <Title>

  ## Context

  ## Decision

  ## Consequences
  ```
* Next Free ADR Number determination:
  Command `ls .jules/history/adr-*.md | grep -oE "adr-[0-9]+" | sort -u | tail -1` returned `adr-0008`.
  Therefore, the NEXT FREE ADR NUMBER is **0009** (`.jules/history/adr-0009-analysis-trace-replay.md`).

---

## Decision Matrix

### Q1. Can all steps of ONE research run be linked by a shared identifier WITHOUT duplicating DomainEvent?
**No.**
*Evidence*: Source inspection of `smos/models/domain_event.py` and all service callers in `smos/services/` reveals zero references to `trace_id`, `analysis_id`, or `correlation_id`. `DomainEvent` records individual entity lifecycle events (`CREATED`, `UPDATED`, `LINKED`) without a parent session or research trace correlation key.

### Q2. Are versions or sufficient input snapshots preserved for re-execution (historical replay)?
**No.**
*Evidence*: Canonical models (`Phenomenon`, `Context`, `Constraint`, `PotentialPhenomenon`, `DomainRelation`) in `smos/models/` store only current state. Neither entity table versioning nor analytical input snapshot payload storage is implemented. Re-running an analysis function after entity/relation modifications executes against the updated state, making historical replay impossible.

### Q3. Do analytical services have clean, reproducible invocation contracts?
**Partial.**
*Evidence*: Read-only analytical services (`FourPositionService`, `EmergenceAnalysisService`, `BlockageAnalysisService`, `ConvergentResonanceService`, `RoleProjectionService`) have clean, deterministic, pure-function invocation signatures. Given a fixed database state, their outputs are perfectly reproducible. However, because inputs are implicitly pulled from current database tables rather than explicitly passed as versioned snapshots, contract reproducibility is bounded by database immutability.

### Q4. How to distinguish immutable facts, mutable data, derived signals?
**Documented.**
*Evidence*:
  1. *Immutable Historical Facts*: `DomainEvent` (append-only change records) and `ContextExposure` (immutable reasoning exposure entries).
  2. *Mutable Data*: Canonical domain entities (`Phenomenon`, `Context`, `Constraint`, `PotentialPhenomenon`), `DomainRelation`, and `Prediction` lifecycle states (`actual_outcome`, `evaluation`).
  3. *Derived Semantic Signals*: `SemanticIndexEntry` (derived embeddings) and `provenance["semantic_candidates"]` (read-only candidate generation signals).

### Q5. What MINIMAL changes are needed if full replay is not currently possible?
**Minimal Changes Required (Option 2)**:
  1. Add an optional `trace_id: Optional[str] = None` field to `DomainEvent` and `DomainEventService.record()`.
  2. Extend `DomainEventService` with `record_analysis_run(trace_id, analysis_type, input_snapshot, output_snapshot)` or record an `ANALYSIS_EXECUTED` event type capturing point-in-time input/output snapshots in `provenance`.
  3. Extend analytical service invocation methods (`build_analysis`, `analyze_emergence`, `analyze_blockage`, `detect`) to accept an optional `trace_id: Optional[str] = None`.
  4. Expose a read-only comparison / replay API endpoint (`POST /api/analysis/replay/{trace_id}`) that retrieves the stored input snapshot for historical replay and compares it against current-state rerun logic.

---

## Decision

**Option 2 — MINIMAL EXTENSION** is chosen.

### Option 1 Disqualification Justification
Option 1 (USE EXISTING MECHANISMS) requires ALL five conditions (a)–(e) to be confirmed in source code:
- (a) *Identifier grouping research runs*: **Failed** (0 trace/correlation ID fields exist).
- (b) *Original inputs / versions recorded*: **Failed** (No input snapshots or entity versioning exist).
- (c) *Reproducible contracts given fixed inputs/state*: **Confirmed** for read-only analytical services under fixed state.
- (d) *Replay independent of state mutation*: **Failed** (Re-running queries current mutable tables).
- (e) *Explainable comparison between original and rerun*: **Failed** (No original outputs saved for diffing).

Since conditions (a), (b), (d), and (e) are NOT met by existing code, Option 1 CANNOT be chosen.

### Option 3 Disqualification Justification
Option 3 (NEW CONTRACT REQUIRED) is rejected because the existing architecture (`DomainEventService`, `provenance` JSON dictionaries, and pure analytical service methods) provides a sound foundation. Implementing trace-linked replay does not require replacing the domain model or event system; it merely requires adding a `trace_id` correlation field and input/output snapshot persistence to the existing `DomainEvent` mechanism.

### Option 2 Scope
Option 2 specifies a small, well-scoped extension to `DomainEvent` and analytical service signatures without altering canonical domain models or breaking backward compatibility. **Per TASK 40 constraints, zero production code changes are made in TASK 40.**

---

## Consequences & Follow-Up Recommendations

### Minimal Extension Specification (For Follow-Up Tasks)

1. **Correlation Identifier (`trace_id`)**:
   - Add `trace_id = Column(String, nullable=True, index=True)` to `DomainEvent` (`smos/models/domain_event.py`).
   - Update `DomainEventService.record()` to accept `trace_id: Optional[str] = None`.

2. **Analysis Execution Event Logging**:
   - Add `ANALYSIS_EXECUTED` to `DomainEventType` enum.
   - When an analytical service (`FourPositionService`, `EmergenceAnalysisService`, `BlockageAnalysisService`, `ConvergentResonanceService`) executes an analysis, option `record_event=True` passes `trace_id` and logs an `ANALYSIS_EXECUTED` event containing:
     - `entity_type`: target entity type (e.g. `"phenomenon"`).
     - `entity_id`: target entity ID.
     - `changes`: summary of analysis parameters.
     - `provenance`: `{ "input_snapshot": { ... }, "output_snapshot": { ... } }`.

3. **Replay vs Rerun API Contract**:
   - Add `GET /api/analysis/trace/{trace_id}`: Retrieves all `DomainEvent` entries for a research run.
   - Add `POST /api/analysis/replay/{trace_id}`:
     - *Historical Replay*: Re-executes analysis using `input_snapshot` stored in the event provenance.
     - *Current-State Rerun*: Re-executes analysis against live DB tables.
     - Returns diff highlighting any discrepancies between original result and current state result.

---

## Two Replay Modes — Summary of Findings

* **Historical Replay**: Not supported (Requires `trace_id` and `input_snapshot` persistence).
* **Current-State Rerun**: Supported (Service methods can be re-invoked against live DB tables).
* **Difference Explainable**: No (Requires original output snapshot comparison).

---

## Deliberately Unchanged Elements

In strict adherence to TASK 40 instructions:
- NO production code in `smos/` was modified.
- NO existing model or schema was changed.
- NO new service or API endpoint was added.
- NO existing test in `tests/` was modified or deleted.
- NO existing ADR in `.jules/history/` was edited.

---

## Remaining Gaps

1. Absence of `trace_id` correlation across multi-step research pipelines.
2. Canonical entity tables lack point-in-time versioning or input snapshot preservation.
3. Analytical runs are not automatically recorded in `DomainEvent`.
4. Absence of an explicit diff/comparison mechanism between historical analysis results and current-state reruns.

---

## Pre-Commit Scope Verification

### Tracked / Staged Files (`git status --short`)
- `git diff --check`: Clean (no whitespace issues).
- `git diff --cached --check`: Clean.
- `git diff --cached --name-only`: Empty (no modified tracked files staged).

### Untracked Files (`git status --short` & `git ls-files --others --exclude-standard`)
- `.jules/history/adr-0009-analysis-trace-replay.md` (EXACTLY ONE NEW FILE).

### Confirmation
- NO production file modified.
- NO existing test modified.
- NO existing ADR modified.
- EXACTLY ONE new file created: `.jules/history/adr-0009-analysis-trace-replay.md`.
