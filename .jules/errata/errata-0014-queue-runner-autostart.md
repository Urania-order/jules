# ERRATA-0014: jules-queue-runner.sh can auto-start tasks

## Symptom
Tasks task-20260916-030203 ("Dependency Test Task") and
task-20260916-031341 ("Test task from unit test") were
dispatched to Jules without an explicit human request.

.jules/queue/pending/ contained ~30 test-task JSON files,
all created around 2026-09-16T02:55.

jules-queue-runner.sh (PID 7973, then 9502 after kill -9)
was observed running and dispatching tasks.

## Cause
jules-queue-runner.sh processes .jules/queue/pending/*.json
and dispatches each via jules-task.sh.

It can be run:
  - once:   ./scripts/jules-queue-runner.sh --once
  - loop:   ./scripts/jules-queue-runner.sh --loop

If started with --loop, it continuously processes the queue.

## Fix
1. Stop the runner:
     pkill -9 -f "jules-queue-runner"
     pkill -9 -f "queue/pending"
2. Check no --loop process remains.
3. Move pending tasks to deferred:
     mkdir -p .jules/queue/deferred
     mv .jules/queue/pending/*.json .jules/queue/deferred/
4. Reset state.json if active_task is stale.
5. Record aborted task cards.

## Prevention
- NEVER start jules-queue-runner.sh with --loop unless intended.
- Before dispatching tasks, review .jules/queue/pending/.
- Periodically check:
    ps aux | grep -iE "queue-runner|--loop" | grep -v grep
    ls .jules/queue/pending/*.json 2>/dev/null | wc -l

## Related
- ERRATA-0012: Jules still modifies .jules/queue/ despite ban.
- Distinguish: orchestrator scripts may touch .jules/queue/;
  Jules (the agent) must not.
