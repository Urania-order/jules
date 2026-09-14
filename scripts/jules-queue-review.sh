#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

PROPOSED_DIR=".jules/queue/proposed"
PENDING_DIR=".jules/queue/pending"
DEFERRED_DIR=".jules/queue/deferred"

FILTER_PRIORITY=""
FILTER_MIN_PRIORITY=""
FILTER_SOURCE=""
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --priority|-p)
            FILTER_PRIORITY="$2"
            shift 2
            ;;
        --priority=*)
            FILTER_PRIORITY="${1#*=}"
            shift 1
            ;;
        --min-priority)
            FILTER_MIN_PRIORITY="$2"
            shift 2
            ;;
        --min-priority=*)
            FILTER_MIN_PRIORITY="${1#*=}"
            shift 1
            ;;
        --source-task|--source|-s)
            FILTER_SOURCE="$2"
            shift 2
            ;;
        --source-task=*|--source=*|-s=*)
            FILTER_SOURCE="${1#*=}"
            shift 1
            ;;
        *)
            POSITIONAL+=("$1")
            shift 1
            ;;
    esac
done

set -- "${POSITIONAL[@]:-}"

ACTION="${1:-list}"
PROPOSAL_ID="${2:-}"
NOTE="${3:-}"
TTL_DAYS="${2:-}"

mkdir -p "$PROPOSED_DIR" "$PENDING_DIR" "$DEFERRED_DIR"

case "$ACTION" in
    list)
        echo ""
        echo "════════════════════════════════════════════"
        echo "  Jules Proposals (active)"
        echo "════════════════════════════════════════════"
        echo ""
        python3 - "$PROPOSED_DIR" "$FILTER_PRIORITY" "$FILTER_MIN_PRIORITY" "$FILTER_SOURCE" "active" <<'PY'
import json, sys
from pathlib import Path

target_dir = Path(sys.argv[1])
prio_filter = sys.argv[2].strip()
min_prio_filter = sys.argv[3].strip()
source_filter = sys.argv[4].strip()
mode = sys.argv[5]

def parse_prio(val_str):
    if not val_str:
        return None
    val_str_lower = val_str.lower()
    if val_str_lower in ("high",):
        return 10
    elif val_str_lower in ("normal", "medium"):
        return 5
    elif val_str_lower in ("low",):
        return 1
    elif val_str.isdigit():
        return int(val_str)
    return None

prio_num = parse_prio(prio_filter)
min_prio_num = parse_prio(min_prio_filter)

proposal_files = sorted(target_dir.glob("*.json"))
matching_proposals = []

for p_file in proposal_files:
    if p_file.name == ".gitkeep":
        continue
    try:
        d = json.loads(p_file.read_text())
    except Exception:
        continue

    # Filter by exact priority / text mapping
    p_val = d.get("priority", 3)
    try:
        p_val = int(p_val)
    except (ValueError, TypeError):
        p_val = 3

    if prio_num is not None and p_val != prio_num:
        continue

    if min_prio_num is not None and p_val < min_prio_num:
        continue

    # Filter by source task substring/match
    if source_filter:
        src = str(d.get("source_task", ""))
        if source_filter.lower() not in src.lower():
            continue

    matching_proposals.append(d)

if not matching_proposals:
    if prio_filter or min_prio_filter or source_filter:
        echo_filters = []
        if prio_filter: echo_filters.append(f"priority={prio_filter}")
        if min_prio_filter: echo_filters.append(f"min-priority={min_prio_filter}")
        if source_filter: echo_filters.append(f"source-task={source_filter}")
        print(f"  No active proposals matching filter ({', '.join(echo_filters)}).")
    else:
        print("  No active proposals.")
else:
    filter_desc = ""
    echo_filters = []
    if prio_filter: echo_filters.append(f"priority: {prio_filter}")
    if min_prio_filter: echo_filters.append(f"min-priority: {min_prio_filter}")
    if source_filter: echo_filters.append(f"source: {source_filter}")
    if echo_filters:
        filter_desc = f" (filtered by {', '.join(echo_filters)})"

    print(f"  Found {len(matching_proposals)} proposal(s){filter_desc}:")
    print("")
    for d in matching_proposals:
        print(f"  • [{d['id']}] Priority: {d.get('priority', 3)}")
        print(f"    Source: {d.get('source_task', 'unknown')}")
        print(f"    {d.get('description', '')[:100]}")
        if d.get("expires_at"):
            print(f"    ⏳ Expires: {d['expires_at']}")
        if d.get("notes"):
            print(f"    📝 Notes: {len(d['notes'])} note(s)")
        print()
