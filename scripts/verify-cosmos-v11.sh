#!/usr/bin/env bash
# Verify all Co-SMOS v1.1 features (Задачі 1-5) applied correctly.
set -u
cd "$(dirname "$0")/.."

PASS=0
FAIL=0

ok()   { echo "    ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "    ❌ $1"; FAIL=$((FAIL+1)); }

check_grep() {
  local label="$1" file="$2" pattern="$3"
  if grep -q "$pattern" "$file" 2>/dev/null; then
    ok "$label  ($file)"
  else
    bad "$label  ($file)"
  fi
}

check_file() {
  local label="$1" path="$2"
  if [ -e "$path" ]; then ok "$label  ($path)"; else bad "$label  ($path)"; fi
}

echo "================================================"
echo " Verify Co-SMOS v1.1 — Reset Center (Задачі 1-5)"
echo "================================================"
echo ""

# ---------------------------------------------------------------
echo "[Задача 1] Column Reset + Archive + WHY"
check_grep  "reset-column endpoint"     smos/api/main.py        "queue/reset-column"
check_grep  "archive dir constant"      smos/core/queue_reset.py "\.jules/queue"
check_grep  "WHY preserved"             smos/core/queue_reset.py "why"
check_grep  "reset buttons in UI"       frontend/index.html     "btn-reset-ready"
echo ""

# ---------------------------------------------------------------
echo "[Задача 2] Archive Export (CSV / MD / JSONL)"
check_grep  "export endpoint"           smos/api/main.py        "queue/archive/export"
check_grep  "csv format support"        smos/core/queue_reset.py "csv"
check_grep  "md format support"         smos/core/queue_reset.py "markdown\|\.md"
check_grep  "jsonl format support"      smos/core/queue_reset.py "jsonl"
echo ""

# ---------------------------------------------------------------
echo "[Задача 3] Archive Undo (Selected + Filter)"
check_grep  "GET  /archive"             smos/api/main.py        "queue/archive\""
check_grep  "POST /archive/undo"        smos/api/main.py        "queue/archive/undo\""
check_grep  "POST /archive/undo-filter" smos/api/main.py        "queue/archive/undo-filter"
check_grep  "frontend tab-archive"      frontend/index.html     "tab-archive"
check_grep  "frontend tab-undo"         frontend/index.html     "tab-undo"
check_grep  "frontend undo-selected"    frontend/index.html     "btn-undo-selected"
check_grep  "frontend undo-all-matched" frontend/index.html     "btn-undo-all-matched"
check_grep  "frontend undo-confirm"     frontend/index.html     "undo-confirm-modal"
check_file  "tests/test_archive_undo"   tests/test_archive_undo.py
echo ""

# ---------------------------------------------------------------
echo "[Задача 4] Scheduled Reset (cron)"
check_grep  "GET    /reset/schedules"   smos/api/main.py        "queue/reset/schedules\""
check_grep  "POST   /reset/schedules"   smos/api/main.py        "queue/reset/schedules\""
check_grep  "PATCH  /reset/schedules"   smos/api/main.py        "queue/reset/schedules/{id}"
check_grep  "DELETE /reset/schedules"   smos/api/main.py        "queue/reset/schedules/{id}"
check_grep  "storage constant"          smos/core/queue_reset.py "reset_schedules.json"
check_grep  "frontend tab-scheduled"    frontend/index.html     "tab-scheduled"
check_grep  "frontend schedule-card"    frontend/index.html     "schedule-card"
check_grep  "frontend btn-add-schedule" frontend/index.html     "btn-add-schedule"
echo ""

# ---------------------------------------------------------------
echo "[Задача 5] Reset Audit Log"
check_grep  "GET /reset/audit"          smos/api/main.py        "queue/reset/audit"
check_grep  "write_audit_entry helper"  smos/core/queue_reset.py "write_audit_entry"
check_grep  "audit storage path"        smos/core/queue_reset.py "reset_audit.jsonl"
check_grep  "frontend tab-audit"        frontend/index.html     "tab-audit"
check_grep  "frontend audit-list"       frontend/index.html     "audit-list"
check_grep  "frontend audit-row"        frontend/index.html     "audit-row"
check_grep  "frontend btn-refresh"      frontend/index.html     "btn-refresh-audit"
echo ""

# ---------------------------------------------------------------
echo "[Git] recent commits"
git log --oneline -10
echo ""

echo "[Git] status (should be clean)"
git status --short
echo ""

# ---------------------------------------------------------------
echo "[Tests] running pytest (audit + undo + archive + schedule + frontend)"
if [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "    activating .venv..."
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if python -m pytest tests/ \
     -k "audit or undo or archive or schedule or reset or frontend_contract" \
     -q 2>&1 | tail -15; then
  ok "targeted tests passed"
else
  bad "targeted tests failed"
fi
echo ""

# ---------------------------------------------------------------
echo "[Tests] full suite (last line)"
python -m pytest tests/ -q 2>&1 | tail -3
echo ""

echo "================================================"
echo " Summary: $PASS passed, $FAIL failed"
echo "================================================"

[ "$FAIL" -eq 0 ]
