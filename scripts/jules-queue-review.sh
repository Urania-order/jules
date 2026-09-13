#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

PROPOSED_DIR=".jules/queue/proposed"
PENDING_DIR=".jules/queue/pending"

ACTION="${1:-list}"
PROPOSAL_ID="${2:-}"

case "$ACTION" in
    list)
        echo ""
        echo "════════════════════════════════════════════"
        echo "  Jules Proposals"
        echo "════════════════════════════════════════════"
        echo ""
        PROPOSALS=$(ls -1 "$PROPOSED_DIR"/*.json 2>/dev/null | grep -v '.gitkeep' || true)
        if [ -z "$PROPOSALS" ]; then
            echo "  No proposals."
            exit 0
        fi
        COUNT=$(echo "$PROPOSALS" | wc -l | tr -d ' ')
        echo "  Found $COUNT proposal(s):"
        echo ""
        for proposal in $PROPOSALS; do
            python3 - "$proposal" <<'PY'
import json, sys
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
print(f"  • [{d['id']}] Priority: {d.get('priority', 3)}")
print(f"    Source: {d.get('source_task', 'unknown')}")
print(f"    {d.get('description', '')[:100]}")
print()
PY
        done
        ;;
    accept)
        [ -z "$PROPOSAL_ID" ] && { echo "Usage: $0 accept <proposal-id>"; exit 1; }
        PROPOSAL_FILE="${PROPOSED_DIR}/${PROPOSAL_ID}.json"
        [ ! -f "$PROPOSAL_FILE" ] && { echo "Not found: $PROPOSAL_ID"; exit 1; }
        python3 - "$PROPOSAL_FILE" "$PENDING_DIR" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

proposal_file = Path(sys.argv[1])
pending_dir = Path(sys.argv[2])
pending_dir.mkdir(parents=True, exist_ok=True)

data = json.loads(proposal_file.read_text())
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
task_id = f"task-{timestamp}-{data['id'].split('-')[-1]}"

task = {
    "id": task_id,
    "priority": data.get("priority", 3),
    "request": data.get("description", ""),
    "status": "pending",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "proposed_by": "jules",
    "source_task": data.get("source_task"),
}
pending_file = pending_dir / f"{task_id}.json"
pending_file.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n")
proposal_file.unlink()
print(f"✅ Accepted: {data['id']} → {task_id}")
PY
        ;;
    reject)
        [ -z "$PROPOSAL_ID" ] && { echo "Usage: $0 reject <proposal-id>"; exit 1; }
        PROPOSAL_FILE="${PROPOSED_DIR}/${PROPOSAL_ID}.json"
        [ ! -f "$PROPOSAL_FILE" ] && { echo "Not found: $PROPOSAL_ID"; exit 1; }
        rm "$PROPOSAL_FILE"
        echo "❌ Rejected: $PROPOSAL_ID"
        ;;
    accept-all)
        for p in $(ls -1 "$PROPOSED_DIR"/*.json 2>/dev/null | grep -v '.gitkeep' || true); do
            "$0" accept "$(basename "$p" .json)"
        done
        ;;
    reject-all)
        for p in $(ls -1 "$PROPOSED_DIR"/*.json 2>/dev/null | grep -v '.gitkeep' || true); do
            "$0" reject "$(basename "$p" .json)"
        done
        ;;
    *)
        echo "Usage: $0 {list|accept|reject|accept-all|reject-all} [proposal-id]"
        exit 1
        ;;
esac
