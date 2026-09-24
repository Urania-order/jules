# ERRATA-0045: git checkout/pull do not retry on stale index.lock

## Severity
LOW-MEDIUM — recurring during jules-complete.sh / manual flow

## Symptom (recurring)
- gh pr merge succeeded
- git checkout main → fatal: Unable to create '.git/index.lock': File exists
- git pull → "Already up to date"
- Observed:
    * 2026-09-23 — ERRATA-0042 merge (PR #68)
    * 2026-09-24 — ERRATA-0044 merge (PR #70)

## Cause
- v1.3.1 added safe_git_commit / safe_git_push to jules-complete.sh
- git checkout / git pull in scripts and manual commands do NOT retry
- Transient .git/index.lock blocks next operation

## Fix (v1.5)
Add safe_git_checkout / safe_git_pull helpers:
    safe_git_checkout() {
        local attempt
        for attempt in 1 2 3; do
            if [ -f .git/index.lock ] && ! pgrep -f "git " >/dev/null; then
                rm -f .git/index.lock
            fi
            if git checkout "$@"; then return 0; fi
            sleep 2
        done
        return 1
    }
(same for git pull)

## Workaround (immediate)
    rm -f .git/index.lock
    git checkout main

## Related
- ERRATA-0038 (v1.3.1)
- TASK 07 (task-20260923-192923)

## Status
OPEN — needs v1.5
