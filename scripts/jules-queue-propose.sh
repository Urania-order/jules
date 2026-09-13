#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

TASK_ID="${1:-}"
DESCRIPTION="${2:-}"
PRIORITY="${3:-3}"

if [ -z "$TASK_ID" ] || [ -z "$DESCRIPTION" ]; then
    echo "Usage: ./scripts/jules-queue-propose.sh <task-id> <description> [priority]"
    exit 1
fi

PROPOSED_DIR=".jules/queue/proposed"
mkdir -p "$PROPOSED_DIR"

TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
PROPOSAL_ID="proposal-${TIMESTAMP}-$$"
PROPOSAL_FILE="${PROPOSED_DIR}/${PROPOSAL_ID}.json"

python3 - "$PROPOSAL_FILE" "$PROPOSAL_ID" "$TASK_ID" "$DESCRIPTION" "$PRIORITY" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

proposal_file = Path(sys.argv[1])
data = {
    "id": sys.argv[2],
    "proposed_by": "jules",
    "source_task": sys.argv[3],
    "description": sys.argv[4],
    "priority": int(sys.argv[5]),
    "status": "proposed",
    "created_at": datetime.now(timezone.utc).isoformat(),
}
proposal_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"Proposal: {data['id']} (priority {data['priority']})")
PY

echo "  File: ${PROPOSAL_FILE}"
