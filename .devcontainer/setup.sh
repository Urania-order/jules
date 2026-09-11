#!/usr/bin/env bash
set -e

echo ""
echo "=========================================="
echo " Jules Co-SMOS Codespace initialization"
echo "=========================================="
echo ""

echo "[1/6] Checking Node..."
node --version
npm --version

echo ""
echo "[2/6] Checking Git..."
git --version

echo ""
echo "[3/6] Checking GitHub CLI..."
gh --version || true

echo ""
echo "[4/6] Installing Jules CLI..."

if ! command -v jules >/dev/null 2>&1; then
    npm install -g @google/jules
else
    echo "Jules CLI already installed."
fi

echo ""
echo "[5/6] Creating Co-SMOS directories..."

mkdir -p \
    .jules/tasks \
    .jules/history \
    .jules/results \
    .co-smos \
    scripts

echo ""
echo "[6/6] Initializing state..."

if [ ! -f ".co-smos/state.json" ]; then
cat > .co-smos/state.json <<'JSON'
{
  "version": 1,
  "project": "jules-codespace",
  "agent": "jules",
  "status": "ready",
  "active_task": null,
  "last_task": null,
  "history": []
}
JSON
fi

chmod +x scripts/*.sh 2>/dev/null || true

echo ""
echo "=========================================="
echo " Environment ready"
echo "=========================================="
echo ""

echo "Jules:"
jules version 2>/dev/null || echo "Run: jules login"

echo ""
echo "Next:"
echo "  jules login"
echo "  ./scripts/jules-task.sh \"your task\""
echo ""
