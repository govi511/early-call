#!/usr/bin/env python3
"""Early Call refresh: ledger CSV -> data/ledger.json, live prices -> data/prices.json.
Unattended-safe: retries, timeouts, lock file, atomic writes, keeps last good price on failure.
Exit code 0 = ok (even if some prices failed), 1 = ledger could not be read, 2 = another run in progress."""
import re, csv, json, os, sys, time, datetime, urllib.request, urllib.parse, fcntl, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LEDGER_ONLY = "--ledger-only" in sys.argv
SRC = ARGS[0] if ARGS else "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
CRYPTO = {"BTC","ETH","SOL","XRP","BNB","DOGE","ADA","AVAX","LINK","LTC","APE","ICP","PAXG","CRV","SEI","NEAR","QNT","S","RSR","PHA","IO","STBL","BTR","Q","BULL","TAO","FET","HYPE","ZEC","ENA","SUI","EIGEN","ATOM","OP","W","ONDO","PLUME","INJ","ZRO","PUMP","VVV","BAT","ETHBTC"}
PAIRS = {"ETHBTC": "ETHBTC"}  # Binance cross pairs priced as the real ratio (not USDT)
def bsym(a): return PAIRS.get(a, a + "USDT")
def is_short(d):
    """Shared short-direction rule (mirrors isShort in filter.js)."""
    d = (d or "").strip().lower()
    return d.startswith(("short", "bear", "put", "hike")) or "short" in d
