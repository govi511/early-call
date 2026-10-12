#!/usr/bin/env python3
"""Early Call refresh: ledger CSV -> data/ledger.json, live prices -> data/prices.json.
Unattended-safe: retries, timeouts, lock file, atomic writes, keeps last good price on failure.
Exit code 0 = ok (even if some prices failed), 1 = ledger could not be read, 2 = another run in progress."""
import csv, json, os, sys, time, datetime, urllib.request, urllib.parse, fcntl, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
SRC = sys.argv[1] if len(sys.argv) > 1 else "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
CRYPTO = {"BTC","ETH","SOL","XRP","BNB","DOGE","ADA","AVAX","LINK","LTC"}
YAHOO_MAP = {"NATGAS":"NG=F","NG":"NG=F","GOLD":"GC=F","XAU":"GC=F","SILVER":"SI=F","OIL":"CL=F","WTI":"CL=F","BRENT":"BZ=F","SPX":"^GSPC","NDX":"^NDX"}
now = lambda: datetime.datetime.now().astimezone().isoformat(timespec="seconds")
def log(m): print(f"[{now()}] {m}", flush=True)
def write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=DATA, suffix=".tmp")
    with os.fdopen(fd, "w") as f: json.dump(obj, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o644); os.replace(tmp, path)
def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 EarlyCall"})
            with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())
        except Exception as e:
            err = e; time.sleep(1.5 * (i + 1))
    raise err
def fetch(asset):
    a = asset.upper()
    if a in CRYPTO:
        p = get(f"https://api.binance.com/api/v3/ticker/price?symbol={a}USDT")
        return {"price": float(p["price"]), "symbol": a+"USDT", "currency": "USDT", "source": "Binance", "as_of": now()}
    sym = YAHOO_MAP.get(a, a)
    m = get("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym) + "?range=1d&interval=5m")["chart"]["result"][0]["meta"]
    ts = datetime.datetime.fromtimestamp(m["regularMarketTime"]).astimezone().isoformat(timespec="seconds")
    return {"price": float(m["regularMarketPrice"]), "symbol": sym, "currency": m.get("currency"), "source": "Yahoo Finance", "as_of": ts}
def main():
    os.makedirs(DATA, exist_ok=True)
    lock = open(os.path.join(DATA, ".refresh.lock"), "w")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: log("another refresh running; skip"); return 2
    try:
        with open(SRC, newline="", encoding="utf-8") as f: rows = []
        with open(SRC, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
                if not r.get("id"): continue
                n = r.get("notes", "").lower()
                r["after_the_fact"] = "after the fact" in n or "after-the-fact" in n
                r["source"] = "X" if any(d in r.get("post_url", "") for d in ("x.com", "twitter.com")) else "other"
                rows.append(r)
    except Exception as e:
        log(f"ERROR reading ledger {SRC}: {e}"); return 1
    write_json(os.path.join(DATA, "ledger.json"), {"generated_at": now(), "calls": rows}); log(f"ledger: {len(rows)} calls")
    try: watch = json.load(open(os.path.join(DATA, "watchlist.json")))
    except Exception: watch = []
    ppath = os.path.join(DATA, "prices.json")
    try: old = json.load(open(ppath)).get("prices", {})
    except Exception: old = {}
    prices, ok, bad = {}, [], []
    for asset in sorted({r["asset"].upper() for r in rows if r.get("asset")} | {w.upper() for w in watch}):
        try: prices[asset] = fetch(asset); ok.append(asset)
        except Exception as e:
            prev = old.get(asset) or {}
            prices[asset] = {**prev, "stale": prev.get("price") is not None, "error": str(e)[:120]} if prev.get("price") is not None else {"price": None, "error": str(e)[:120]}
            bad.append(asset)
    write_json(ppath, {"fetched_at": now(), "prices": prices, "ok": ok, "failed": bad})
    log(f"prices ok={ok} failed={bad}"); return 0
if __name__ == "__main__": sys.exit(main())
