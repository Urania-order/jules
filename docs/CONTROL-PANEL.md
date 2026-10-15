# Co-SMOS v1.2 — Control Panel Documentation

## Section 0 — AI Context (compact)

```markdown
# Co-SMOS Control Panel — AI Context

## System
- Repo: Urania-order/jules
- Agent: Jules (cloud AI)
- Operator: Human
- State: .co-smos/state.json

## Two Task Types
- TASK (code):     run-task.sh,    commit: OK
- AUDIT (no code): jules-task.sh, commit: Do NOT commit

## Commands
- jules-status.sh
- run-task.sh /tmp/task.txt
- jules-task.sh "$(cat /tmp/t.txt)"
- jules remote list --session
- jules remote pull --session <id>
- jules-complete.sh --task <id>

## Audit Workflow
1. jules-task.sh (commit: Do NOT commit)
2. jules remote list --session → Completed
3. jules remote pull --session <id> → No diff
4. Cmd+C report from UI Jules
5. ./scripts/jules-audit-report.sh <task-id>

## Files
- .jules/results/        read-only
- docs/audit-reports/    reports (INDEX.md + task-*-report.md)
- .co-smos/state.json    active_task, last_task

## Audit Trail
Built from actual report metadata. Do not assume a planned chain.

## Key Principles
- Audit ≠ code (No diff)
- Report = evidence for next tasks
- Epistemic non-mutation
- READY_FOR_* ≠ auto-proceed

## Scripts (Verified in scripts/)
- Task: `run-task.sh`, `jules-task.sh`, `jules-status.sh`, `jules-complete.sh`
- Audit: `jules-audit-list.sh`, `jules-audit-report.sh`, `jules-audit-show.sh`, `jules-audit-verify.sh`
- Queue & Runner: `jules-queue-add.sh`, `jules-queue-clear.sh`, `jules-queue-propose.sh`, `jules-queue-review.sh`, `jules-queue-runner.sh`, `jules-queue-status.sh`, `process-queue.sh`
- Recovery & Maintenance: `jules-recover.sh`, `jules-replay.sh`, `jules-review.sh`, `normalize-state.sh`, `migrate-task-metadata.sh`, `clean-test-tasks.sh`
- Helpers & Validation: `co-smos.sh`, `safe-checkout.sh`, `safe-git.sh`, `test.sh`, `validate.sh`, `verify-cosmos-v11.sh`, `verify.sh`

## Control Room Panels (18 Panels Total)
1. Control Room (`dashboard`): Global overview, queue metrics, system status.
2. Command Intake (`command-intake`): Operator input intake and command parsing.
3. Reset Center (`reset-center`): Queue resetting and schedule controls.
4. Stages (`stages`): Task lifecycle stage pipeline visualization.
5. Commands (`sequence`): Executable command sequences and execution state.
6. Cycles (`cycles`): Autonomous cycle runner management.
7. Queue (`queue`): Task queue list, reordering, and state inspector.
8. Batch (`batch`): Batch execution jobs and template runner.
9. Recordings (`sequences`): Execution sequence recordings and playback.
10. Templates (`templates`): Task and prompt template management.
11. Proposals (`proposals`): Autonomous proposal review, accept, defer, reject.
12. Events (`events`): System-wide domain event stream log.
13. History (`history`): Historical task execution logs and replay flow.
14. Ontology (`ontology`): Graph visualization of domain entities and relations.
15. Consult (`consult`): Multi-agent consultation tuning, tokens, and audit logs.
16. Semantic (`semantic`): Read-only vector search and entity similarity explorer.
17. Admin (`admin`): Administrative controls and operator action logs.
18. Audit (`audit`): Audit report index, active audits, and audit trail verification.
```

---

## Section 1 — What is Co-SMOS

Co-SMOS (Cognitive Systems Monitoring and Operating System) functions like a high-precision restaurant kitchen operating under strict quality control.

