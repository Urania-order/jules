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
WARN_PRINTED=0

while [ "$ELAPSED" -lt "$MAX_WAIT_SEC" ]; do
  SESSION_LINE=""
  REMOTE_LIST=$(jules remote list --session 2>/dev/null || true)

  if [ -n "$REMOTE_LIST" ]; then
    # a) First: extract session_id from task log (.jules/results/<TASK_ID>.log)
    SESSION_ID=$(grep -oE 'ID: [0-9]+' ".jules/results/${TASK_ID}.log" 2>/dev/null | head -1 | awk '{print $2}' || true)
    if [ -n "${SESSION_ID:-}" ]; then
      SESSION_LINE=$(echo "$REMOTE_LIST" | grep -F "$SESSION_ID" | head -1 || true)
    fi

    # b) Second: TASK_MATCH (date part) — current
    if [ -z "$SESSION_LINE" ] && [ -n "${TASK_MATCH:-}" ]; then
      SESSION_LINE=$(echo "$REMOTE_LIST" | grep -F "$TASK_MATCH" | head -1 || true)
    fi

    # c) Third: DESC from ## Request section of task file
    if [ -z "$SESSION_LINE" ]; then
      DESC=""
      if [ -f "$TASK_FILE" ]; then
        DESC=$(awk '/^## Request/{flag=1;next}/^## /{flag=0}flag' "$TASK_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | head -1 | tr -d '\r\n' | head -c 40 || true)
      fi
      if [ -z "$DESC" ] && [ -f ".jules/tasks/${TASK_ID}.md" ]; then
        DESC=$(awk '/^## Request/{flag=1;next}/^## /{flag=0}flag' ".jules/tasks/${TASK_ID}.md" 2>/dev/null | grep -v '^[[:space:]]*$' | head -1 | tr -d '\r\n' | head -c 40 || true)
      fi
      if [ -n "${DESC:-}" ]; then
        SESSION_LINE=$(echo "$REMOTE_LIST" | grep -F "$DESC" | head -1 || true)
      fi
    fi

    # d) Fourth: DESC from anywhere in task file (last resort)
    if [ -z "$SESSION_LINE" ]; then
      DESC_ANY=""
      if [ -f "$TASK_FILE" ]; then
        DESC_ANY=$(grep -v '^#' "$TASK_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | head -1 | tr -d '\r\n' | head -c 40 || true)
        if [ -z "$DESC_ANY" ]; then
          DESC_ANY=$(grep -v '^[[:space:]]*$' "$TASK_FILE" 2>/dev/null | head -1 | tr -d '\r\n' | head -c 40 || true)
        fi
      fi
      if [ -z "$DESC_ANY" ] && [ -f ".jules/tasks/${TASK_ID}.md" ]; then
        DESC_ANY=$(grep -v '^#' ".jules/tasks/${TASK_ID}.md" 2>/dev/null | grep -v '^[[:space:]]*$' | head -1 | tr -d '\r\n' | head -c 40 || true)
      fi
      if [ -n "${DESC_ANY:-}" ]; then
        SESSION_LINE=$(echo "$REMOTE_LIST" | grep -F "$DESC_ANY" | head -1 || true)
      fi
    fi
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

  if [ -z "$STATUS" ] || [ "$STATUS" = "unknown" ]; then
      STATUS="unknown"
      if [ "$ELAPSED" -ge 60 ] && [ "$WARN_PRINTED" -eq 0 ]; then
          echo "  ⚠️ Warning: Session status still unknown after ${ELAPSED}s"
          WARN_PRINTED=1
      fi
  fi

  echo "  [+${ELAPSED}s] ${STATUS}"
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
