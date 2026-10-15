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
