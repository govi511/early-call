#!/usr/bin/env bash
# Rebuild data/ledger.json from the store CSV and push it only if it changed. Silent when nothing changed.
# Shares data/.git.lock with push-data.sh so the two never overlap.
set -euo pipefail
cd "$(dirname "$0")"
exec 9>data/.git.lock
export GIT_TERMINAL_PROMPT=0
flock -w 240 9 || { echo "sync-ledger: lock busy" >&2; exit 2; }
export EARLYCALL_LOCK_HELD=1  # refresh.py shares this lock; it is already held here
python3 refresh.py --ledger-only >> refresh.log 2>&1 || { echo "refresh.py --ledger-only failed (see refresh.log)" >&2; exit 1; }
git add data/ledger.json data/baselines.json 2>/dev/null || git add data/ledger.json
git diff --cached --quiet && exit 0
git commit -q -m "ledger: sync $(date '+%Y-%m-%d %H:%M %Z')"
git pull -q --rebase --autostash origin main 2>>refresh.log || { git rebase --abort 2>/dev/null; echo "git pull failed (see refresh.log)" >&2; exit 1; }
git push -q origin HEAD 2>>refresh.log || { echo "git push failed (see refresh.log)" >&2; exit 1; }
