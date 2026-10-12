#!/usr/bin/env python3
"""Early Call refresh: ledger CSV -> data/ledger.json, live prices -> data/prices.json.
Unattended-safe: retries, timeouts, lock file, atomic writes, keeps last good price on failure.
Exit code 0 = ok (even if some prices failed), 1 = ledger could not be read, 2 = another run in progress."""
import csv, json, os, sys, time, datetime, urllib.request, urllib.parse, fcntl, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
SRC = sys.argv[1] if len(sys.argv) > 1 else "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
CRYPTO = {"BTC","ETH","SOL","XRP","BNB","DOGE","ADA","AVAX","LINK","LTC","APE","ICP","PAXG"}
KRAKEN = {"XMR":"XMRUSD"}  # Binance XMR pair is delisted/stale
YAHOO_MAP = {"NATGAS":"NG=F","NG":"NG=F","GOLD":"GC=F","XAU":"GC=F","XAUUSD":"GC=F","XAGUSD":"SI=F","SILVER":"SI=F","OIL":"CL=F","WTI":"CL=F","BRENT":"BZ=F","SPX":"^GSPC","NDX":"^NDX"}
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
    if a in KRAKEN:
        r = get(f"https://api.kraken.com/0/public/Ticker?pair={KRAKEN[a]}")
        if r.get("error"): raise RuntimeError(r["error"])
        t = next(iter(r["result"].values())); p, o = float(t["c"][0]), float(t["o"])
        return {"price": p, "change_pct": (p - o) / o * 100, "symbol": KRAKEN[a], "currency": "USD", "source": "Kraken", "as_of": now()}
    if a in CRYPTO:
        p = get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={a}USDT")
        return {"price": float(p["lastPrice"]), "change_pct": float(p["priceChangePercent"]), "symbol": a+"USDT", "currency": "USDT", "source": "Binance", "as_of": now()}
    sym = YAHOO_MAP.get(a, a)
    m = get("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym) + "?range=1d&interval=5m")["chart"]["result"][0]["meta"]
    p = m.get("regularMarketPrice")
    if p is None: raise RuntimeError("no price")
    pc = m.get("chartPreviousClose") or m.get("previousClose")
    rt = m.get("regularMarketTime")
    ts = datetime.datetime.fromtimestamp(rt).astimezone().isoformat(timespec="seconds") if rt else now()
    return {"price": float(p), "change_pct": (p - pc) / pc * 100 if pc else None, "symbol": sym, "currency": m.get("currency"), "source": "Yahoo Finance", "as_of": ts}

# ---- Candles -> data/candles/<ASSET>.json  ({"1D":[[t,o,h,l,c],...],"1W":...,"1M":...}) ----
RANGES = {"1D": ("15m", 96, "1d", "15m", 15), "1W": ("1h", 168, "5d", "60m", 60), "1M": ("4h", 180, "1mo", "1d", 240)}
def r4(x): return float(f"{x:.6g}")
def candles(asset):
    a = asset.upper(); out = {}
    for k, (bi, lim, yr, yi, km) in RANGES.items():
        if a in KRAKEN:
            r = get(f"https://api.kraken.com/0/public/OHLC?pair={KRAKEN[a]}&interval={km}")
            rows = next(v for kk, v in r["result"].items() if kk != "last")[-lim:]
            out[k] = [[int(x[0]), r4(float(x[1])), r4(float(x[2])), r4(float(x[3])), r4(float(x[4]))] for x in rows]
        elif a in CRYPTO:
            rows = get(f"https://api.binance.com/api/v3/klines?symbol={a}USDT&interval={bi}&limit={lim}")
            out[k] = [[int(x[0]) // 1000, r4(float(x[1])), r4(float(x[2])), r4(float(x[3])), r4(float(x[4]))] for x in rows]
        else:
            sym = YAHOO_MAP.get(a, a)
            res = get("https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym) + f"?range={yr}&interval={yi}")["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            out[k] = [[t, r4(o), r4(h), r4(l), r4(c)] for t, o, h, l, c in zip(res.get("timestamp", []), q["open"], q["high"], q["low"], q["close"]) if None not in (o, h, l, c)]
    return out
def write_candles(assets):
    d = os.path.join(DATA, "candles"); os.makedirs(d, exist_ok=True); bad = []
    for a in assets:
        try:
            c = candles(a)
            fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
            with os.fdopen(fd, "w") as f: json.dump({"asset": a, "as_of": now(), **c}, f, separators=(",", ":"))
            os.chmod(tmp, 0o644); os.replace(tmp, os.path.join(d, a + ".json"))
        except Exception as e: bad.append(a)
    log(f"candles ok={len(assets)-len(bad)} failed={bad}")
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
    log(f"prices ok={ok} failed={bad}")
    write_candles(sorted({r["asset"].upper() for r in rows if r.get("asset")}))
    return 0
if __name__ == "__main__": sys.exit(main())
