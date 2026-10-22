#!/usr/bin/env bash
# Refresh data and push only data/*.json changes to GitHub Pages. Silent when nothing changed.
set -euo pipefail
export GIT_TERMINAL_PROMPT=0  # never prompt; fail instead
cd "$(dirname "$0")"
exec 9>data/.git.lock
flock -w 240 9 || { echo "push-data: lock busy" >&2; exit 2; }
export EARLYCALL_LOCK_HELD=1  # refresh.py shares this lock; it is already held here
python3 refresh.py >> refresh.log 2>&1 || { echo "refresh.py failed (see refresh.log)" >&2; exit 1; }
git add data/*.json data/candles/*.json
git diff --cached --quiet && exit 0
git commit -q -m "data: refresh $(date '+%Y-%m-%d %H:%M %Z')"
git pull -q --rebase --autostash origin main 2>>refresh.log || { git rebase --abort 2>/dev/null; echo "git pull failed (see refresh.log)" >&2; exit 1; }
if ! out=$(git push origin HEAD 2>&1); then
  echo "$out" >> refresh.log
  echo "push-data: GIT PUSH FAILED - data NOT published. git said:" >&2; echo "$out" | tail -5 >&2
  echo "push-data: check 'gh auth status' and git config credential.https://github.com.helper" >&2
  exit 3
fi
# verify the remote really has our commit
[ "$(git ls-remote origin refs/heads/main | cut -f1)" = "$(git rev-parse HEAD)" ] || { echo "push-data: push reported OK but origin/main != HEAD" >&2; exit 3; }
