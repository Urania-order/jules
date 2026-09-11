# jules-codespace

Experimental AI development environment where GitHub Codespaces
acts as the workspace and Jules acts as an autonomous software
engineering agent.

## Structure

    jules-codespace/
    ├── .devcontainer/
    │   ├── devcontainer.json
    │   └── setup.sh
    ├── .jules/
    │   ├── tasks/
    │   ├── history/
    │   └── results/
    ├── .co-smos/
    │   └── state.json
    ├── scripts/
    │   └── jules-task.sh
    ├── AGENTS.md
    └── README.md

## Quick start

    jules login
    ./scripts/jules-task.sh "Analyze project structure and find issues"

## Safety

- Never modify `main` directly
- Every task runs on a dedicated branch
- Human review before merge
