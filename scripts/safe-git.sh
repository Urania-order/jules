#!/usr/bin/env bash
# Safe git operations with stale index.lock handling (ERRATA-0045)
# Source this file: source scripts/safe-git.sh

remove_stale_git_lock() {
    [ -f .git/index.lock ] || return 0
    if command -v lsof >/dev/null 2>&1; then
        lsof .git/index.lock >/dev/null 2>&1 || rm -f .git/index.lock
    else
        pgrep -f "git (commit|push|rebase|merge|checkout|pull|stash)" >/dev/null 2>&1 \
            || rm -f .git/index.lock
    fi
}

safe_git_checkout() {
    local attempt
    for attempt in 1 2 3; do
        remove_stale_git_lock
        if git checkout "$@"; then return 0; fi
        echo "  [safe_git] checkout attempt $attempt failed; retrying..." >&2
        sleep 2
    done
    echo "  [safe_git] checkout failed after 3 attempts" >&2
    return 1
}

safe_git_pull() {
    local attempt
    for attempt in 1 2 3; do
        remove_stale_git_lock
        if git pull "$@"; then return 0; fi
        echo "  [safe_git] pull attempt $attempt failed; retrying..." >&2
        sleep 2
    done
    return 1
}

safe_git_fetch() {
    local attempt
    for attempt in 1 2 3; do
        remove_stale_git_lock
        if git fetch "$@"; then return 0; fi
        sleep 2
    done
    return 1
}

safe_git_stash_push() {
    remove_stale_git_lock
    git stash push "$@"
}

safe_git_stash_pop() {
    remove_stale_git_lock
    git stash pop "$@"
}
