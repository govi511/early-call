#!/usr/bin/env bash
# Rebuild data/ledger.json from the store CSV and push it only if it changed. Silent when nothing changed.
# Shares data/.git.lock with push-data.sh so the two never overlap.
set -euo pipefail
cd "$(dirname "$0")"
exec 9>data/.git.lock
flock -w 180 9 || { echo "sync-ledger: lock busy" >&2; exit 2; }
python3 refresh.py --ledger-only >> refresh.log 2>&1 || { echo "refresh.py --ledger-only failed (see refresh.log)" >&2; exit 1; }
git add data/ledger.json
git diff --cached --quiet && exit 0
git commit -q -m "ledger: sync $(date '+%Y-%m-%d %H:%M %Z')"
git pull -q --rebase origin main 2>>refresh.log || true
git push -q origin HEAD 2>>refresh.log || { echo "git push failed (see refresh.log)" >&2; exit 1; }
