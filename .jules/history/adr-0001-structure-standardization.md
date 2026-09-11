# Architectural Decision Record: ADR-0001
- **Date:** 2026-09-10
- **Task ID:** task-20260910-174339
- **Title:** Repository Structure & DevContainer Standardization

## Context
Initial analysis of `jules-codespace` revealed several configuration and structural issues:
1. Absence of a `.gitignore` file, causing temporary artifacts and log outputs from tasks to be tracked by Git.
2. Version mismatch between `Dockerfile` (`javascript-node:18`) and `.devcontainer/devcontainer.json` (`javascript-node:1-20-bookworm`).
3. Redundant and fragile setup commands in `.devcontainer/bootstrap.sh` and `fallback.sh` that attempted to download Node 18 apt sources on bookworm.
4. Hardcoded mount target `/workspace/.jules/history` in `devcontainer.json` instead of using dynamic variables like `${containerWorkspaceFolder}`.
5. Absence of project-wide validation tests to verify repo structure and file syntax integrity.

## Decisions Made
1. **Added `.gitignore`**:
   - Excluded `node_modules/`, `.npm/`, `*.log`, system files, and `.jules/results/*.log` while explicitly keeping `.gitkeep` files in `.jules/` subdirectories.
2. **Standardized Base Image**:
   - Updated `Dockerfile` to use `mcr.microsoft.com/devcontainers/javascript-node:1-20-bookworm` aligning with `devcontainer.json`.
3. **Updated Mount Targets**:
   - Modified `.devcontainer/devcontainer.json` mount target to `${containerWorkspaceFolder}/.jules/history`.
4. **Refactored DevContainer Scripts**:
   - Simplified `.devcontainer/bootstrap.sh` and `.devcontainer/fallback.sh` to remove manual NodeSource apt-get operations and safely rely on container Node environment.
5. **Introduced Project Validation Script**:
   - Added `scripts/validate.sh` to perform automated validation on JSON syntax (`state.json`, `devcontainer.json`), script syntax (`bash -n`), and directory structure requirements.

## Consequences
- The repository is clean, well-structured, and protected against committing build/log artifacts.
- Container builds are aligned across `Dockerfile` and DevContainer configurations.
- Validation can be automated and tested repeatedly via `scripts/validate.sh`.
