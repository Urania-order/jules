#!/usr/bin/env bash
# scripts/jules-complete.sh
# Atomically complete a Jules task.

set -euo pipefail

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")}"
cd "$PROJECT_ROOT"

STATE_FILE=".co-smos/state.json"
TASKS_DIR=".jules/tasks"
RESULTS_DIR=".jules/results"

SESSION_ID=""
TASK_ID=""
FORCE="${FORCE:-0}"

if [ $# -eq 0 ]; then
  echo "Usage: ./scripts/jules-complete.sh <SESSION_ID>"
  echo "       ./scripts/jules-complete.sh --task <TASK_ID> [--force]"
  exit 1
fi

POSITIONAL_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --task)
      [ -z "${2:-}" ] && { echo "ERROR: --task requires TASK_ID"; exit 1; }
      TASK_ID="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: ./scripts/jules-complete.sh <SESSION_ID>"
      echo "       ./scripts/jules-complete.sh --task <TASK_ID> [--force]"
      exit 0
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ -z "$SESSION_ID" ] && [ ${#POSITIONAL_ARGS[@]} -gt 0 ]; then
  SESSION_ID="${POSITIONAL_ARGS[0]}"
fi

# Normalize stale history entries in .co-smos/state.json (idempotent)
python3 - <<'PY'
import json, os
from pathlib import Path

state_file = Path(".co-smos/state.json")
if state_file.exists():
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        modified = False

        def normalize_task(t):
            if not isinstance(t, dict):
                return False
            tid = t.get("id")
            title = t.get("title")
            req = t.get("request") or t.get("description")

            new_title = None
            if not title:
                new_title = (req.split("\n")[0][:80] if req else tid)
            elif tid and title == tid and req and req != tid:
                new_title = req.split("\n")[0][:80]

            if new_title and new_title != title:
                t["title"] = new_title
                return True
            return False

        for h in data.get("history", []):
            if normalize_task(h):
                modified = True
        if normalize_task(data.get("active_task")):
            modified = True
        if normalize_task(data.get("last_task")):
            modified = True

        if modified:
            state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass
PY

# Setup logging
mkdir -p "$RESULTS_DIR"
TIMESTAMP_LOG="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="${RESULTS_DIR}/post-complete-${TIMESTAMP_LOG}.log"

log_step() {
  local step="$1"
  local status="$2"
  local exit_code="$3"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "${ts} | step=${step} | status=${status} | exit_code=${exit_code}" >> "$LOG_FILE"
}

echo ""
echo "================================================"
echo " Jules Co-SMOS — Complete Task"
echo "================================================"
echo " Project root: $PROJECT_ROOT"
[ -n "$SESSION_ID" ] && echo " Session ID:   $SESSION_ID"
[ -n "$TASK_ID" ]    && echo " Task ID:      $TASK_ID"
echo " Log file:     $LOG_FILE"
echo ""

if [ -z "$TASK_ID" ]; then
  if [ ! -f "$STATE_FILE" ]; then
    echo "ERROR: $STATE_FILE not found and --task not provided."
    exit 3
  fi
  TASK_ID="$(python3 -c "
import json
try:
    s = json.load(open('$STATE_FILE'))
    a = s.get('active_task') or {}
    print(a.get('id') or '')
except Exception:
    print('')
")"
fi

if [ -z "$TASK_ID" ]; then
  echo "ERROR: could not determine TASK_ID (no active_task in state.json)."
  exit 3
fi

TASK_FILE="$TASKS_DIR/${TASK_ID}.md"
# Resolve SESSION_ID from log if empty
if [ -z "$SESSION_ID" ] && [ -n "$TASK_ID" ]; then
  TASK_LOG="${RESULTS_DIR}/${TASK_ID}.log"
  if [ -f "$TASK_LOG" ]; then
    SESSION_ID="$(grep -m1 '^ID:' "$TASK_LOG" | awk '{print $2}' || true)"
    if [ -n "$SESSION_ID" ]; then
      echo " Resolved SESSION_ID from log: $SESSION_ID"
    fi
  fi
fi

if [ -z "$SESSION_ID" ]; then
  echo "ERROR: could not determine SESSION_ID (no --session, no active_task, no log)."
  echo "       Hint: check ${RESULTS_DIR}/${TASK_ID}.log for 'ID: <session>'"
  exit 3
fi

echo " Resolved TASK_ID: $TASK_ID"

# --- idempotency check (ERRATA-0016, ERRATA-0036) ---
if [ "${FORCE:-0}" != "1" ]; then
  if python3 -c "
import json, sys
try:
    s = json.load(open('$STATE_FILE'))
    for h in s.get('history', []):
        if h.get('id') == '$TASK_ID' and h.get('result') == 'applied':
            sys.exit(0)
    lt = s.get('last_task') or {}
    if lt.get('id') == '$TASK_ID' and lt.get('result') == 'applied':
        sys.exit(0)
    sys.exit(1)
except Exception:
    sys.exit(1)
"; then
    echo ""
    echo "Task $TASK_ID is already completed and applied."
    echo "Skipping to avoid a duplicate pull."
    echo ""
    exit 0
  fi
fi
# --- end idempotency check ---

echo ""

# STEP [1/9]
if [ -f .git/index.lock ] && ! pgrep -f "git" > /dev/null; then
  rm -f .git/index.lock
fi

STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "[1/9] Stashing local changes..."
  git stash push -u -m "jules-complete: pre-pull stash for $TASK_ID" >/dev/null
  STASHED=1
else
  echo "[1/9] No local changes to stash."
fi
log_step "[1/9]" "OK" 0

# STEP [2/9]
echo "[2/9] Pulling result from Jules..."
PULL_OUT="$(jules remote pull --session "$SESSION_ID" --apply 2>&1 || true)"
echo "$PULL_OUT" | sed 's/^/      /'

if echo "$PULL_OUT" | grep -q "No diff found in the remote VM"; then
  PULL_RESULT="no-op"
  echo "      → No diff found. Marking as no-op."
elif echo "$PULL_OUT" | grep -qi "error\|failed\|conflict"; then
  PULL_RESULT="error"
  echo "      → Pull reported errors. Will record but continue."
else
  PULL_RESULT="applied"
fi
log_step "[2/9]" "$PULL_RESULT" 0

# STEP [3/9]
if [ "$STASHED" -eq 1 ]; then
  echo "[3/9] Restoring local changes..."
  if ! git stash pop >/dev/null 2>&1; then
    echo "      WARNING: stash pop reported conflicts. Resolve manually."
  fi
else
  echo "[3/9] No stash to restore."
fi
log_step "[3/9]" "OK" 0

# STEP [4/9]
echo "[4/9] Current git status:"
git status --short | sed 's/^/      /'
echo ""
echo "      Diff stat (HEAD):"
git diff HEAD --stat | sed 's/^/      /' || true
echo ""

# --- post-pull forbidden paths check (ERRATA-0012, refined) ---
FORBIDDEN_VIOLATIONS="$(git diff --name-only HEAD 2>/dev/null \
  | grep -E '^\.(co-smos|jules/(tasks|results|queue))/' \
  | grep -v '^\.co-smos/state\.json$' \
  | grep -v "^\.jules/tasks/${TASK_ID}\.md$" \
  | grep -v "^\.jules/results/${TASK_ID}\.log$" \
  | grep -v "^\.jules/results/post-complete-.*\.log$" \
  || true)"
if [ -n "$FORBIDDEN_VIOLATIONS" ]; then
  echo "      WARNING: unexpected changes in forbidden paths:"
  echo "$FORBIDDEN_VIOLATIONS" | sed 's/^/        /'
  echo "      -> See ERRATA-0012"
  echo "      -> Jules should not modify these; review and revert if needed"
else
  echo "      post-pull check: no unexpected forbidden path changes"
fi
echo ""

# --- clean untracked files in forbidden paths (ERRATA-0015) ---
# Preserve admin queue files and sidecars as legitimate queue items
FORBIDDEN_UNTRACKED="$(git ls-files --others --exclude-standard 2>/dev/null \
  | grep -E '^\.(co-smos|jules/(tasks|results|queue))/' \
  | grep -v "^\.jules/tasks/${TASK_ID}\.md$" \
  | grep -v "^\.jules/results/${TASK_ID}\.log$" \
  | grep -v "^\.jules/results/post-complete-.*\.log$" \
  | grep -v "^\.jules/queue/pending/admin-.*\.txt$" \
  | grep -v "^\.jules/queue/running/admin-.*\.txt$" \
  | grep -v "^\.jules/queue/completed/admin-.*\.txt$" \
  | grep -v "^\.jules/queue/pending/.*\.meta\.json$" \
  | grep -v "^\.jules/queue/running/.*\.meta\.json$" \
  | grep -v "^\.jules/queue/completed/.*\.meta\.json$" \
  || true)"

if [ -n "$FORBIDDEN_UNTRACKED" ]; then
  echo "      WARNING: untracked files in forbidden paths detected:"
  echo "$FORBIDDEN_UNTRACKED" | sed 's/^/        /'
  echo ""
  echo "      Moving them to .jules/queue/deferred/ ..."
  mkdir -p .jules/queue/deferred
  COUNT=0
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if [ -f "$f" ]; then
      base="$(basename "$f")"
      target=".jules/queue/deferred/${base}"
      if [ -e "$target" ]; then
        target=".jules/queue/deferred/${base}.$$"
      fi
      mv "$f" "$target" && COUNT=$((COUNT + 1))
    fi
  done <<< "$FORBIDDEN_UNTRACKED"
  echo "      Moved $COUNT file(s) to .jules/queue/deferred/"
  echo "      See ERRATA-0015 for details."
  echo ""
else
  echo "      no untracked files in forbidden paths"
fi
echo ""
log_step "[4/9]" "OK" 0

# STEP [5/9]
echo "[5/9] Updating $STATE_FILE..."
SESSION_ID="$SESSION_ID" TASK_ID="$TASK_ID" PULL_RESULT="$PULL_RESULT" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
from pathlib import Path

state_file = Path(".co-smos/state.json")
task_id = os.environ["TASK_ID"]
session_id = os.environ.get("SESSION_ID") or ""
pull_result = os.environ.get("PULL_RESULT", "unknown")

if state_file.exists():
    try:
        state = json.loads(state_file.read_text())
    except Exception:
        state = {}
else:
    state = {}

state.setdefault("version", 1)
state.setdefault("project", "jules-codespace")
state.setdefault("agent", "jules")
state.setdefault("history", [])

active = state.get("active_task") or {}
now = datetime.now(timezone.utc).isoformat()

req = active.get("request") or active.get("description")
title = active.get("title")

completed = {
    "id": task_id,
    "status": "completed",
    "session_id": session_id or active.get("session_id"),
    "branch": active.get("branch") or state.get("branch"),
    "request": req,
    "title": title,
    "priority": active.get("priority", 5),
    "created_at": active.get("created_at"),
    "proposed_by": active.get("proposed_by"),
    "source_task": active.get("source_task"),
    "started_at": active.get("started_at"),
    "finished_at": now,
    "result": pull_result,
}

if not completed.get("title") or completed.get("title") == task_id:
    mdfile = Path(f".jules/tasks/{task_id}.md")
    if mdfile.exists():
        content = mdfile.read_text(encoding="utf-8")
        lines = content.split("\n")
        # Try "## Request" section first
        in_req = False
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("## Request"):
                in_req = True
                continue
            if in_req and line_stripped and not line_stripped.startswith("#"):
                completed["title"] = line_stripped[:120]
                break
        # Fallback: first heading (not "Jules Task")
        if not completed.get("title") or completed.get("title") == task_id:
            for line in lines:
                line_stripped = line.strip()
                if line_stripped.startswith("# ") and "Jules Task" not in line_stripped:
                    completed["title"] = line_stripped[2:120]
                    break

if not completed.get("title") or completed.get("title") == task_id:
    if completed.get("request") and completed.get("request") != task_id:
        completed["title"] = completed["request"].split("\n")[0][:120]
    else:
        completed["title"] = task_id

if not completed.get("request"):
    completed["request"] = completed.get("title")

state["last_task"] = completed
state["active_task"] = None
state["status"] = "ready"
state["history"].append(completed)

state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
print(f"      state.json updated: {task_id} -> completed (result={pull_result})")

import re
normalized_count = 0

def _norm_entry(entry):
    if not isinstance(entry, dict):
        return False
    tid = entry.get("id")
    if not tid or not isinstance(tid, str):
        return False
    m = re.match(r"^task-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", tid)
    if not m:
        return False
    iso_val = f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:{m.group(6)}+00:00"
    if entry.get("created_at") != iso_val:
        entry["created_at"] = iso_val
        return True
    return False

for h in state.get("history", []):
    if _norm_entry(h):
        normalized_count += 1
if _norm_entry(state.get("active_task")):
    normalized_count += 1
if _norm_entry(state.get("last_task")):
    normalized_count += 1

if normalized_count > 0:
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")

print(f"normalized created_at for {normalized_count} task(s)")
PY
log_step "[5/9]" "OK" 0

# STEP [6/9]
if [ -f "$TASK_FILE" ]; then
  echo "[6/9] Updating task record: $TASK_FILE"
  {
    echo ""
    echo "## Final Status"
    echo ""
    echo "completed"
    echo ""
    echo "## Result"
    echo ""
    echo "pull result: $PULL_RESULT"
    echo ""
    echo "Session: $SESSION_ID"
    echo ""
    echo "Completed at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >> "$TASK_FILE"
else
  echo "[6/9] WARNING: $TASK_FILE not found, skipping."
fi
log_step "[6/9]" "OK" 0

# STEP [7/9]
echo "[7/9] Running tests..."
if [ "${JULES_SKIP_TESTS:-0}" = "1" ]; then
  echo "      JULES_SKIP_TESTS=1: Skipping test execution."
  log_step "[7/9]" "SKIPPED" 0
else
  TEST_OUT_FILE="$(mktemp)"
  if uv run pytest tests/ -q > "$TEST_OUT_FILE" 2>&1; then
    echo "      ✅ Tests passed"
    tail -10 "$TEST_OUT_FILE" | sed 's/^/      /' || true
    rm -f "$TEST_OUT_FILE"
    log_step "[7/9]" "PASSED" 0
  else
    echo "❌ Tests FAILED"
    echo "→ Commits NOT created"
    echo "→ Changes preserved in working tree"
    echo "→ To inspect: git status"
    echo "→ To rollback manually: git checkout -- ."
    echo "→ To re-run: ./scripts/jules-complete.sh --task $TASK_ID"
    echo ""
    echo "--- Test Output (tail -30) ---"
    tail -30 "$TEST_OUT_FILE" || true
    echo ""
    echo "--- Git Status ---"
    git status || true
    echo ""
    echo "--- Current Commit ---"
    git log -1 --oneline || true
    rm -f "$TEST_OUT_FILE"
    log_step "[7/9]" "FAILED" 1
    exit 1
  fi
fi

# STEP [8/9]
echo "[8/9] Committing and pushing..."

safe_git_commit() {
  local msg="$1"
  for attempt in 1 2 3; do
    if [ -f .git/index.lock ] && ! pgrep -f "git commit" > /dev/null; then
      rm -f .git/index.lock
    fi
    if git commit -m "$msg"; then return 0; fi
    echo "⚠ commit attempt $attempt failed — retry in 3s"
    sleep 3
    rm -f .git/index.lock
  done
  return 1
}

safe_git_push() {
  local branch="${1:-main}"
  for attempt in 1 2 3; do
    if git push origin "$branch"; then return 0; fi
    sleep 5
  done
  return 1
}

CODE_PATHS=()
for p in frontend smos tests docs scripts Dockerfile .devcontainer .gitignore; do
  [ -e "$p" ] && CODE_PATHS+=("$p")
done

if [ ${#CODE_PATHS[@]} -gt 0 ]; then
  git add "${CODE_PATHS[@]}" 2>/dev/null || true
  if ! git diff --cached --quiet; then
    if safe_git_commit "feat: apply Jules result for $TASK_ID

Session: $SESSION_ID
Pull result: $PULL_RESULT"; then
      echo "      -> code commit done"
    else
      echo "      -> code commit failed"
    fi
  else
    echo "      -> no code changes to commit"
  fi
fi

ART_PATHS=(".co-smos" ".jules/tasks" ".jules/results" ".jules/history" ".jules/errata")
for p in "${ART_PATHS[@]}"; do
  [ -e "$p" ] && git add "$p" 2>/dev/null || true
done
if ! git diff --cached --quiet; then
  if safe_git_commit "chore: record Co-SMOS artifacts for $TASK_ID

Session: $SESSION_ID
Pull result: $PULL_RESULT"; then
    echo "      -> artifacts commit done"
  else
    echo "      -> artifacts commit failed"
  fi
else
  echo "      -> no artifacts to commit"
fi

if [ "${JULES_NO_PUSH:-0}" = "1" ]; then
  echo "      JULES_NO_PUSH=1: Skipping git push."
  log_step "[8/9]" "OK_NO_PUSH" 0
else
  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  if git remote get-url origin >/dev/null 2>&1; then
    echo "      pushing $CURRENT_BRANCH -> origin..."
    if safe_git_push "$CURRENT_BRANCH"; then
      echo "      -> push done"
    else
      echo "      WARNING: push failed"
    fi
  fi
  log_step "[8/9]" "OK" 0
fi

# STEP [9/9]
echo "[9/9] Waiting for CI..."
if [ "${JULES_SKIP_CI:-0}" = "1" ] || [ "${JULES_NO_PUSH:-0}" = "1" ]; then
  echo "      Skipping CI check (JULES_SKIP_CI=1 or JULES_NO_PUSH=1)"
  log_step "[9/9]" "SKIPPED" 0
else
  TIMEOUT="${JULES_CI_TIMEOUT:-300}"
  if [ "$TIMEOUT" -lt 15 ]; then
    INTERVAL="$TIMEOUT"
    [ "$INTERVAL" -lt 1 ] && INTERVAL=1
  else
    INTERVAL=15
  fi

  MAX_POLLS=$(( TIMEOUT / INTERVAL ))
  if [ "$MAX_POLLS" -lt 1 ]; then
    MAX_POLLS=1
  fi

  CI_STATUS=""
  for ((i=1; i<=MAX_POLLS; i++)); do
    sleep "$INTERVAL"
    CI_STATUS="$(gh run list --repo Urania-order/jules --limit 1 --json conclusion --jq '.[0].conclusion' 2>/dev/null || echo "")"
    if [ "$CI_STATUS" != "null" ] && [ -n "$CI_STATUS" ]; then
      break
    fi
  done

  if [ "$CI_STATUS" = "success" ]; then
    echo "      ✅ CI passed"
    log_step "[9/9]" "SUCCESS" 0
  elif [ "$CI_STATUS" = "failure" ]; then
    echo "      ❌ CI FAILED"
    echo "      → Commits ARE pushed"
    echo "      → To revert: git revert HEAD~2..HEAD && git push"
    echo "      → Or fix and push again"
    log_step "[9/9]" "FAILED" 1
    exit 1
  else
    echo "      ⏳ CI timeout"
    echo "      → Check manually: gh run list --repo Urania-order/jules"
    log_step "[9/9]" "TIMEOUT" 0
    exit 0
  fi
fi

echo ""
echo "================================================"
echo " Task completed"
echo "================================================"
echo ""
echo "Task ID:  $TASK_ID"
echo "Session:  $SESSION_ID"
echo "Result:   $PULL_RESULT"
echo ""
