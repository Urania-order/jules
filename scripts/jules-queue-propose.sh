#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

TASK_ID="${1:-}"
DESCRIPTION="${2:-}"
PRIORITY="${3:-3}"
TTL_DAYS="${4:-}"

if [ -z "$TASK_ID" ] || [ -z "$DESCRIPTION" ]; then
    echo "Usage: ./scripts/jules-queue-propose.sh <task-id> <description> [priority] [ttl-days]"
    exit 1
fi

PROPOSED_DIR=".jules/queue/proposed"
mkdir -p "$PROPOSED_DIR"

TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
PROPOSAL_ID="proposal-${TIMESTAMP}-$$"
PROPOSAL_FILE="${PROPOSED_DIR}/${PROPOSAL_ID}.json"

python3 - "$PROPOSAL_FILE" "$PROPOSAL_ID" "$TASK_ID" "$DESCRIPTION" "$PRIORITY" "$TTL_DAYS" <<'PY'
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

proposal_file = Path(sys.argv[1])
ttl_arg = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else None

created_at_dt = datetime.now(timezone.utc)
data = {
    "id": sys.argv[2],
    "proposed_by": "jules",
    "source_task": sys.argv[3],
    "description": sys.argv[4],
    "priority": int(sys.argv[5]),
    "status": "proposed",
    "created_at": created_at_dt.isoformat(),
}
if ttl_arg and ttl_arg.isdigit():
    expires_at_dt = created_at_dt + timedelta(days=int(ttl_arg))
    data["expires_at"] = expires_at_dt.isoformat()
    data["ttl_days"] = int(ttl_arg)

proposal_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"Proposal: {data['id']} (priority {data['priority']})")
PY

echo "  File: ${PROPOSAL_FILE}"
