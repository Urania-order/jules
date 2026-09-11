#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

STATE_FILE=".co-smos/state.json"

echo ""
echo "=========================================="
echo " Jules Co-SMOS Status"
echo "=========================================="
echo ""

echo "[Git]"
echo "  Branch:         $(git branch --show-current)"
echo "  Last commit:    $(git log --oneline -1 2>/dev/null || echo 'none')"
echo "  Uncommitted:    $(git status --porcelain | wc -l) file(s)"
echo ""

echo "[Co-SMOS State]"
if [ -f "$STATE_FILE" ] && command -v python3 >/dev/null 2>&1; then
    python3 - "$STATE_FILE" <<'PY'
import json, sys
from pathlib import Path

p = Path(sys.argv[1])
state = json.loads(p.read_text())

print(f"  Status:       {state.get('status', 'unknown')}")
print(f"  Project:      {state.get('project', 'unknown')}")
print(f"  Agent:        {state.get('agent', 'unknown')}")

active = state.get("active_task")
if active:
    print("")
    print("  Active task:")
    print(f"    ID:         {active.get('id')}")
    print(f"    Branch:     {active.get('branch', '-')}")
    print(f"    Started:    {active.get('started_at', '-')}")
    req = active.get('request', '-')
    print(f"    Request:    {req[:80]}{'...' if len(req) > 80 else ''}")
else:
    print("  Active task:  none")

last = state.get("last_task")
if last:
    print("")
    print("  Last task:")
    print(f"    ID:         {last.get('id')}")
    print(f"    Status:     {last.get('status', '-')}")
    print(f"    Finished:   {last.get('finished_at', '-')}")

history = state.get("history", [])
if history:
    print("")
    print(f"  History:      {len(history)} entries")
PY
else
    echo "  state.json not found or python3 missing"
fi
echo ""

echo "[Jules Sessions]"
if command -v jules >/dev/null 2>&1; then
    jules remote list --session 2>&1 | head -6
else
    echo "  jules CLI not in PATH"
fi
echo ""

echo "[Task Artifacts]"
echo "  Tasks:"
ls -1t .jules/tasks/*.md 2>/dev/null | head -5 | sed 's/^/    /' || echo "    (none)"
echo ""
echo "  Results:"
ls -1t .jules/results/*.log 2>/dev/null | head -5 | sed 's/^/    /' || echo "    (none)"
echo ""

echo "[Branches]"
echo "  Local:"
git branch --list | sed 's/^/    /'
echo ""
echo "  Remote (jules/*):"
git branch -r --list 'origin/jules/*' 2>/dev/null | head -5 | sed 's/^/    /' || echo "    (none)"
echo ""

echo "=========================================="
echo " Done"
echo "=========================================="
echo ""
