#!/usr/bin/env bash
# Prints OK, or STALE <minutes> if heartbeat >5 min old or store CSV is >5 min newer than ledgerUpdatedAt.
cd "$(dirname "$0")/.."
SRC=/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv
now=$(date +%s)
hb=$(date -d "$(cat data/.ledger-watch.heartbeat 2>/dev/null)" +%s 2>/dev/null || echo 0)
lu=$(python3 -c "import json;print(json.load(open('data/ledger.json')).get('ledgerUpdatedAt',''))" 2>/dev/null)
lu=$(date -d "$lu" +%s 2>/dev/null || echo 0)
cm=$(stat -c %Y "$SRC" 2>/dev/null || echo 0)
a=$(( (now-hb)/60 )); b=$(( (cm-lu)/60 ))
m=$(( a>b ? a : b ))
if [ $a -gt 5 ] || [ $b -gt 5 ]; then echo "STALE $m"; exit 1; fi
echo OK