| Role | Analogy | Description in Co-SMOS |
|---|---|---|
| **Operator (Human)** | Head Chef / Owner | Defines high-level directives, reviews audit reports, approves execution proposals, and controls system state. |
| **Agent (Jules)** | Line Cook / Specialist | Executes specific coding tasks or analytical audit tasks within sandboxed sessions. |
| **Queue / State** | Kitchen Order Board | Keeps track of pending, deferred, active, and completed tasks in `.co-smos/state.json`. |
| **Control Room UI** | Kitchen Control Dashboard | Live web interface (`frontend/index.html`) providing real-time visibility and management across all 18 panels. |

---

## Section 2 — Two Task Types

Co-SMOS strictly segregates implementation tasks from analytical audit tasks.

### 1. Implementation Task (TASK)
- **Runner**: `./scripts/run-task.sh /tmp/task-description.txt`
- **Purpose**: Writes or modifies repository code, schema, tests, or documentation.
- **Git Policy**: Commit allowed after full test suite and guardrail verification pass.
- **Result**: Produces a git diff and pull request.
- **Example**: Implementing feature endpoints, fixing bugs, or updating UI templates.

### 2. Audit Task (AUDIT)
- **Runner**: `./scripts/jules-task.sh "$(cat /tmp/audit-task.txt)"`
- **Purpose**: Purely analytical investigation, contract specification design, or architectural discovery.
- **Git Policy**: **Do NOT commit code changes**. Must NOT produce code diffs.
- **Result**: Generates an analytical report captured via `./scripts/jules-audit-report.sh <task-id>`.
- **Example**: Design audits (e.g. M-02A Versioning Contract Definition) or baseline discovery audits.

---

## Section 3 — Quick Start (5 Commands)

```bash
# 1. Navigate to repository root
cd /path/to/jules

# 2. Ensure scripts directory is accessible or run explicitly
export PATH="$PWD/scripts:$PATH"

# 3. Check current state and queue status
./scripts/jules-status.sh

# 4. Dispatch a task (TASK or AUDIT)
./scripts/run-task.sh /tmp/my-task.txt

# 5. Complete task execution after remote completion
./scripts/jules-complete.sh --task task-20261015-145701
```

---

## Section 4 — Work Cycle (9 Steps of `jules-complete.sh`)

When completing a task via `jules-complete.sh`, the system executes nine sequential steps:

| Step | Operation | Details |
|---|---|---|
| `[1/9]` | Stale Lock Removal | Invokes `remove_stale_git_lock` to clear lingering `.git/index.lock`. |
| `[2/9]` | Pull Remote Result | Calls `jules remote pull --session <id>` to fetch agent output. |
| `[3/9]` | Restore Stash | Restores stashed local changes if any were saved before pulling. |
| `[4/9]` | Check Git Status | Displays current working tree status (`git status --short`). |
| `[5/9]` | Update State | Updates active and last task status in `.co-smos/state.json`. |
| `[6/9]` | Update Task Record | Updates task metadata record under `.jules/queue/`. |
| `[7/9]` | Run Tests ⚠️ | Runs test suite (`uv run pytest tests/`). **Fails complete flow if tests fail.** |
| `[8/9]` | Commit & Push | Commits verified changes and pushes to `origin/main`. |
| `[9/9]` | CI Status Check | Monitors remote CI build status until completion. |

*Warning for Step 7*: Step 7 executes tests automatically. Do not bypass step 7 unless explicitly instructed by emergency override flags (`JULES_SKIP_TESTS=1`), which must be recorded as process anomalies.

---

## Section 5 — Control Room Overview

The Co-SMOS Control Room (`frontend/index.html`) consists of a top status bar displaying backend connection status, error alerts, active task summary, and 18 specialized view panels accessible through navigation buttons.

---

## Section 6 — Panels in Detail

1. **Control Room (`dashboard`)**
   - *Purpose*: Primary operational dashboard.
   - *Shows*: Backend health, queue summaries, recent tasks, system metrics.
   - *Action*: Monitor system heartbeat and launch quick task actions.

2. **Command Intake (`command-intake`)**
   - *Purpose*: Operator command entry point.
   - *Shows*: Text intake field for natural language instructions and task dispatch.
   - *Action*: Parse and submit operator directives into the task queue.

