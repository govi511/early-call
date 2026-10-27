#!/usr/bin/env bash
# Lag fix: publish ledger changes within ~1 min instead of waiting for the next scheduled sync.
# Polls the store CSV mtime every 60s and runs sync-ledger.sh when it changes (sync is a no-op if ledger.json is unchanged).
# Start: nohup setsid tools/ledger-watch.sh >/dev/null 2>&1 &   (single instance via flock on .ledger-watch.lock)
cd "$(dirname "$0")/.."
exec 8>.ledger-watch.lock; flock -n 8 || exit 0
SRC=/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv
last=""
while true; do
  m=$(stat -c %Y "$SRC" 2>/dev/null || echo 0)
  if [ "$m" != "$last" ]; then
    sleep 20  # let the writer finish
    ./sync-ledger.sh >> .ledger-watch.log 2>&1 && last="$m" || echo "[$(date -Is)] sync failed rc=$?" >> .ledger-watch.log
  fi
  sleep 60
done
