#!/usr/bin/env bash
# Co-SMOS — full task cycle: dispatch → commit → wait → complete → verify
set -u
cd "$(dirname "$0")/.."

TASK_FILE="${1:-}"
if [ -z "$TASK_FILE" ] || [ ! -f "$TASK_FILE" ]; then
  echo "Usage: $0 <task-file> [--verify N]"
  exit 1
fi
shift

VERIFY_TASK=""
if [ "${1:-}" = "--verify" ] && [ -n "${2:-}" ]; then
  VERIFY_TASK="$2"
fi

if [ -z "${VIRTUAL_ENV:-}" ]; then
  source .venv/bin/activate
fi
export PATH="$HOME/.nvm/versions/node/v16.20.2/bin:$PATH"

echo "=== [1/5] Dispatch ==="
OUT=$(./scripts/jules-task.sh "$(cat "$TASK_FILE")" 2>&1)
echo "$OUT"
TASK_ID=$(echo "$OUT" | grep -oE "task-[0-9]{8}-[0-9]{6}" | head -1)
if [ -z "$TASK_ID" ]; then
  echo "ERROR: no TASK_ID"
  exit 1
fi
echo ">>> TASK_ID = $TASK_ID"

echo ""
echo "=== [2/5] Commit dispatch ==="
git add .co-smos/state.json .jules/tasks/${TASK_ID}.md 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m "chore: record ${TASK_ID} dispatch" || true
  git push origin main || true
fi

echo ""
echo "=== [3/5] Wait for Completed (max 15 min) ==="
ELAPSED=0
while [ "$ELAPSED" -lt 900 ]; do
  LINE=$(jules remote list --session 2>/dev/null | head -3 | grep -E "Completed|In Progress|Planning|Failed" | head -1)
  STATUS=$(echo "$LINE" | awk '{print $NF}')
  echo "  [+${ELAPSED}s] ${STATUS:-unknown}"
  [ "$STATUS" = "Completed" ] && break
  [ "$STATUS" = "Failed" ] && exit 2
  sleep 30
  ELAPSED=$((ELAPSED + 30))
done

echo ""
echo "=== [4/5] Complete ==="
./scripts/jules-complete.sh --task "$TASK_ID"

echo ""
echo "=== [5/5] Verify ==="
if [ -n "$VERIFY_TASK" ]; then
  ./scripts/verify.sh --task "$VERIFY_TASK" || true
else
  ./scripts/verify.sh --all 2>&1 | tail -5 || true
fi

echo ""
echo "Done: $TASK_ID"
