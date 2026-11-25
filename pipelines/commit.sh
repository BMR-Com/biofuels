#!/usr/bin/env bash
# Commit data/ and logs/ changes from a workflow and push, retrying over concurrent bot pushes.
set -u
msg="$1"
git config user.name "bmr-data-bot"; git config user.email "bot@users.noreply.github.com"
git add data logs 2>/dev/null
git diff --cached --quiet && { echo "nothing to commit"; exit 0; }
git commit -q -m "$msg"
for i in 1 2 3 4 5; do
  git pull -q --rebase --autostash -X theirs origin main && git push -q && ok=1 && break
  git rebase --abort 2>/dev/null || true; sleep 8
done
[ -n "${ok:-}" ] || { echo "::error::push failed"; exit 1; }