PY
        ;;
    deferred)
        echo ""
        echo "════════════════════════════════════════════"
        echo "  Jules Proposals (deferred)"
        echo "════════════════════════════════════════════"
        echo ""
        python3 - "$DEFERRED_DIR" "$FILTER_PRIORITY" "$FILTER_MIN_PRIORITY" "$FILTER_SOURCE" "deferred" <<'PY'
import json, sys
from pathlib import Path

target_dir = Path(sys.argv[1])
prio_filter = sys.argv[2].strip()
min_prio_filter = sys.argv[3].strip()
source_filter = sys.argv[4].strip()
mode = sys.argv[5]

def parse_prio(val_str):
    if not val_str:
        return None
    val_str_lower = val_str.lower()
    if val_str_lower in ("high",):
        return 10
    elif val_str_lower in ("normal", "medium"):
        return 5
    elif val_str_lower in ("low",):
        return 1
    elif val_str.isdigit():
        return int(val_str)
    return None

prio_num = parse_prio(prio_filter)
min_prio_num = parse_prio(min_prio_filter)

proposal_files = sorted(target_dir.glob("*.json"))
matching_proposals = []

for p_file in proposal_files:
    if p_file.name == ".gitkeep":
        continue
    try:
        d = json.loads(p_file.read_text())
    except Exception:
        continue

    p_val = d.get("priority", 3)
    try:
        p_val = int(p_val)
    except (ValueError, TypeError):
        p_val = 3

    if prio_num is not None and p_val != prio_num:
        continue

    if min_prio_num is not None and p_val < min_prio_num:
        continue

    if source_filter:
        src = str(d.get("source_task", ""))
        if source_filter.lower() not in src.lower():
            continue

    matching_proposals.append(d)

if not matching_proposals:
    if prio_filter or min_prio_filter or source_filter:
        echo_filters = []
        if prio_filter: echo_filters.append(f"priority={prio_filter}")
        if min_prio_filter: echo_filters.append(f"min-priority={min_prio_filter}")
        if source_filter: echo_filters.append(f"source-task={source_filter}")
        print(f"  No deferred proposals matching filter ({', '.join(echo_filters)}).")
    else:
        print("  No deferred proposals.")
else:
    filter_desc = ""
    echo_filters = []
    if prio_filter: echo_filters.append(f"priority: {prio_filter}")
    if min_prio_filter: echo_filters.append(f"min-priority: {min_prio_filter}")
    if source_filter: echo_filters.append(f"source: {source_filter}")
    if echo_filters:
        filter_desc = f" (filtered by {', '.join(echo_filters)})"

    print(f"  Found {len(matching_proposals)} deferred proposal(s){filter_desc}:")
    print("")
    for d in matching_proposals:
        print(f"  • [{d['id']}] Priority: {d.get('priority', 3)}")
        print(f"    Source: {d.get('source_task', 'unknown')}")
        print(f"    {d.get('description', '')[:100]}")
        if d.get("deferred_at"):
            print(f"    ⏸️  Deferred: {d['deferred_at']}")
        if d.get("notes"):
            print(f"    📝 Notes: {len(d['notes'])} note(s)")
        print()
PY
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
    "notes": data.get("notes", []),
}
pending_file = pending_dir / f"{task_id}.json"
pending_file.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n")
proposal_file.unlink()
print(f"✅ Accepted: {data['id']} → {task_id}")
PY
        ;;
    defer|reject)
        [ -z "$PROPOSAL_ID" ] && { echo "Usage: $0 reject|defer <proposal-id> [note]"; exit 1; }
        PROPOSAL_FILE="${PROPOSED_DIR}/${PROPOSAL_ID}.json"
        [ ! -f "$PROPOSAL_FILE" ] && { echo "Not found: $PROPOSAL_ID"; exit 1; }
        python3 - "$PROPOSAL_FILE" "$DEFERRED_DIR" "$NOTE" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

