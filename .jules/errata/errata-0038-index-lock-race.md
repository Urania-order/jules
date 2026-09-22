# ERRATA-0038: git index.lock race in jules-complete.sh

## Severity
MEDIUM — commit skipped, working tree dirty after complete

## Symptom (2026-09-22, TASK 02 / task-20260922-153432)
- jules-complete.sh [7/9] Tests PASSED (316 passed)
- [8/9] Committing:
    fatal: Unable to create '/Users/vagra/jules/.git/index.lock': File exists.
    Another git process seems to be running in this repository, e.g.
    an editor opened by 'git commit'. Please make sure all processes
    are terminated then try again. If it still fails, a git process
    may have crashed in this repository earlier:
    remove the file manually to continue.
- Code applied but NOT committed
- Result: working tree dirty after jules-complete.sh finished
- Manual fix needed: rm -f .git/index.lock; git add; git commit; git push

## Cause
- Two git processes can run concurrently:
    1. run-task.sh — commit dispatch (chore: record task-...)
    2. jules-complete.sh — commit result (feat: apply Jules result)
- Race: one holds .git/index.lock, other fails immediately
- No retry, no stale-lock detection

## Impact
- Code applied in working tree, but not in git
- GitHub does not have the changes
- user must manually commit
- observed on TASK 02 (2026-09-22)

## Fix (v1.3.1)
In scripts/jules-complete.sh, before git commit:
    safe_git_commit() {
        local msg="$1"
        local attempt
        for attempt in 1 2 3; do
            if [ -f .git/index.lock ]; then
                if pgrep -f "git commit" > /dev/null 2>&1 || pgrep -f "git push" > /dev/null 2>&1; then
                    echo "      ⚠ active git process — waiting 5s (attempt $attempt)"
                    sleep 5
                else
                    echo "      ⚠ stale index.lock — removing (attempt $attempt)"
                    rm -f .git/index.lock
                fi
            fi
            if git commit -m "$msg"; then
                return 0
            fi
            echo "      ⚠ commit attempt $attempt failed — retry in 3s"
            sleep 3
            rm -f .git/index.lock
        done
        return 1
    }

    safe_git_push() {
        local attempt
        for attempt in 1 2 3; do
            if git push origin main; then
                return 0
            fi
            echo "      ⚠ push attempt $attempt failed — retry in 5s"
            sleep 5
        done
        return 1
    }

Replace existing `git commit` / `git push` with safe_git_commit / safe_git_push.

## Workaround (immediate)
    rm -f .git/index.lock
    git add <files>
    git commit -m "..."
    git push origin main

## Prevention
1. Do not run git commands manually while run-task.sh is active.
2. Use safe_git_commit / safe_git_push (v1.3.1).
3. If stale lock suspected: check `ps aux | grep git`.

## Related
- TASK 02 (task-20260922-153432)
- v1.2.9 (run-task.sh race fix — different race, same family)
- ERRATA-0037 (run-task.sh races + cleanup mistakes)

## Status
OPEN — needs v1.3.1 (fix in jules-complete.sh)