3. **Reset Center (`reset-center`)**
   - *Purpose*: Queue reset and schedule maintenance.
   - *Shows*: Reset options, column reset tools, and schedule configurations.
   - *Action*: Reset stalled tasks, restore archives, or configure schedules.

4. **Stages (`stages`)**
   - *Purpose*: Stage lifecycle pipeline monitor.
   - *Shows*: Pipeline progression across execution stages.
   - *Action*: View task progression through validation and execution stages.

5. **Commands (`sequence`)**
   - *Purpose*: Executable command sequence tracker.
   - *Shows*: Active command chains and execution step outputs.
   - *Action*: Track granular step execution for composite operations.

6. **Cycles (`cycles`)**
   - *Purpose*: Autonomous cycle runner controller.
   - *Shows*: Cycle runner status, iteration counts, and cycle logs.
   - *Action*: Pause, resume, or trigger autonomous maintenance cycles.

7. **Queue (`queue`)**
   - *Purpose*: Task queue management.
   - *Shows*: Pending, deferred, active, and completed task cards.
   - *Action*: Reorder queue priorities, inspect task details, or cancel tasks.

8. **Batch (`batch`)**
   - *Purpose*: Batch job processing.
   - *Shows*: Batch jobs, execution templates, and queue status.
   - *Action*: Launch or monitor multi-task batch execution pipelines.

9. **Recordings (`sequences`)**
   - *Purpose*: Sequence recording and playback.
   - *Shows*: Recorded execution sequences and playback options.
   - *Action*: Replay recorded command sequences for diagnostic verification.

10. **Templates (`templates`)**
    - *Purpose*: Task and prompt template repository.
    - *Shows*: Standardized task templates and parameter definitions.
    - *Action*: Instantiate new tasks using predefined templates.

11. **Proposals (`proposals`)**
    - *Purpose*: Autonomous proposal decision center.
    - *Shows*: Generated system proposals requiring operator approval.
    - *Action*: Accept, defer, reject, or modify proposals.

12. **Events (`events`)**
    - *Purpose*: Real-time domain event log viewer.
    - *Shows*: Stream of system events and entity status transitions.
    - *Action*: Filter and inspect system-wide audit events.

13. **History (`history`)**
    - *Purpose*: Historical task logs and replay execution.
    - *Shows*: Completed task history and modal replay logs.
    - *Action*: Inspect historical outcomes and trigger execution replays.

14. **Ontology (`ontology`)**
    - *Purpose*: Visual domain graph explorer.
    - *Shows*: Interactive SVG node-edge graph of phenomena, contexts, constraints, potentials, and predictions.
    - *Action*: Filter entity types and inspect detailed entity relationships.

15. **Consult (`consult`)**
    - *Purpose*: Multi-agent consultation tuning.
    - *Shows*: Role settings, consultation tokens, rate limits, and audit logs.
    - *Action*: Tune consultant roles, regenerate tokens, and inspect consultation logs.

16. **Semantic (`semantic`)**
    - *Purpose*: Read-only semantic vector search and similarity explorer.
    - *Shows*: Vector similarity candidate cards and similarity search results.
    - *Action*: Perform concept searches and find entity semantic neighbors.

17. **Admin (`admin`)**
    - *Purpose*: System administration panel.
    - *Shows*: Operator action logs, administrative queue overrides, and job controls.
    - *Action*: Trigger administrative jobs and manage queue locks.

18. **Audit (`audit`)**
    - *Purpose*: Dedicated Audit Panel added in Co-SMOS v1.2.
    - *Shows*: Active Audits table, Audit Reports Index, Audit Trail visualization, and Verification runner.
    - *Action*: Verify audit-trail continuity and save audit reports via copyable CLI command.

---

## Section 7 — Scripts Reference

Verified scripts in `scripts/`:

### Tasks
- `run-task.sh`: Launch code implementation task.
- `jules-task.sh`: Launch analytical audit task.
- `jules-status.sh`: Check active task status and queue state.
- `jules-complete.sh`: Complete remote task, run tests, and commit/push.

