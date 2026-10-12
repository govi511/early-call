#!/usr/bin/env python3
"""Early Call refresh: ledger CSV -> data/ledger.json, live prices -> data/prices.json.
Unattended-safe: retries, timeouts, lock file, atomic writes, keeps last good price on failure.
Exit code 0 = ok (even if some prices failed), 1 = ledger could not be read, 2 = another run in progress."""
import csv, json, os, sys, time, datetime, urllib.request, urllib.parse, fcntl, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LEDGER_ONLY = "--ledger-only" in sys.argv
SRC = ARGS[0] if ARGS else "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
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
def fetch(asset, force=None):
    a = asset.upper()
    if force == 'yahoo': return _yahoo(a)
    if force == 'binance': return _binance(a)
    if a in KRAKEN:
        r = get(f"https://api.kraken.com/0/public/Ticker?pair={KRAKEN[a]}")
        if r.get("error"): raise RuntimeError(r["error"])
        t = next(iter(r["result"].values())); p, o = float(t["c"][0]), float(t["o"])
        return {"price": p, "change_pct": (p - o) / o * 100, "symbol": KRAKEN[a], "currency": "USD", "source": "Kraken", "as_of": now()}
    if a in CRYPTO: return _binance(a)
    return _yahoo(a)
def _binance(a):
        p = get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={a}USDT", tries=1)
        return {"price": float(p["lastPrice"]), "change_pct": float(p["priceChangePercent"]), "symbol": a+"USDT", "currency": "USDT", "source": "Binance", "as_of": now()}
def _yahoo(a):
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
        elif SOURCE_USED.get(a, 'binance' if a in CRYPTO else 'yahoo') == 'binance':
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
def fingerprint(r):
    """asset+direction+entry+stop+target, numbers only (labels like '(1h close)' ignored)"""
    import re
    n = lambda v: ",".join(re.findall(r"\d+(?:\.\d+)?", v or "")) or (v or "").strip().lower()
    return "|".join([r.get("asset","").upper(), r.get("direction","").lower().split()[0] if r.get("direction") else "", n(r.get("entry")), n(r.get("stop")), n(r.get("target"))])
def mark_clusters(rows):
    """Same fingerprint from different accounts within 48h: all but earliest -> copy_of; all accounts -> spam_farm."""
    def ts(r):
        try: return datetime.datetime.strptime(r.get("logged_at_lisbon",""), "%Y-%m-%d %H:%M")
        except ValueError: return None
    groups = {}
    for r in rows:
        r["copy_of"] = ""; r["spam_farm"] = False
        if not any(c.isdigit() for c in r.get("entry","")): continue  # no numeric levels -> can't fingerprint
        groups.setdefault(fingerprint(r), []).append(r)
    clusters = []
    for fp, g in groups.items():
        g = sorted(g, key=lambda r: (ts(r) or datetime.datetime.max, int(r["id"]) if r["id"].isdigit() else 0))
        first = g[0]; t0 = ts(first)
        members = [r for r in g[1:] if r["account"] != first["account"] and (t0 is None or ts(r) is None or ts(r) - t0 <= datetime.timedelta(hours=48))]
        if not members: continue
        for r in members: r["copy_of"] = first["id"]
        accts = {first["account"], *(r["account"] for r in members)}
        for r in [first, *members]: r["spam_farm"] = True
        clusters.append({"fingerprint": fp, "first": first["id"], "copies": [r["id"] for r in members], "accounts": sorted(accts)})
    return clusters
SOURCE_USED = {}
def pick(asset, ref):
    """Fetch price; if a ledger entry level exists, the price must be within 3x of it (catches ticker clashes,
    e.g. NEAR token vs NEAR stock). Tries the default source, then the other one; otherwise raises -> n/a."""
    a = asset.upper(); tried = []
    order = [None, 'binance', 'yahoo'] if a not in KRAKEN else [None]
    for src in order:
        try: p = fetch(a, src)
        except Exception as e: tried.append(f"{src or 'default'}: {str(e)[:40]}"); continue
        if ref is None or ref <= 0 or 1/3 <= p["price"] / ref <= 3:
            SOURCE_USED[a] = 'kraken' if p["source"] == "Kraken" else 'binance' if p["source"] == "Binance" else 'yahoo'
            return p
        tried.append(f"{p['source']} {p['price']} far from entry {ref:g}")
        if ref is None: break
    raise RuntimeError("no matching price: " + "; ".join(tried))
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
    clusters = mark_clusters(rows)
    farm = sorted({a for c in clusters for a in c["accounts"]})
    out = {"generated_at": now(), "calls": rows, "clusters": clusters, "spam_farm_accounts": farm}
    lp = os.path.join(DATA, "ledger.json")
    try:
        old = json.load(open(lp)); same = {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in out.items() if k != "generated_at"}
    except Exception: same = False
    if not same: write_json(lp, out)
    log(f"ledger: {len(rows)} calls, {len(clusters)} copy clusters, farm={farm}{' (unchanged)' if same else ''}")
    if LEDGER_ONLY: return 0
    try: watch = json.load(open(os.path.join(DATA, "watchlist.json")))
    except Exception: watch = []
    ppath = os.path.join(DATA, "prices.json")
    try: old = json.load(open(ppath)).get("prices", {})
    except Exception: old = {}
    import re
    refs = {}
    for r in rows:
        n = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", re.sub(r"\(.*?\)", "", r.get("entry", "")))]
        if n and r.get("asset"): refs.setdefault(r["asset"].upper(), sum(n[:2]) / len(n[:2]))
    prices, ok, bad = {}, [], []
    for asset in sorted({r["asset"].upper() for r in rows if r.get("asset")} | {w.upper() for w in watch}):
        try:
            prices[asset] = pick(asset, refs.get(asset)); ok.append(asset)
        except Exception as e:
            prev = old.get(asset) or {}
            ref = refs.get(asset)
            if prev.get("price") is not None and ref and not (1/3 <= prev["price"] / ref <= 3): prev = {}  # don't keep a mismatched old price
            prices[asset] = {**prev, "stale": prev.get("price") is not None, "error": str(e)[:120]} if prev.get("price") is not None else {"price": None, "error": str(e)[:120]}
            bad.append(asset)
    write_json(ppath, {"fetched_at": now(), "prices": prices, "ok": ok, "failed": bad})
    log(f"prices ok={ok} failed={bad}")
    write_candles(sorted(a for a in {r["asset"].upper() for r in rows if r.get("asset")} if prices.get(a, {}).get("price") is not None and not prices[a].get("stale")))
    return 0
if __name__ == "__main__": sys.exit(main())
