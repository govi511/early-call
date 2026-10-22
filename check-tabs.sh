#!/usr/bin/env bash
# Post-publish smoke test: every tab must render content and no uncaught JS errors.
# Usage: ./check-tabs.sh [url]   (exit 0 = OK, 1 = FAIL -> roll back)
URL="${1:-https://govi511.github.io/early-call/}?check=$(date +%s)"
CHROME=$(command -v google-chrome || command -v chromium || command -v chromium-browser)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
"$CHROME" --headless=new --no-sandbox --disable-gpu --window-size=390,1400 \
  --virtual-time-budget=15000 --enable-logging=stderr --v=0 \
  --dump-dom "$URL" >"$T/dom.html" 2>"$T/log.txt"
fail=0
python3 - "$T/dom.html" <<'P' || fail=1
import sys,re,html
d=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
need={'signals':'feed','leader':'lb','alerts':None,'events':None}
bad=0
def text(id_):
    m=re.search(r'<[^>]*id="%s"[^>]*>(.*?)</section>'%id_,d,re.S)
    if not m: m=re.search(r'id="%s"[^>]*>(.*?)</(div|section)>'%id_,d,re.S)
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',m.group(1)))).strip() if m else None
for sec,inner in need.items():
    t=text(sec); ti=text(inner) if inner else t
    ok=t is not None and ti is not None and len(ti)>=20
    print(('OK  ' if ok else 'FAIL'),sec,'' if ok else '(missing or empty)')
    bad|= not ok
sys.exit(1 if bad else 0)
P
# Known noise to ignore (G BOT fixing): Kraken ETH/BTC request error
errs=$(grep -i "Uncaught" "$T/log.txt" | grep -vi "kraken" || true)
if [ -n "$errs" ]; then echo "FAIL console errors:"; echo "$errs" | head -5; fail=1; else echo "OK   no uncaught errors"; fi
[ $fail = 0 ] && echo "ALL TABS OK" || echo "CHECK FAILED - roll back"
exit $fail