### Audit
- `jules-audit-list.sh`: List saved audit reports.
- `jules-audit-report.sh`: Save audit report from clipboard or stdin to `docs/audit-reports/`.
- `jules-audit-show.sh`: Display a specific audit report.
- `jules-audit-verify.sh`: Verify continuity of audit report index and files.

### Queue & Runner
- `jules-queue-add.sh`: Add new task to queue.
- `jules-queue-clear.sh`: Clear pending queue items.
- `jules-queue-propose.sh`: Generate task proposals.
- `jules-queue-review.sh`: Interactive queue review interface.
- `jules-queue-runner.sh`: Queue execution worker loop.
- `jules-queue-status.sh`: Display detailed queue state breakdown.
- `process-queue.sh`: Process pending tasks sequentially.

### Recovery & Maintenance
- `jules-recover.sh`: Recover from corrupted task or git states.
- `jules-replay.sh`: Replay task execution logs.
- `jules-review.sh`: Review task diffs and outcomes.
- `normalize-state.sh`: Clean and normalize `.co-smos/state.json`.
- `migrate-task-metadata.sh`: Migrate legacy task metadata formats.
- `clean-test-tasks.sh`: Remove ephemeral test tasks.

### Helpers & Validation
- `co-smos.sh`: Master CLI entry wrapper.
- `safe-checkout.sh`: Safe git checkout with lock cleanup.
- `safe-git.sh`: Helper functions for git lock handling and stashing.
- `test.sh`: Standard test runner wrapper.
- `validate.sh`: Repository validation suite.
- `verify-cosmos-v11.sh`: Co-SMOS v1.1 state verification script.
- `verify.sh`: General system state verification script.

---

## Section 8 — Audit Workflow (Detailed)

1. **Task Dispatch**: Launch audit task with `jules-task.sh`. Ensure git policy is set to **Do NOT commit**.
2. **Execution**: Jules performs analysis and writes report text in session output without code modifications.
3. **Session Completion**: Check completion via `jules remote list --session` and confirm empty diff via `jules remote pull --session <id>`.
4. **Report Capture**: Copy report content from Jules UI output.
5. **Report Storage**: Run `./scripts/jules-audit-report.sh <task-id>`. This creates `docs/audit-reports/<task-id>-report.md` and updates `docs/audit-reports/INDEX.md`.
6. **Trail Verification**: Run `./scripts/jules-audit-verify.sh` or click **Verify Trail** in the Audit panel UI to confirm audit continuity.

---

## Section 9 — Troubleshooting

- **Tests Failed during Complete**: Run `uv run pytest tests/` locally to identify failing tests. Fix code before re-running `jules-complete.sh`.
- **CI Build Failed**: Inspect GitHub Actions CI logs. Ensure all dependencies and test environment parameters match local pytest expectations.
- **DNS or Remote Connection Issue**: Retry using `jules remote list --session`. Check local internet connectivity.
- **Task Stuck in `.co-smos/state.json`**: Run `./scripts/normalize-state.sh` or `./scripts/jules-recover.sh` to clear active task state.
- **`git init -b` or Lock Error**: Run `./scripts/safe-checkout.sh` or execute `rm -f .git/index.lock`.

---

## Section 10 — Errata

For recorded errata, operational anomalies, and system architectural edge cases, refer to the directory:
`.jules/errata/`

---

## Section 11 — Safety (What NOT to Do)

- **Do NOT Force Push**: Never use `git push --force` on `main` or shared branches.
- **Do NOT Touch Forbidden Paths**: `.co-smos/`, `.jules/tasks/`, `.jules/results/`, `.jules/queue/` are read-only.
- **Do NOT Skip Tests**: Never pass `JULES_SKIP_TESTS=1` without explicit operator authorization and logged rationale.
- **Do NOT Commit Code in Audit Tasks**: Audit tasks must never commit code modifications.

---

## Section 12 — Next Steps

With Co-SMOS v1.2 Control Panel and Audit Panel established, future phase tasks (such as M-02 Content Versioning Implementation) can be dispatched as separate implementation tasks under their own explicit acceptance criteria. Completion of v1.2 does not automatically authorize starting M-02.
