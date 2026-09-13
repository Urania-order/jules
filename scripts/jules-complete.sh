#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Jules Complete — автоматизація завершення завдання
# ============================================================
#
# Usage:
#   ./scripts/jules-complete.sh <task-id> <session-id> <branch-name>
#
# Example:
#   ./scripts/jules-complete.sh task-20260912-194341 7828326494924666542 feat/my-feature
#
# ============================================================

PROJECT_ROOT="${JULES_PROJECT_ROOT:-$(git rev-parse --show-toplevel)}"
cd "$PROJECT_ROOT"

TASK_ID="${1:-}"
SESSION_ID="${2:-}"
BRANCH_NAME="${3:-}"

if [ -z "$TASK_ID" ] || [ -z "$SESSION_ID" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Usage: ./scripts/jules-complete.sh <task-id> <session-id> <branch-name>"
    echo ""
    echo "Example:"
    echo "  ./scripts/jules-complete.sh task-20260912-194341 7828326494924666542 feat/my-feature"
    echo ""
    echo "Available tasks:"
    ls -1t .jules/tasks/*.md 2>/dev/null | sed 's|.jules/tasks/||; s|\.md$||' | head -5 | sed 's/^/  /' || echo "  (none)"
    exit 1
fi

STATE_FILE=".co-smos/state.json"
TASK_FILE=".jules/tasks/${TASK_ID}.md"

echo ""
echo "════════════════════════════════════════════"
echo "  JULES COMPLETE"
echo "════════════════════════════════════════════"
echo ""
echo "Task ID:     $TASK_ID"
echo "Session ID:  $SESSION_ID"
echo "Branch:      $BRANCH_NAME"
echo ""

# --- Step 1: Pull result from Jules ---
echo "[1/8] Pulling result from Jules..."

set +e
PULL_OUTPUT=$(jules remote pull --session "$SESSION_ID" --apply 2>&1)
PULL_EXIT=$?
set -e

echo "$PULL_OUTPUT" | tail -5

if [ $PULL_EXIT -ne 0 ]; then
    echo ""
    echo "⚠️  Pull failed (exit $PULL_EXIT)."

    # Check if changes are already in working directory
    CHANGES=$(git status --short 2>/dev/null | grep -E '^( M|M |\?\?)' | wc -l | tr -d ' ')

    if [ "$CHANGES" -gt 0 ]; then
        echo "  ✅ Found $CHANGES uncommitted change(s) in working directory."
        echo "  Assuming patch was already applied (e.g. by manual pull)."
        echo "  Continuing..."
    else
        echo "  ❌ No uncommitted changes found."
        echo "  Cannot proceed — nothing to commit."
        echo ""
        echo "  Possible causes:"
        echo "    - session ID is incorrect"
        echo "    - patch has conflicts (manual resolution needed)"
        echo "    - jules CLI not logged in"
        echo ""
        read -rp "Continue anyway? [y/N] " CONTINUE </dev/tty || CONTINUE="n"
        if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
            echo "Aborted."
            exit 1
        fi
    fi
else
    echo "  ✅ Patch applied successfully."
fi
echo ""

# --- Step 2: Update state.json ---
echo "[2/8] Updating state.json..."

if [ -f "$STATE_FILE" ]; then
    python3 - "$STATE_FILE" "$TASK_ID" "$SESSION_ID" "$BRANCH_NAME" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

state_file = Path(sys.argv[1])
task_id = sys.argv[2]
session_id = sys.argv[3]
branch = sys.argv[4]

state = json.loads(state_file.read_text())
active = state.get("active_task") or {}

now = datetime.now(timezone.utc).isoformat()
completed = {
    "id": task_id,
    "status": "completed",
    "session_id": session_id,
    "branch": branch,
    "request": active.get("request"),
    "started_at": active.get("started_at"),
    "finished_at": now,
}

state["last_task"] = completed
state["active_task"] = None
state["status"] = "ready"
state.setdefault("history", []).append(completed)
state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
print(f"  ✅ Task {task_id} marked as completed")
PY
else
    echo "  ⚠️  state.json not found"
fi
echo ""

# --- Step 3: Review task ---
echo "[3/8] Reviewing task..."

if [ -x "./scripts/jules-review.sh" ]; then
    ./scripts/jules-review.sh "$TASK_ID" 2>&1 | tail -15
else
    echo "  ⚠️  jules-review.sh not found"
fi
echo ""

# --- Step 4: Validate project ---
echo "[4/8] Validating project..."

if [ -x "./scripts/validate.sh" ]; then
    if ./scripts/validate.sh >/tmp/validate.log 2>&1; then
        echo "  ✅ Validation passed"
    else
        echo "  ❌ Validation failed"
        tail -10 /tmp/validate.log
        read -rp "Continue anyway? [y/N] " CONTINUE
        if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
            echo "Aborted."
            exit 1
        fi
    fi
else
    echo "  ⚠️  validate.sh not found"
fi
echo ""

# --- Step 5: Run tests ---
echo "[5/8] Running tests..."

if command -v uv >/dev/null 2>&1; then
    if uv run pytest tests/ -q \
        --ignore=tests/test_ecology_service.py \
        --ignore=tests/test_value_service.py \
        --ignore=tests/test_mcp.py >/tmp/pytest.log 2>&1; then
        RESULT=$(tail -1 /tmp/pytest.log)
        echo "  ✅ $RESULT"
    else
        echo "  ❌ Tests failed"
        tail -15 /tmp/pytest.log
        read -rp "Continue anyway? [y/N] " CONTINUE
        if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
            echo "Aborted."
            exit 1
        fi
    fi
else
    echo "  ⚠️  uv not found — skipping tests"
fi
echo ""

# --- Step 6: Git commit ---
echo "[6/8] Committing changes..."

git checkout -b "$BRANCH_NAME"
git add -A

if git diff --cached --quiet; then
    echo "  ⚠️  Nothing to commit — working tree clean"
else
    COMMIT_MSG="feat: complete ${TASK_ID}

Jules session: ${SESSION_ID}
Task: ${TASK_ID}"
    git commit -m "$COMMIT_MSG" 2>&1 | tail -3
    echo "  ✅ Committed"
fi
echo ""

# --- Step 7: Push and create PR ---
echo "[7/8] Pushing and creating PR..."

git push -u origin "$BRANCH_NAME" 2>&1 | tail -3

if command -v gh >/dev/null 2>&1; then
    gh pr create --fill 2>&1 | tail -3 || echo "  ⚠️  PR may already exist"
else
    echo "  ⚠️  gh not found — create PR manually"
fi
echo ""

# --- Step 8: Wait for CI and merge ---
echo "[8/8] Waiting for CI and merging..."

if command -v gh >/dev/null 2>&1; then
    echo "  Waiting for CI checks..."
    MAX_WAIT=300
    WAITED=0
    INTERVAL=15
    CI_STATUS="unknown"

    while [ "$WAITED" -lt "$MAX_WAIT" ]; do
        CHECKS=$(gh pr checks 2>&1 || true)

        if echo "$CHECKS" | grep -qiE 'pending|queued|in progress'; then
            echo "  [$WAITED/${MAX_WAIT}s] CI still running..."
            sleep "$INTERVAL"
            WAITED=$((WAITED + INTERVAL))
        elif echo "$CHECKS" | grep -qiE 'fail|error'; then
            CI_STATUS="failed"
            break
        elif echo "$CHECKS" | grep -qiE 'pass|success'; then
            CI_STATUS="passed"
            break
        else
            echo "  [$WAITED/${MAX_WAIT}s] Waiting for checks to appear..."
            sleep "$INTERVAL"
            WAITED=$((WAITED + INTERVAL))
        fi
    done

    echo ""
    gh pr checks 2>&1 | tail -10
    echo ""

    if [ "$CI_STATUS" = "failed" ]; then
        echo "  ❌ CI failed. PR left open for manual review."
        exit 1
    fi

    if [ "$CI_STATUS" != "passed" ]; then
        echo "  ⚠️  CI did not finish within ${MAX_WAIT}s."
        echo "  PR left open for manual review."
        exit 0
    fi

    echo "  ✅ CI passed."
    echo ""
    printf "Merge PR? [y/N] "
    read -r MERGE </dev/tty || MERGE="n"

    if [ "$MERGE" = "y" ] || [ "$MERGE" = "Y" ]; then
        gh pr merge --squash --admin --delete-branch 2>&1 | tail -5
        git checkout main
        git pull origin main
        echo ""
        echo "  ✅ Merged and returned to main"
    else
        echo "  ⚠️  PR left open for manual review"
    fi
fi
echo ""

echo "════════════════════════════════════════════"
echo "  COMPLETE"
echo "════════════════════════════════════════════"
echo ""
echo "Task:   $TASK_ID"
echo "Branch: $BRANCH_NAME"
echo ""
