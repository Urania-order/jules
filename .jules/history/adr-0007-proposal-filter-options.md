# ADR 0007: Proposal Filter Options in Queue Review Script

## Status
Accepted

## Context
The task proposal subsystem allows Jules to generate post-task proposals stored in `.jules/queue/proposed/` (or deferred proposals in `.jules/queue/deferred/`).
Human operators inspect, accept, or reject proposals using `scripts/jules-queue-review.sh`.

Prior to this change, running `jules-queue-review.sh list` or `jules-queue-review.sh deferred` displayed all proposals in the directory without filtering options. As the number of proposals grows, operators need the ability to filter proposals by:
1. `priority` (e.g. only proposals with priority matching or greater/equal to a threshold, or specified priority string/integer like `--min-priority`, `--priority` / `-p`).
2. `source_task` (e.g. proposals originating from a specific task ID via `--source-task` / `--source` / `-s`).

## Decision
1. Update `scripts/jules-queue-review.sh` to accept optional filter flags for `list` and `deferred` subcommands (and also support positionally parsed or option-parsed flags across the script):
   - `--priority <val>` / `-p <val>`: Filters proposals where `priority` matches `<val>` (or text mappings high=10, normal=5, low=1, or integer values). Also support `--min-priority <val>` if needed, or exact/min matching. For flexibility, exact match or integer comparison will be supported. Text labels (high=10, normal=5, low=1) and integer priority numbers are mapped cleanly.
   - `--source-task <id>` / `--source <id>` / `-s <id>`: Filters proposals where `source_task` contains or matches the specified task ID string.
2. Ensure command usage and help strings clearly document the new filtering capabilities.
3. Keep backward compatibility with existing positional usage (`list`, `deferred`, `accept <id>`, `reject <id>`, etc.).

## Consequences
- Operators can quickly filter proposals by priority and source task when running `list` or `deferred`.
- Existing workflows and automated tests remain unaffected while gaining enhanced filtering functionality.
