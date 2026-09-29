#!/usr/bin/env bash
set -euo pipefail

count=0
for dir in pending deferred; do
    for f in .jules/queue/$dir/*.json; do
        [ -f "$f" ] || continue
        if grep -q "Graph Task Test" "$f"; then
            rm "$f"
            count=$((count + 1))
        fi
    done
done
echo "Removed $count test task files"
