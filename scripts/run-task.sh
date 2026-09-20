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
echo "=== [3/5] Wait for Completed ==="
MAX_WAIT_SEC="${JULES_MAX_WAIT_SEC:-900}"
POLL_INTERVAL="${JULES_POLL_INTERVAL:-30}"
ELAPSED=0
TASK_MATCH=$(echo "$TASK_ID" | sed 's/^task-//')
STATUS=""

while [ "$ELAPSED" -lt "$MAX_WAIT_SEC" ]; do
  SESSION_LINE=$(jules remote list --session 2>/dev/null | grep -F "$TASK_MATCH" | head -1)
  if [ -z "$SESSION_LINE" ]; then
      DESC=$(head -c 40 "$TASK_FILE" | tr -d '\n')
      SESSION_LINE=$(jules remote list --session 2>/dev/null | grep -F "$DESC" | head -1)
  fi
  STATUS=$(echo "$SESSION_LINE" | awk '{print $NF}')

  if [ "$STATUS" = "Completed" ]; then
      echo "  ✅ Completed"
      break
  fi
  if [ "$STATUS" = "Failed" ]; then
      echo "  ❌ Failed"
      exit 2
  fi

  echo "  [+${ELAPSED}s] ${STATUS:-unknown}"
  sleep "$POLL_INTERVAL"
  ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

if [ "$STATUS" != "Completed" ]; then
  echo "  ⚠ Timeout after ${MAX_WAIT_SEC}s — session still ${STATUS:-unknown}"
  echo "  Run manually: ./scripts/jules-complete.sh --task $TASK_ID"
  exit 3
fi

echo ""
echo "=== [4/5] Complete ==="
./scripts/jules-complete.sh --task "$TASK_ID"

RESULT=$(python3 -c "
import json
try:
    s = json.load(open('.co-smos/state.json'))
    lt = s.get('last_task') or {}
    print(lt.get('result', 'unknown'))
except Exception:
    print('unknown')
" 2>/dev/null)

case "$RESULT" in
    applied)
        echo "✅ APPLIED: $TASK_ID"
        ;;
    no-op)
        echo "⚠️  NO-OP: Jules may still be running or returned empty diff"
        echo "   Check: jules remote list --session"
        exit 4
        ;;
    error)
        echo "❌ ERROR: check post-complete log"
        exit 5
        ;;
    *)
        echo "❓ UNKNOWN result: $RESULT"
        exit 6
        ;;
esac

echo ""
echo "=== [5/5] Verify ==="
if [ -n "$VERIFY_TASK" ]; then
  ./scripts/verify.sh --task "$VERIFY_TASK" || true
else
  ./scripts/verify.sh --all 2>&1 | tail -5 || true
fi

echo ""
echo "Done: $TASK_ID"
