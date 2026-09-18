#!/usr/bin/env bash
# Co-SMOS — universal verification script
set -u
cd "$(dirname "$0")/.."

PASS=0
FAIL=0

ok()  { echo "    ✅ $1"; PASS=$((PASS+1)); }
bad() { echo "    ❌ $1"; FAIL=$((FAIL+1)); }

check_grep() {
  local label="$1" file="$2" pattern="$3"
  if grep -q "$pattern" "$file" 2>/dev/null; then
    ok "$label  ($file)"
  else
    bad "$label  ($file)"
  fi
}

check_no_grep() {
  local label="$1" file="$2" pattern="$3"
  if grep -q "$pattern" "$file" 2>/dev/null; then
    bad "$label  ($file) — should NOT be present"
  else
    ok "$label  ($file) — absent"
  fi
}

check_file() {
  local label="$1" path="$2"
  if [ -e "$path" ]; then ok "$label  ($path)"; else bad "$label  ($path)"; fi
}

TASK_NAMES=(
  ""
  "Column Reset + Archive + WHY"
  "Archive Export (CSV / MD / JSONL)"
  "Archive Undo (Selected + Filter)"
  "Scheduled Reset (cron)"
  "Reset Audit Log"
  "Sequence UX fix (ERRATA-0023)"
  "Truncate task.request in all views (ERRATA-0024)"
  "safeDate + layout (ERRATA-0025)"
  "Fix Undo Selected in Undo tab (ERRATA-0026)"
  "Fix history overwrite + navbar RESET (ERRATA-0027/0028)"
)

verify_task_1() {
  echo "[Task 1] ${TASK_NAMES[1]}"
  check_grep  "reset-column endpoint"    smos/api/main.py         "queue/reset-column"
  check_grep  "archive dir"              smos/core/queue_reset.py "\.jules/queue"
  check_grep  "WHY preserved"            smos/core/queue_reset.py "why"
  check_grep  "reset buttons UI"         frontend/index.html      "btn-reset-ready"
}

verify_task_2() {
  echo "[Task 2] ${TASK_NAMES[2]}"
  check_grep  "export endpoint"          smos/api/main.py         "queue/archive/export"
  check_grep  "csv format"               smos/core/queue_reset.py "csv"
  check_grep  "jsonl format"             smos/core/queue_reset.py "jsonl"
  check_grep  "export buttons UI"        frontend/index.html      "btn-export-csv"
}

verify_task_3() {
  echo "[Task 3] ${TASK_NAMES[3]}"
  check_grep  "POST /archive/undo"       smos/api/main.py         "queue/archive/undo"
  check_grep  "POST /archive/undo-filter" smos/api/main.py        "queue/archive/undo-filter"
  check_grep  "frontend tab-archive"     frontend/index.html      "tab-archive"
  check_grep  "frontend tab-undo"        frontend/index.html      "tab-undo"
  check_grep  "frontend undo-all-matched" frontend/index.html     "btn-undo-all-matched"
  check_grep  "frontend undo-confirm"    frontend/index.html      "undo-confirm-modal"
  check_file  "test_archive_undo.py"     tests/test_archive_undo.py
}

verify_task_4() {
  echo "[Task 4] ${TASK_NAMES[4]}"
  check_grep  "reset/schedules endpoint" smos/api/main.py         "queue/reset/schedules"
  check_grep  "storage constant"         smos/core/queue_reset.py "reset_schedules.json"
  check_grep  "frontend tab-scheduled"   frontend/index.html      "tab-scheduled"
  check_grep  "frontend schedule-card"   frontend/index.html      "schedule-card"
  check_grep  "frontend btn-add-schedule" frontend/index.html     "btn-add-schedule"
}

verify_task_5() {
  echo "[Task 5] ${TASK_NAMES[5]}"
  check_grep  "GET /reset/audit"         smos/api/main.py         "queue/reset/audit"
  check_grep  "write_audit_entry helper" smos/core/queue_reset.py "write_audit_entry"
  check_grep  "audit storage"            smos/core/queue_reset.py "reset_audit.jsonl"
  check_grep  "frontend tab-audit"       frontend/index.html      "tab-audit"
  check_grep  "frontend audit-list"      frontend/index.html      "audit-list"
  check_grep  "frontend btn-refresh"     frontend/index.html      "btn-refresh-audit"
}

verify_task_6() {
  echo "[Task 6] ${TASK_NAMES[6]}"
  check_grep  "navbar Commands"          frontend/index.html      "data-view=\"sequence\">Commands"
  check_grep  "navbar Recordings"        frontend/index.html      "data-view=\"sequences\">Recordings"
}

verify_task_7() {
  echo "[Task 7] ${TASK_NAMES[7]}"
  check_grep  "truncateTask helper"      frontend/index.html      "function truncateTask"
  check_no_grep "no raw task.request"    frontend/index.html      'escapeHTML(task.request || task.title)}'
}

verify_task_8() {
  echo "[Task 8] ${TASK_NAMES[8]}"
  check_grep  "safeDate helper"          frontend/index.html      "function safeDate"
  check_no_grep "no raw new Date(task"   frontend/index.html      "new Date(task.created_at).toLocaleTimeString"
  check_no_grep "no raw new Date(seq"    frontend/index.html      "new Date(seq.created_at).toLocaleTimeString"
}

verify_task_9() {
  echo "[Task 9] ${TASK_NAMES[9]} — pending"
  echo "    ⚠ Not yet applied (ERRATA-0026)"
}

verify_task_10() {
  echo "[Task 10] ${TASK_NAMES[10]}"
  check_grep  "reset event in history"   smos/core/queue_reset.py 'state_data\["history"\]\.append'
  check_no_grep "no navbar RESET QUEUES" frontend/index.html      'RESET QUEUES</button>'
}

run_tests() {
  echo "[Tests] pytest targeted"
  if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "    activating .venv..."
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  python -m pytest tests/ \
    -k "reset or archive or schedule or audit or frontend_contract" \
    -q 2>&1 | tail -5
}

list_tasks() {
  for i in 1 2 3 4 5 6 7 8 9 10; do
    echo "  $i) ${TASK_NAMES[$i]}"
  done
}

main() {
  local mode="${1:---all}"

  case "$mode" in
    --list)
      list_tasks
      exit 0
      ;;
    --tests)
      run_tests
      exit 0
      ;;
    --task)
      local n="${2:-}"
      if [ -z "$n" ] || [ "$n" -lt 1 ] || [ "$n" -gt 10 ]; then
        echo "Usage: $0 --task N  (N=1..10)"
        exit 1
      fi
      "verify_task_$n"
      ;;
    --all|*)
      for i in 1 2 3 4 5 6 7 8 9 10; do
        echo ""
        "verify_task_$i"
      done
      ;;
  esac

  echo ""
  echo "================================================"
  echo " Summary: $PASS passed, $FAIL failed"
  echo "================================================"
  [ "$FAIL" -eq 0 ]
}

main "$@"
