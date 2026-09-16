# ERRATA-0015: Post-pull check misses untracked forbidden files

## Symptom
After ./scripts/jules-complete.sh --task task-20260916-170317,
git status --short showed 8 untracked files in forbidden paths:

  ?? .jules/queue/completed/task-20260916-165950-6729.json
  ?? .jules/queue/pending/task-20260916-165946-8351.json
  ?? .jules/queue/pending/task-20260916-165949-1024.json
  ?? .jules/queue/pending/task-20260916-165949-6390.json
  ?? .jules/queue/pending/task-20260916-165950-1364.json
  ?? .jules/queue/pending/task-20260916-165951-1703.json
  ?? .jules/queue/pending/task-20260916-165951-3836.json
  ?? .jules/queue/pending/task-20260916-174758-8829.json

The post-pull check reported:
  post-pull check: no unexpected forbidden path changes

But it missed these untracked files.

## Cause
The post-pull check used:
  git diff --name-only HEAD
which only shows MODIFIED tracked files.
It does NOT show UNTRACKED files.

Jules created new files in .jules/queue/ in its VM.
When pull --apply ran, these files were applied as new
untracked files. The post-pull check did not see them.

## Fix
1. jules-complete.sh now detects and moves untracked files
   under forbidden paths to .jules/queue/deferred/ before
   updating state.json (PR #44, commit b86b861).
2. Post-pull check extended to include untracked files:
   git ls-files --others --exclude-standard
   | grep -E '^\.(co-smos|jules/(tasks|results|queue))/'

## Prevention
- Do not allow Jules to create files in .jules/queue/.
- Strengthen prompt: "You MUST NOT create or modify any file
  under .co-smos/, .jules/tasks/, .jules/results/, .jules/queue/,
  even as new files."
- Post-pull check MUST include untracked files.
- jules-complete.sh MUST auto-move untracked forbidden files.
- Consider gitignoring .jules/queue/ entirely.

## Related
- ERRATA-0012: Jules still modifies .jules/queue/ despite ban.
- ERRATA-0014: jules-queue-runner.sh can auto-start tasks.
