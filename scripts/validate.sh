#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo " Running Co-SMOS Project Validation Tests"
echo "=========================================="
echo ""

ERRORS=0

echo "[1/5] Checking required directory structure..."
REQUIRED_DIRS=(
    ".co-smos"
    ".devcontainer"
    ".jules/tasks"
    ".jules/history"
    ".jules/results"
    "scripts"
    "smos"
    "smos/core"
    "smos/services"
    "smos/models"
    "tests"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "  ✅ Directory exists: $dir"
    else
        echo "  ❌ Missing directory: $dir"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "[2/5] Validating JSON files syntax..."
JSON_FILES=(
    ".co-smos/state.json"
    ".devcontainer/devcontainer.json"
)

for json_file in "${JSON_FILES[@]}"; do
    if [ -f "$json_file" ]; then
        if python3 -m json.tool "$json_file" > /dev/null 2>&1; then
            echo "  ✅ Valid JSON: $json_file"
        else
            echo "  ❌ Invalid JSON: $json_file"
            ERRORS=$((ERRORS + 1))
        fi
    else
        if [ "$json_file" = ".co-smos/state.json" ]; then
            mkdir -p .co-smos
            cat > "$json_file" <<'STATE_EOF'
{
  "version": 1,
  "project": "jules-codespace",
  "agent": "jules",
  "status": "ready",
  "active_task": null,
  "last_task": null,
  "history": []
}
STATE_EOF
            echo "  ✅ Created default: $json_file"
        else
            echo "  ❌ Missing file: $json_file"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done

echo ""
echo "[3/5] Checking shell script syntax..."
SHELL_SCRIPTS=(
    "scripts/jules-task.sh"
    "scripts/jules-status.sh"
    "scripts/validate.sh"
    ".devcontainer/setup.sh"
    ".devcontainer/bootstrap.sh"
    ".devcontainer/fallback.sh"
)

for script in "${SHELL_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        if bash -n "$script"; then
            echo "  ✅ Syntax OK: $script"
        else
            echo "  ❌ Syntax error in script: $script"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "  ❌ Missing script: $script"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "[4/5] Checking required documentation and configuration files..."
REQUIRED_FILES=(
    "AGENTS.md"
    "README.md"
    "Dockerfile"
    ".gitignore"
    "pyproject.toml"
    "ARCHITECTURE.md"
    "COMMONS.md"
    "OBSERVATORY.md"
    "ROADMAP.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ File exists: $file"
    else
        echo "  ❌ Missing file: $file"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "[5/5] Checking Co-SMOS core interfaces..."
CORE_FILES=(
    "smos/core/interfaces.py"
    "smos/services/commons_service.py"
    "smos/services/observatory_service.py"
    "smos/services/ecology_engine.py"
    "smos/services/value_ecology_service.py"
)

for file in "${CORE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ File exists: $file"
    else
        echo "  ❌ Missing file: $file"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
echo "=========================================="
if [ "$ERRORS" -eq 0 ]; then
    echo " SUCCESS: All validation checks passed!"
    echo "=========================================="
    exit 0
else
    echo " FAILURE: $ERRORS validation check(s) failed."
    echo "=========================================="
    exit 1
fi