proposal_file = Path(sys.argv[1])
deferred_dir = Path(sys.argv[2])
note = sys.argv[3] if len(sys.argv) > 3 else ""

deferred_dir.mkdir(parents=True, exist_ok=True)

data = json.loads(proposal_file.read_text())
data["status"] = "deferred"
data["deferred_at"] = datetime.now(timezone.utc).isoformat()
if note:
    data.setdefault("notes", []).append({
        "text": note,
        "added_at": datetime.now(timezone.utc).isoformat(),
    })

deferred_file = deferred_dir / proposal_file.name
deferred_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
proposal_file.unlink()
print(f"⏸️  Deferred: {data['id']} → {deferred_file.name}")
PY
        ;;
    restore)
        [ -z "$PROPOSAL_ID" ] && { echo "Usage: $0 restore <proposal-id>"; exit 1; }
        DEFERRED_FILE="${DEFERRED_DIR}/${PROPOSAL_ID}.json"
        [ ! -f "$DEFERRED_FILE" ] && { echo "Not found: $PROPOSAL_ID"; exit 1; }
        python3 - "$DEFERRED_FILE" "$PROPOSED_DIR" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

deferred_file = Path(sys.argv[1])
proposed_dir = Path(sys.argv[2])
proposed_dir.mkdir(parents=True, exist_ok=True)

data = json.loads(deferred_file.read_text())
data["status"] = "proposed"
data["restored_at"] = datetime.now(timezone.utc).isoformat()

proposed_file = proposed_dir / deferred_file.name
proposed_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
deferred_file.unlink()
print(f"✅ Restored: {data['id']} → {proposed_file.name}")
PY
        ;;
    append)
        [ -z "$PROPOSAL_ID" ] || [ -z "$NOTE" ] && { echo "Usage: $0 append <proposal-id> <note>"; exit 1; }
        # Спробувати в proposed/, потім в deferred/
        for DIR in "$PROPOSED_DIR" "$DEFERRED_DIR"; do
            PROPOSAL_FILE="${DIR}/${PROPOSAL_ID}.json"
            if [ -f "$PROPOSAL_FILE" ]; then
                python3 - "$PROPOSAL_FILE" "$NOTE" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

proposal_file = Path(sys.argv[1])
note = sys.argv[2]

data = json.loads(proposal_file.read_text())
data.setdefault("notes", []).append({
    "text": note,
    "added_at": datetime.now(timezone.utc).isoformat(),
})
proposal_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"📝 Note added to {data['id']}: {note[:60]}")
PY
                exit 0
            fi
        done
        echo "Not found: $PROPOSAL_ID"
        exit 1
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
    expire)
        python3 - "$PROPOSED_DIR" "$DEFERRED_DIR" "$TTL_DAYS" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

proposed_dir = Path(sys.argv[1])
deferred_dir = Path(sys.argv[2])
default_ttl = int(sys.argv[3]) if sys.argv[3] and sys.argv[3].isdigit() else 7

deferred_dir.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc)
expired_count = 0

for proposal_file in proposed_dir.glob("*.json"):
    if proposal_file.name == ".gitkeep":
        continue
    try:
        data = json.loads(proposal_file.read_text())
    except Exception:
        continue

    is_expired = False
    if "expires_at" in data:
        try:
            exp_dt = datetime.fromisoformat(data["expires_at"])
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if now >= exp_dt:
                is_expired = True
        except ValueError:
            pass
    elif "created_at" in data:
        try:
            created_dt = datetime.fromisoformat(data["created_at"])
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if now >= created_dt + timedelta(days=default_ttl):
                is_expired = True
        except ValueError:
            pass

    if is_expired:
        data["status"] = "expired"
        data["expired_at"] = now.isoformat()
        deferred_file = deferred_dir / proposal_file.name
        deferred_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        proposal_file.unlink()
        expired_count += 1
        print(f"⏰ Expired: {data['id']} → {deferred_file.name}")

if expired_count == 0:
    print("No aged proposals to expire.")
else:
    print(f"Expired {expired_count} aged proposal(s).")
PY
        ;;
    *)
        echo "Usage: $0 [--priority|-p <val>] [--min-priority <val>] [--source-task|-s <id>] {list|deferred|accept|reject|restore|append|accept-all|reject-all|expire} [proposal-id|ttl-days] [note]"
        exit 1
        ;;
esac
