# ERRATA-0006: NVM PATH not available in scripts

- Date: 2026-09-14
- Discovered in: task-20260914-165322
- Severity: MEDIUM
- Category: macOS 10.13 Intel (environment)

## Symptom

    ERROR: Jules CLI is not installed.

But jules is installed in ~/.nvm/versions/node/v16.20.2/bin/.

## Root cause

When script runs via nohup or from runner — shell profile not loaded.
~/.nvm/... not in PATH.

## Fix

Add PATH check at script start:

    if ! command -v jules >/dev/null 2>&1; then
        NVM_BIN="$HOME/.nvm/versions/node/v16.20.2/bin"
        if [ -d "$NVM_BIN" ]; then
            export PATH="$NVM_BIN:$PATH"
        fi
    fi

## Rule for future

All scripts that call jules MUST ensure PATH includes NVM.
Check: command -v jules before use.

## Check before task

- [ ] Scripts that call jules have NVM PATH check?
- [ ] command -v jules returns path?
