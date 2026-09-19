#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

source .venv/bin/activate
export PATH="$HOME/.nvm/versions/node/v16.20.2/bin:$PATH"

QUEUE_DIR=".jules/queue"
RUNNING_DIR="$QUEUE_DIR/running"
PENDING_DIR="$QUEUE_DIR/pending"
COMPLETED_DIR="$QUEUE_DIR/completed"
DEFERRED_DIR="$QUEUE_DIR/deferred"

mkdir -p "$RUNNING_DIR" "$PENDING_DIR" "$COMPLETED_DIR" "$DEFERRED_DIR"

# --- Dedup: extract TASK header, move duplicates to deferred ---
dedup_pending() {
  echo "=== Dedup: checking pending/ for duplicate TASK headers ==="
  declare -A seen
  local moved=0
  for f in $(ls -tr "$PENDING_DIR"/admin-*.txt 2>/dev/null); do
    local header
    header=$(grep -m1 "^# TASK" "$f" 2>/dev/null || echo "")
    if [ -z "$header" ]; then
      echo "  $f — no TASK header, skipping"
      continue
    fi
    if [ -n "${seen[$header]+x}" ]; then
      echo "  DUPLICATE: $f  (header: $header)"
      echo "             original: ${seen[$header]}"
      mv "$f" "$DEFERRED_DIR/"
      moved=$((moved + 1))
    else
      seen[$header]="$f"
      echo "  KEEP: $f  (header: $header)"
    fi
  done
  echo "  Moved $moved duplicate(s) to deferred/"
  echo ""
}

pick_next() {
  local f
  f=$(ls -t "$RUNNING_DIR"/admin-*.txt 2>/dev/null | head -1)
  if [ -n "$f" ]; then echo "$f"; return; fi
  f=$(ls -tr "$PENDING_DIR"/admin-*.txt 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    mv "$f" "$RUNNING_DIR/"
    echo "$RUNNING_DIR/$(basename "$f")"
    return
  fi
  echo ""
}

process_one() {
  local file="$1"
  local base
  base=$(basename "$file")
  local header
  header=$(grep -m1 "^# TASK" "$file" 2>/dev/null || echo "(no header)")

  echo ""
  echo "═══════════════════════════════════════════════"
  echo " Processing: $base"
  echo " Header:     $header"
  echo "═══════════════════════════════════════════════"

  local before_hash
  before_hash=$(git rev-parse HEAD)

  ./scripts/run-task.sh "$file"
  local rc=$?

  echo ""
  echo "─── Result for $base (exit=$rc) ───"

  local after_hash
  after_hash=$(git rev-parse HEAD)
  if [ "$after_hash" != "$before_hash" ]; then
    echo "✅ New commits:"
    git log --oneline "${before_hash}..${after_hash}" | sed 's/^/   /'
  fi

  local result
  result=$(python3 -c "
import json
try:
    s = json.load(open('.co-smos/state.json'))
    lt = s.get('last_task') or {}
    print(lt.get('result', 'unknown'))
except Exception:
    print('unknown')
" 2>/dev/null)

  echo "last_task.result: $result"

  if [ "$result" = "applied" ] || [ "$result" = "no-op" ]; then
    echo "✅ Moving $base → completed/"
    mv "$file" "$COMPLETED_DIR/" 2>/dev/null || true
  else
    echo "⚠️  Moving $base → deferred/"
    mv "$file" "$DEFERRED_DIR/" 2>/dev/null || true
  fi
}

# --- Main ---
echo "=== Co-SMOS: process queue one by one ==="
echo ""

# 1. Dedup pending
dedup_pending

# 2. Process one by one
COUNT=0
while true; do
  next=$(pick_next)
  if [ -z "$next" ]; then
    echo ""
    echo "Queue is empty."
    break
  fi
  process_one "$next"
  COUNT=$((COUNT + 1))
  echo ""
  read -p "Continue with next? [Y/n] " ans
  case "$ans" in
    n|N) break ;;
  esac
done

echo ""
echo "═══════════════════════════════════════════════"
echo " Processed: $COUNT file(s)"
echo "═══════════════════════════════════════════════"
echo ""
echo "=== Final state ==="
echo "pending:   $(ls "$PENDING_DIR"/admin-*.txt 2>/dev/null | wc -l | tr -d ' ')"
echo "running:   $(ls "$RUNNING_DIR"/admin-*.txt 2>/dev/null | wc -l | tr -d ' ')"
echo "completed: $(ls "$COMPLETED_DIR"/admin-*.txt 2>/dev/null | wc -l | tr -d ' ')"
echo "deferred:  $(ls "$DEFERRED_DIR"/admin-*.txt 2>/dev/null | wc -l | tr -d ' ')"
echo ""
git log --oneline -10
