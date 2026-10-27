#!/usr/bin/env bash
# Keeps exactly one ledger-watch.sh alive (no cron/systemd on this box). Checks every 5 min.
cd "$(dirname "$0")/.."
exec 7>.ledger-watch-keepalive.lock; flock -n 7 || exit 0
while true; do
  # watcher holds .ledger-watch.lock; if we can grab it, it's not running
  if flock -n .ledger-watch.lock true; then
    setsid tools/ledger-watch.sh 7>&- >/dev/null 2>&1 < /dev/null &
    echo "[$(date -Is)] keepalive started watcher" >> .ledger-watch.log
  fi
  sleep 300 7>&-
done
