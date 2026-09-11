#!/usr/bin/env bash

set -e

echo "🧠 AI Codespace bootstrap starting..."

# Node detect
if ! command -v node >/dev/null 2>&1; then
    echo "❌ Node not found in devcontainer environment."
    exit 1
fi

echo "✅ Node: $(node -v)"
echo "✅ npm: $(npm -v)"

# Jules install
if ! command -v jules >/dev/null 2>&1; then
    echo "⚙️ Installing @google/jules..."
    npm install -g @google/jules || echo "⚠️ jules install failed"
fi

# workspace setup
mkdir -p .jules/tasks .jules/history .jules/results .co-smos

echo "🧪 System ready"
