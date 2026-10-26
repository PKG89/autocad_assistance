#!/usr/bin/env bash
set -euo pipefail

repo=$(git rev-parse --show-toplevel)
cd "$repo"

branch=$(git branch --show-current)
if [[ "$branch" != "codex/geo-ai-start" ]]; then
  echo "ERROR: expected codex/geo-ai-start, found ${branch:-DETACHED}" >&2
  exit 1
fi

for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
  if git rev-parse -q --verify "$marker" >/dev/null; then
    echo "ERROR: active Git operation: $marker" >&2
    exit 1
  fi
done
for state in rebase-merge rebase-apply; do
  if [[ -d "$(git rev-parse --git-path "$state")" ]]; then
    echo "ERROR: active Git operation: $state" >&2
    exit 1
  fi
done

echo "branch=$branch"
echo "head=$(git rev-parse HEAD)"
git status --short --branch

if [[ ! -x .venv/bin/python ]]; then
  echo "ERROR: .venv/bin/python is missing" >&2
  exit 1
fi
.venv/bin/python --version
free -h
df -h "$repo"