ALIAS = {"QQQ/SPY":"QQQ","SPY/QQQ":"SPY","ETH/BTC":"ETHBTC"}  # multi-ticker calls -> first ticker
NONPRICE = {"FED","FOMC","FEDFUNDS","RATES","CPI"}  # macro calls, not tradable assets
NP_NOTE = "not a tradable asset"
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
YH = ("https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
YAHOO_429 = False  # once Yahoo rate-limits us, skip it for the rest of this run
def ychart(sym, qs):
    global YAHOO_429
    if YAHOO_429: raise RuntimeError("yahoo skipped (429 earlier this run)")
    err = None
    for h in YH * 2:
        try:
            req = urllib.request.Request(f"{h}/v8/finance/chart/{urllib.parse.quote(sym)}?{qs}", headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())
        except Exception as e:
            err = e
            if "429" in str(e): YAHOO_429 = True; break
    raise err
def norm(asset):
    a = asset.upper().strip()
    if a in ALIAS: return ALIAS[a]
    return a.split("/")[0] if "/" in a and not a.endswith("/USD") else a
def kraken_pair(a):
    """Kraken pair for a token (static map or discovered at runtime via public Ticker)."""
    if a in KRAKEN: return KRAKEN[a]
    r = get(f"https://api.kraken.com/0/public/Ticker?pair={a}USD", tries=1)
    if r.get("error") or not r.get("result"): raise RuntimeError(f"kraken: {r.get('error')}")
    KRAKEN[a] = next(iter(r["result"])); return KRAKEN[a]
def _alt(a):
    """Crypto fallback when Binance lacks the pair: Kraken, then Gate.io (public, no key)."""
    try:
        pair = kraken_pair(a); r = get(f"https://api.kraken.com/0/public/Ticker?pair={pair}", tries=1)
        t = next(iter(r["result"].values())); p, o = float(t["c"][0]), float(t["o"])
        if p > 0: return {"price": p, "change_pct": (p - o) / o * 100, "symbol": pair, "currency": "USD", "source": "Kraken", "as_of": now()}
    except Exception: KRAKEN.pop(a, None)
    t = get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={a}_USDT", tries=1)
    if not isinstance(t, list) or not t or float(t[0]["last"]) <= 0: raise RuntimeError("no alt source")
    return {"price": float(t[0]["last"]), "change_pct": float(t[0].get("change_percentage") or 0), "symbol": a+"_USDT", "currency": "USDT", "source": "Gate.io", "as_of": now()}
def fetch(asset, force=None):
    a = norm(asset)
    if force == 'alt': return _alt(a)
    if force == 'yahoo': return _yahoo(a)
    if force == 'binance': return _binance(a)
    if a in KRAKEN:
        r = get(f"https://api.kraken.com/0/public/Ticker?pair={KRAKEN[a]}")
        if r.get("error"): raise RuntimeError(r["error"])
        t = next(iter(r["result"].values())); p, o = float(t["c"][0]), float(t["o"])
        return {"price": p, "change_pct": (p - o) / o * 100, "symbol": KRAKEN[a], "currency": "USD", "source": "Kraken", "as_of": now()}
    if a in CRYPTO: return _binance(a)
    try: return _yahoo(a)
    except Exception as e:
        log(f"yahoo failed for {a}: {e}; trying Nasdaq")
        return _nasdaq(a)
def _nasdaq(a):
    import urllib.request, json as _j
    errs = []
    for cls in ("stocks","etf"):
        try:
            req=urllib.request.Request(f"https://api.nasdaq.com/api/quote/{a}/info?assetclass={cls}",headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            d=_j.load(urllib.request.urlopen(req,timeout=15)).get("data") or {}
            pd=d.get("primaryData") or {}
            p=float(pd["lastSalePrice"].replace("$","").replace(",",""))
            ch=float(pd.get("percentageChange","0").replace("%","").replace("+","") or 0)
            return {"price":p,"change_pct":ch,"symbol":a,"currency":"USD","source":"Nasdaq","as_of":now()}
        except Exception as e: errs.append(f"{cls}: {e}")
    raise RuntimeError("no nasdaq price (" + ", ".join(errs) + ")")
def _binance(a):
        p = get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={bsym(a)}", tries=1)
        if float(p["lastPrice"]) <= 0: raise RuntimeError("binance pair dead (price 0)")
        return {"price": float(p["lastPrice"]), "change_pct": float(p["priceChangePercent"]), "symbol": bsym(a), "currency": "BTC" if a in PAIRS else "USDT", "source": "Binance", "as_of": now()}
def _yahoo(a):
    sym = YAHOO_MAP.get(a, a)
    m = ychart(sym, "range=1d&interval=5m")["chart"]["result"][0]["meta"]
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
    a = norm(asset); out = {}
    for k, (bi, lim, yr, yi, km) in RANGES.items():
        if a in KRAKEN:
            r = get(f"https://api.kraken.com/0/public/OHLC?pair={KRAKEN[a]}&interval={km}")
            rows = next(v for kk, v in r["result"].items() if kk != "last")[-lim:]
            out[k] = [[int(x[0]), r4(float(x[1])), r4(float(x[2])), r4(float(x[3])), r4(float(x[4]))] for x in rows]
        elif SOURCE_USED.get(a, 'binance' if a in CRYPTO else 'yahoo') == 'binance':
            rows = get(f"https://api.binance.com/api/v3/klines?symbol={bsym(a)}&interval={bi}&limit={lim}")
            out[k] = [[int(x[0]) // 1000, r4(float(x[1])), r4(float(x[2])), r4(float(x[3])), r4(float(x[4]))] for x in rows]
        else:
            sym = YAHOO_MAP.get(a, a)
            res = ychart(sym, f"range={yr}&interval={yi}")["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            out[k] = [[t, r4(o), r4(h), r4(l), r4(c)] for t, o, h, l, c in zip(res.get("timestamp", []), q["open"], q["high"], q["low"], q["close"]) if None not in (o, h, l, c)]
    return out
def write_candles(assets):
    d = os.path.join(DATA, "candles"); os.makedirs(d, exist_ok=True); bad = []
    for a in assets:
        if "/" in a: continue  # alias like QQQ/SPY: candles live under the mapped ticker
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
    return "|".join([r.get("asset","").upper(), ("short" if is_short(r.get("direction")) else "long") if r.get("direction") else "", n(r.get("entry")), n(r.get("stop")), n(r.get("target"))])
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
WATCH_ACC = os.path.join(os.path.dirname(SRC), "watchlist-accounts.json")
def add_feed(rows):
    """feed = following | famous | discovery (derived; CSV schema unchanged)."""
    try: calls = {a["handle"].lower() for a in json.load(open(WATCH_ACC)) if a.get("role") == "call"}
    except Exception: calls = set()
    for r in rows:
        n = r.get("notes", "").lower(); acc = r.get("account", "").lstrip("@").lower()
        r["feed"] = "following" if "source following" in n else "famous" if acc in calls else "discovery"
def _ts_utc(r):
    try:
        from zoneinfo import ZoneInfo
        return int(datetime.datetime.strptime(r["logged_at_lisbon"], "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Europe/Lisbon")).timestamp())
    except Exception: return None
def _hist(asset, ts):
    """Price at post time. Tries every source; on total failure raises with every reason joined."""
    a = norm(asset); errs = []
    if a in CRYPTO:
        try:
            k = get(f"https://api.binance.com/api/v3/klines?symbol={bsym(a)}&interval=1m&startTime={ts*1000}&limit=1", tries=1)
            if k and float(k[0][1]) > 0: return float(k[0][1]), "Binance"
            errs.append("binance: no candle")
        except Exception as e: errs.append(f"binance: {e}")
        if a in PAIRS: raise RuntimeError("; ".join(errs))  # ratio pairs: no USD fallback
        try: kraken_pair(a)
        except Exception as e: errs.append(f"kraken pair: {e}")
    if a in KRAKEN:
        try:
            r = get(f"https://api.kraken.com/0/public/OHLC?pair={KRAKEN[a]}&interval=1&since={ts-60}")
            rows = next(v for k, v in r["result"].items() if k != "last")
            if rows: return float(rows[0][1]), "Kraken"
            errs.append("kraken: no rows")
        except Exception as e: errs.append(f"kraken: {e}")
    if a in CRYPTO:
        try:
            g = get(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={a}_USDT&interval=1m&from={ts}&to={ts+600}", tries=1)
            if isinstance(g, list) and g: return float(g[0][5]), "Gate.io"
            errs.append("gate.io: no candles")
        except Exception as e: errs.append(f"gate.io: {e}")
        raise RuntimeError("; ".join(errs))
    for name, fn in (("yahoo", _yhist), ("nasdaq hist", _nhist)):
        try: return fn(a, ts)
        except Exception as e: errs.append(f"{name}: {e}")
    if time.time() - ts < 2*86400:
        try: return _nasdaq(a)["price"], "Nasdaq (approx)"
        except Exception as e: errs.append(f"nasdaq quote: {e}")
    raise RuntimeError("; ".join(errs))
def _nhist(a, ts):
    import urllib.request, json as _j, datetime as _d
    sym = {"QQQ/SPY":"QQQ"}.get(a, a)
    day = _d.datetime.fromtimestamp(ts, _d.timezone(_d.timedelta(hours=-4)))
    errs = []
    f = (day - _d.timedelta(days=6)).strftime("%Y-%m-%d"); t = day.strftime("%Y-%m-%d")
    for cls in ("stocks", "etf"):
        try:
            req = urllib.request.Request(f"https://api.nasdaq.com/api/quote/{sym}/historical?assetclass={cls}&fromdate={f}&todate={t}&limit=10", headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            rows = (((_j.load(urllib.request.urlopen(req, timeout=15)).get("data") or {}).get("tradesTable") or {}).get("rows")) or []
            num = lambda x: float(x.replace("$","").replace(",",""))
            ds = day.strftime("%m/%d/%Y")
            for r in rows:
                if r["date"] == ds and day.hour < 16: return num(r["open"]), "Nasdaq daily (open)"
            prior = [r for r in rows if r["date"] != ds or day.hour >= 16]
            if prior: return num(prior[0]["close"]), "Nasdaq daily (close)"
            errs.append(f"{cls}: no rows")
        except Exception as e: errs.append(f"{cls}: {e}")
    raise RuntimeError("no nasdaq history (" + ", ".join(errs) + ")")
def _yhist(a, ts):
    sym = YAHOO_MAP.get(a, a)
    res = ychart(sym, f"period1={ts-3600}&period2={ts+4*86400}&interval=5m")["chart"]["result"][0]
    pts = [(t, c) for t, c in zip(res.get("timestamp") or [], (res.get("indicators", {}).get("quote") or [{}])[0].get("close") or []) if c is not None]
    after = [c for t, c in pts if t >= ts - 300]
    if after: return float(after[0]), "Yahoo Finance"
    # posted outside market hours: last close before the post
    res = ychart(sym, f"period1={ts-5*86400}&period2={ts}&interval=5m")["chart"]["result"][0]
    pts = [c for t, c in zip(res.get("timestamp") or [], res["indicators"]["quote"][0]["close"]) if c is not None and t <= ts]
    if pts: return float(pts[-1]), "Yahoo Finance (last close)"
    raise RuntimeError("no history")
def add_baselines(rows):
    """Calls without a numeric entry: baseline = price at post time. Cached in data/baselines.json."""
    import re
    bp = os.path.join(DATA, "baselines.json")
    try: cache = json.load(open(bp))
    except Exception: cache = {}
    changed = False
    for r in rows:
        if re.findall(r"\d+(?:\.\d+)?", re.sub(r"\(.*?\)", "", r.get("entry", ""))) or not r.get("asset"): continue
        key = f'{r["id"]}|{r["asset"].upper()}|{r.get("logged_at_lisbon","")}'
        if norm(r["asset"]) in NONPRICE:
            r["nonpriceable"] = True
            if cache.get(key, {}).get("source") != NP_NOTE: cache[key] = {"price": None, "source": NP_NOTE, "at": r.get("logged_at_lisbon")}; changed = True
            continue
        if key in cache and cache[key].get("price") is None: del cache[key]  # every failed baseline is retried on each run
        if key not in cache:
            ts = _ts_utc(r)
            try:
                if ts is None: raise RuntimeError("bad time")
                px, src = _hist(r["asset"], ts); cache[key] = {"price": px, "source": src, "at": r["logged_at_lisbon"]}
            except Exception as e:
                log(f"baseline {key} failed: {str(e)[:400]}")
                cache[key] = {"price": None, "source": "unavailable", "error": str(e)[:400], "at": r.get("logged_at_lisbon")}; changed = True  # retried next run
                continue
            changed = True
        if cache[key]["price"] is None: continue
        r["baseline"] = cache[key]["price"]; r["baseline_source"] = cache[key]["source"]
        # fixed scoring point: price 7 days after post, locked once and never changed
        c = cache[key]; ts = _ts_utc(r)
        if "locked_pct" not in c and ts and time.time() >= ts + 7 * 86400:
            try:
                px7, _ = _hist(r["asset"], ts + 7 * 86400); d = -1 if is_short(r.get("direction")) else 1
                c["locked_pct"] = round(d * (px7 - c["price"]) / c["price"] * 100, 4); c["locked_price"] = px7
                c["locked_at"] = datetime.datetime.fromtimestamp(ts + 7 * 86400).astimezone().isoformat(timespec="minutes"); changed = True
            except Exception as e: log(f"lock {key} failed: {str(e)[:400]}")
        if "locked_pct" in c: r["locked_pct"] = c["locked_pct"]; r["locked_at"] = c["locked_at"]
    if changed: write_json(bp, cache)
def pick(asset, ref):
    """Fetch price; if a ledger entry level exists, the price must be within 3x of it (catches ticker clashes,
    e.g. NEAR token vs NEAR stock). Tries the default source, then the other one; otherwise raises -> n/a."""
    a = norm(asset); tried = []
    if a in NONPRICE: return {"price": None, "nonpriceable": True, "note": NP_NOTE, "source": NP_NOTE, "as_of": now()}
    order = [None, 'binance', 'alt', 'yahoo'] if a not in KRAKEN else [None]
    for src in order:
        try: p = fetch(a, src)
        except Exception as e: tried.append(f"{src or 'default'}: {str(e)[:40]}"); continue
        if ref is None or ref <= 0 or 1/3 <= p["price"] / ref <= 3:
            if a != asset.upper(): p["symbol"] = f'{p.get("symbol")} (from {asset.upper()})'
            SOURCE_USED[a] = 'kraken' if p["source"] == "Kraken" else 'binance' if p["source"] == "Binance" else 'yahoo'
            return p
        tried.append(f"{p['source']} {p['price']} far from entry {ref:g}")
        if ref is None: break
    raise RuntimeError("no matching price: " + "; ".join(tried))
def main():
    os.makedirs(DATA, exist_ok=True)
    # Shared lock with sync-ledger.sh / push-data.sh (data/.git.lock). Those scripts take it first and set
    # EARLYCALL_LOCK_HELD=1; standalone runs wait up to 240s instead of skipping.
    if os.environ.get("EARLYCALL_LOCK_HELD") != "1":
        lock = open(os.path.join(DATA, ".git.lock"), "w"); t0 = time.time()
        while True:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); break
            except OSError:
                if time.time() - t0 > 240: log("lock busy for 240s; giving up"); return 2
                time.sleep(2)
    try:
        with open(SRC, newline="", encoding="utf-8") as f: rows = []
        with open(SRC, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
                if not r.get("id"): continue
                n = r.get("notes", "").lower()
                r["after_the_fact"] = "after the fact" in n or "after-the-fact" in n
                m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*([km]?)\s+followers\b", r.get("notes", ""), re.I)
                r["followers"] = int(float(m.group(1).replace(",", ".")) * {"": 1, "k": 1e3, "m": 1e6}[m.group(2).lower()]) if m else None
                r["source"] = "X" if any(d in r.get("post_url", "") for d in ("x.com", "twitter.com")) else "other"
                rows.append(r)
    except Exception as e:
        log(f"ERROR reading ledger {SRC}: {e}"); return 1
    add_feed(rows); add_baselines(rows)
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
    for asset in list(bad):  # alias (e.g. QQQ/SPY) failed but its mapped ticker priced: reuse it
        m = norm(asset)
        if m != asset and prices.get(m, {}).get("price") is not None:
            prices[asset] = {**prices[m], "symbol": f'{prices[m].get("symbol")} (from {asset})'}; bad.remove(asset); ok.append(asset)
    write_json(ppath, {"fetched_at": now(), "prices": prices, "ok": ok, "failed": bad})
    log(f"prices ok={ok} failed={bad}")
    write_candles(sorted(a for a in {r["asset"].upper() for r in rows if r.get("asset")} if prices.get(a, {}).get("price") is not None and not prices[a].get("nonpriceable") and not prices[a].get("stale")))
    return 0
if __name__ == "__main__": sys.exit(main())
