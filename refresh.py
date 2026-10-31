#!/usr/bin/env python3
"""Early Call refresh: ledger CSV -> data/ledger.json, live prices -> data/prices.json.
Unattended-safe: retries, timeouts, lock file, atomic writes, keeps last good price on failure.
Exit code 0 = ok (even if some prices failed), 1 = ledger could not be read, 2 = another run in progress."""
import random, subprocess, re, csv, json, os, sys, time, datetime, urllib.request, urllib.parse, fcntl, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LEDGER_ONLY = "--ledger-only" in sys.argv
SRC = ARGS[0] if ARGS else "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
CRYPTO = {"BTC","ETH","SOL","XRP","BNB","DOGE","ADA","AVAX","LINK","LTC","APE","ICP","PAXG","CRV","SEI","NEAR","QNT","S","RSR","PHA","IO","STBL","BTR","Q","BULL","TAO","FET","HYPE","ZEC","ENA","SUI","EIGEN","ATOM","OP","W","ONDO","PLUME","INJ","ZRO","PUMP","VVV","BAT","ETHBTC","WLD","PENGU","UNI"}
PAIRS = {"ETHBTC": "ETHBTC"}  # Binance cross pairs priced as the real ratio (not USDT)
def bsym(a): return PAIRS.get(a, a + "USDT")
def is_short(d):
    """Shared short-direction rule (mirrors isShort in filter.js)."""
    d = (d or "").strip().lower()
    return d.startswith(("short", "bear", "put", "hike")) or "short" in d
ALIAS = {"QQQ/SPY":"QQQ","SPY/QQQ":"SPY","ETH/BTC":"ETHBTC","XAUUSD (GOLD)":"XAUUSD","WTI CRUDE OIL (CL)":"WTI"}  # multi-ticker calls -> first ticker
NONPRICE = {"FED","FOMC","FEDFUNDS","RATES","CPI","US HOUSING","PELOSI"}  # macro calls, not tradable assets
NP_NOTE = "not a tradable asset"
NP_LABEL = "multi-asset/context label, no price expected"
CONTEXT_ONLY = set()  # assets whose ledger rows are all early-signal context rows (filled in main)
def level_nums(s):
    """Numbers in a level string, parsed exactly like lvl() in app.js: drop (...) notes, thousands commas, times and durations."""
    s = re.sub(r"\(.*?\)", "", str(s or "")); s = re.sub(r"(\d),(?=\d{3}\b)", r"\1", s)
    s = re.sub(r"\b\d{1,2}:\d{2}\b|\b\d+(?:\s*[-–]\s*\d+)?[- ]?(?:days?|weeks?|hours?|months?|h|d|w|m)\b", " ", s, flags=re.I)
    s = NOT_LEVEL_RE.sub(" ", s)  # dates ("by Oct 30") and percentages ("10-20% bounce") are never price levels
    s = re.sub(r"\b(\d{3,})(?:\.\d+)?\s*[-–]\s*(\d{1,2})\b(?![.,]?\d)", lambda m: f"{m.group(1)}-{m.group(1)[:-len(m.group(2))]}{m.group(2)}" if len(m.group(2)) < len(m.group(1)) else m.group(0), s)  # 7750-55 -> 7750-7755
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
NOT_LEVEL_RE = re.compile(r"\b" + _MON + r"[- ]?\d{1,2}(?:st|nd|rd|th)?\b(?:,?\s*\d{4}\b)?"   # Oct 30, Oct-30, Oct 30th, Oct 30, 2026
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+" + _MON + r"(?![a-z])"                                     # 30 Oct
    r"|\b\d{4}-\d{2}-\d{2}\b"                                     # 2026-10-30 (slash forms skipped: "17/22/28" are targets)
    r"|[-+]?\d+(?:\.\d+)?\s*(?:-|–|to)\s*[-+]?\d+(?:\.\d+)?\s*%|[-+]?\d+(?:\.\d+)?\s*%", re.I)  # 10-20%, 5%
def is_label(asset): return "/" in asset and " " in asset.strip()
# Label words -> priceable tickers (multi-asset labels like "S&P 500/OIL" are split and the first priceable part is used)
LABEL_TICKER = {"S&P 500":"SPY","S&P":"SPY","SP500":"SPY","SPX":"SPX","US500":"SPY","NASDAQ":"QQQ","NASDAQ 100":"QQQ","US TECH 100":"QQQ","NAS100":"QQQ","NDX":"NDX",
    "OIL":"OIL","WTI":"WTI","WTI OIL":"WTI","CRUDE":"OIL","BRENT":"BRENT","GOLD":"GOLD","XAU":"XAU","XAUUSD":"XAUUSD","SILVER":"SILVER","XAGUSD":"XAGUSD",
    "KOSPI":"KOSPI","SKHYNIX":"SKHYNIX","SPACEX":"SPCX","SPCX":"SPCX","UK100":"UK100","FTSE":"UK100","ES":"ES","ES_F":"ES","ES1!":"ES","US 500":"SPX","US500 INDEX":"SPX","CAD":"USDCAD","USD/CAD":"USDCAD","GBP":"GBPUSD","EUR":"EURUSD","USD":"DXY","DXY":"DXY"}
LABEL_SKIP = {"FED","FOMC","RATES","CPI","SEMIS","MACRO","US HOUSING","STARLINK","OPENAI","IRAN","SAUDI","CHINA","PELOSI"}
def label_parts(asset):
    a = re.sub(r"\(.*?\)", "", asset.upper()).strip()
    return [p.strip() for p in re.split(r"[/,]| AND ", a) if p.strip()]
def label_ticker(asset):
    """First priceable ticker for a label/multi-asset asset, or None."""
    a = asset.upper().strip()
    if a in LABEL_TICKER and LABEL_TICKER[a] != a: return LABEL_TICKER[a]
    if re.match(r"(US ?500|S&P ?500|SPX)\b.*\(.*\bES\b", a): return "ES"  # "US 500 (ES futures levels)": levels are ES futures -> ES=F
    b = re.sub(r"\(.*?\)", "", a).strip()
    if b != a and b in LABEL_TICKER and LABEL_TICKER[b] != b and "/" not in a: return LABEL_TICKER[b]  # "US 500 (T212 CFD)" -> SPX
    m = re.search(r"\(([A-Z]{3})/([A-Z]{3})\)", a)
    if m: return LABEL_TICKER.get(f"{m.group(1)}/{m.group(2)}") or None
    parts = label_parts(asset)
    if len(parts) < 2 and a not in LABEL_TICKER: return None
    for p in parts:
        if p in LABEL_SKIP or p in NONPRICE: continue
        if p in LABEL_TICKER: return LABEL_TICKER[p]
        if re.fullmatch(r"[A-Z]{1,5}", p): return p
    return None
SPLIT_SKIP = {"AI","FX","JPY","RUB","SEMIS","BONDS"}  # theme/currency words that are not tickers
def split_tickers(r):
    """Multi-ticker label (e.g. "AAPL/TSLA/SPCX") -> list of priceable tickers, one derived call each. [] if not a multi-ticker call."""
    asset = r.get("asset") or ""; a = asset.upper().strip()
    if not re.search(r"[/,]| and ", re.sub(r"\(.*?\)", "", asset), re.I) or a in ALIAS or r.get("ratio_call"): return []
    out = []
    for p in label_parts(asset):
        if p in LABEL_SKIP or p in NONPRICE or p in SPLIT_SKIP: continue
        t = LABEL_TICKER.get(p) or LABEL_TICKER.get(re.sub(r"\s+OIL$", "", p)) or (p if re.fullmatch(r"[A-Z]{1,5}(?:[.-][A-Z]{1,2})?", p) or p in YAHOO_MAP else None)
        if t and YAHOO_MAP.get(t, t) not in {YAHOO_MAP.get(x, x) for x in out}: out.append(t)  # Oil/WTI, Gold/XAU = one instrument
    return out if len(out) >= 2 else []
_LV = {}
def _LIVE():
    if not _LV:
        try: _LV.update({k: (v or {}).get("price") for k, v in json.load(open(os.path.join(DATA, "prices.json")))["prices"].items()})
        except Exception: _LV["_"] = None
    return _LV
def add_splits(rows):
    """Append one derived call per ticker for multi-ticker rows. The CSV row stays (split_into=[ids]) but is not scored itself.
    First ticker keeps the row's levels/status (what the call was scored on before); the others have no levels, so they are
    scored like any no-entry call: % move since the post (baseline at post time, locked at 7 days)."""
    out = []
    for r in rows:
        out.append(r); ts = split_tickers(r)
        if not ts: continue
        r["split_into"] = []
        for i, t in enumerate(ts):
            d = dict(r); d.pop("split_into", None)
            d.update({"id": f'{r["id"]}-{t}', "asset": t, "split_of": r["id"], "split_label": r["asset"]})
            lv = " ".join(str(r.get(k) or "") for k in ("entry", "stop", "target"))
            mixed = any(re.search(rf"\b{re.escape(o)}\b", lv, re.I) for o in ts if o != t)  # levels text names another ticker
            e0 = level_nums(r.get("entry")); lp = _LIVE().get(t)
            if not i and e0 and lp and not (1/3 <= e0[0] / lp <= 3): mixed = True  # levels belong to another ticker
            if i or mixed:
                d.update({"entry": "", "stop": "", "target": "", "resolved_at": ""})
                if d.get("status") in ("hit_target", "stopped", "expired", "unclear"): d["status"] = "open"
                d.pop("exit_price", None); d.pop("exit_pct", None); d["conditional"] = False; d["entry_filled"] = None; d["waiting_for_entry"] = False
            r["split_into"].append(d["id"]); out.append(d)
    rows[:] = out
KRAKEN = {"XMR":"XMRUSD"}  # Binance XMR pair is delisted/stale
CNBC_MAP = {"NATGAS":"@NG.1","NG":"@NG.1","GOLD":"@GC.1","XAU":"@GC.1","XAUUSD":"@GC.1","XAGUSD":"@SI.1","SILVER":"@SI.1","OIL":"@CL.1","WTI":"@CL.1","BRENT":"@LCO.1","SPX":".SPX","NDX":".NDX","ES":"@SP.1",
    "VIX":".VIX","EURJPY":"EURJPY=","KOSPI":".KS11","NYSE COMPOSITE":".NYA","NYA":".NYA","NYSE":".NYA"}
CNBC_CCY = {"EURJPY=":"JPY",".KS11":"KRW"}
def _cnbc(a):
    """Free no-key CNBC quote feed (front-month futures / indices); used first for CNBC_MAP so Yahoo 429s don't matter."""
    sym = CNBC_MAP.get(a, a)
    q = get("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=" + urllib.parse.quote(sym) + "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json", tries=2)
    q = q["FormattedQuoteResult"]["FormattedQuote"][0]
    p = float(str(q["last"]).replace(",", ""))
    if p <= 0: raise RuntimeError("cnbc: no price")
    try: ch = float(str(q.get("change_pct", "")).replace("%", "").replace("+", ""))
    except ValueError: ch = None
    return {"price": p, "change_pct": ch, "symbol": sym, "currency": CNBC_CCY.get(sym) or q.get("currencyCode") or "USD", "source": "CNBC", "as_of": now()}
YAHOO_MAP = {"KOSPI":"^KS11","SKHYNIX":"000660.KS","UK100":"^FTSE","USDCAD":"CAD=X","GBPUSD":"GBPUSD=X","EURUSD":"EURUSD=X","DXY":"DX-Y.NYB","NATGAS":"NG=F","NG":"NG=F","GOLD":"GC=F","XAU":"GC=F","XAUUSD":"GC=F","XAGUSD":"SI=F","SILVER":"SI=F","OIL":"CL=F","WTI":"CL=F","BRENT":"BZ=F","SPX":"^GSPC","ES":"ES=F","NDX":"^NDX"}
now = lambda: datetime.datetime.now().astimezone().isoformat(timespec="seconds")
def log(m): print(f"[{now()}] {m}", flush=True)
def write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=DATA, suffix=".tmp")
    with os.fdopen(fd, "w") as f: json.dump(obj, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o644); os.replace(tmp, path)
def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())
        except Exception as e:
            err = e; time.sleep(1.5 * (i + 1))
    raise err
YH = ("https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
YAHOO_429 = 0.0  # cooldown-until (epoch s) after backoff is exhausted; Yahoo is retried once it passes, never skipped for the whole run
YAHOO_COOLDOWN = 90
YCACHE_PATH = os.path.join(DATA, ".yahoo-cache.json")  # past-window history responses never change: cache them on disk
_YMEM = {}
def _ycache():
    if "_disk" not in _YMEM:
        try: _YMEM["_disk"] = json.load(open(YCACHE_PATH))
        except Exception: _YMEM["_disk"] = {}
    return _YMEM["_disk"]
YQUOTE_TTL = 300  # live quote responses reused for 5 min (memory + disk) so back-to-back runs don't re-hit Yahoo
def _ypast(qs):
    m = re.search(r"period2=(\d+)", qs); return bool(m) and int(m.group(1)) < time.time() - 3600
def ychart(sym, qs):
    global YAHOO_429
    key = f"{sym}?{qs}"
    if key in _YMEM: return _YMEM[key]
    disk = _ycache()
    if key in disk:
        hit = disk[key]
        if not (isinstance(hit, dict) and "_t" in hit): return hit
        if time.time() - hit["_t"] < YQUOTE_TTL: return hit["v"]
    if time.time() < YAHOO_429: raise RuntimeError(f"yahoo cooling down after 429 ({YAHOO_429 - time.time():.0f}s left)")
    err = None; delay = 2
    for attempt, h in enumerate(YH * 2):
        try:
            time.sleep(1.0 + random.random() * 0.5)  # pace requests (1-1.5s) so Yahoo does not throttle with 429
            req = urllib.request.Request(f"{h}/v8/finance/chart/{urllib.parse.quote(sym)}?{qs}", headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r: out = json.loads(r.read())
            _YMEM[key] = out
            if _ypast(qs) or "range=1d" in qs:
                disk[key] = out if _ypast(qs) else {"_t": time.time(), "v": out}
                try:
                    fd, tmp = tempfile.mkstemp(dir=DATA, suffix=".tmp")
                    with os.fdopen(fd, "w") as f: json.dump(disk, f, separators=(",", ":"))
                    os.replace(tmp, YCACHE_PATH)
                except Exception: pass
            return out
        except Exception as e:
            err = e
            stale = disk.get(key)
            if "429" in str(e) and isinstance(stale, dict) and "_t" in stale and time.time() - stale["_t"] < 3600: return stale["v"]  # 429: serve <1h-old cached quote
            if "429" in str(e):
                if attempt >= 3: YAHOO_429 = time.time() + YAHOO_COOLDOWN; break
                ra = getattr(e, "headers", None) and e.headers.get("Retry-After")
                time.sleep(min(30, float(ra)) if ra and str(ra).isdigit() else delay); delay *= 2  # backoff 2s, 4s, 8s (or Retry-After)
            elif "404" in str(e): break
    raise err
# ---- Stooq (no key, CSV). Fallback for stocks/indices when Yahoo 429s. File cache + per-run circuit breaker. ----
STOOQ_MAP = {"VIX": "^vix", "SPX": "^spx", "ES": "es.f", "SPY": "spy.us", "NDX": "^ndx", "DJI": "^dji", "DJIA": "^dji", "UK100": "^ukx", "FTSE": "^ukx",
    "DAX": "^dax", "NIKKEI": "^nkx", "KOSPI": "^kospi", "HSI": "^hsi", "DXY": "dx.f", "GOLD": "xauusd", "XAU": "xauusd", "XAUUSD": "xauusd",
    "XAGUSD": "xagusd", "SILVER": "xagusd", "EURUSD": "eurusd", "GBPUSD": "gbpusd", "USDCAD": "usdcad", "OIL": "cl.f", "WTI": "cl.f",
    "BRENT": "cb.f", "NATGAS": "ng.f", "NG": "ng.f", "NYSE COMPOSITE": "^nya", "BESI": "besi.nl"}
STOOQ_CACHE = os.path.join(DATA, ".stooq-cache.json")
STOOQ_TTL = {"q": 600, "d": 6 * 3600, "60": 1800}  # seconds per endpoint kind
STOOQ_DOWN = [0]  # consecutive failures this run; after 3, Stooq is skipped (host blocked / bot check)
_SQ = {}
def stooq_sym(a): return STOOQ_MAP.get(a) or (a.lower() + ".us" if re.fullmatch(r"[A-Z]{1,5}", a) else None)
def _stooq_csv(kind, sym):
    if "_disk" not in _SQ:
        try: _SQ["_disk"] = json.load(open(STOOQ_CACHE))
        except Exception: _SQ["_disk"] = {}
    disk = _SQ["_disk"]; key = f"{kind}:{sym}"; hit = disk.get(key)
    if hit and time.time() - hit["t"] < STOOQ_TTL[kind]: return hit["rows"]
    if STOOQ_DOWN[0] >= 3: raise RuntimeError("stooq skipped (unreachable earlier this run)")
    url = (f"https://stooq.com/q/l/?s={urllib.parse.quote(sym)}&f=sd2t2ohlcvp&h&e=csv" if kind == "q"
           else f"https://stooq.com/q/d/l/?s={urllib.parse.quote(sym)}&i={kind}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv"})
        with urllib.request.urlopen(req, timeout=8) as r: txt = r.read().decode("utf-8", "ignore")
        if "<html" in txt[:200].lower(): raise RuntimeError("stooq: bot check / html response")
        rows = list(csv.DictReader(txt.splitlines()))
        if not rows or "N/D" in str(rows[-1].values()) or "No data" in txt[:50]: raise RuntimeError("stooq: no data")
    except Exception as e:
        STOOQ_DOWN[0] += 1
        if hit: return hit["rows"]  # stale cache beats nothing
        raise
    STOOQ_DOWN[0] = 0; disk[key] = {"t": time.time(), "rows": rows[-400:]}
    try:
        fd, tmp = tempfile.mkstemp(dir=DATA, suffix=".tmp")
        with os.fdopen(fd, "w") as f: json.dump(disk, f, separators=(",", ":"))
        os.replace(tmp, STOOQ_CACHE)
    except Exception: pass
    return disk[key]["rows"]
def _stooq(a):
    sym = stooq_sym(a)
    if not sym: raise RuntimeError("stooq: no symbol mapping")
    q = _stooq_csv("q", sym)[0]; p = float(q["Close"]); o = float(q.get("Open") or 0)
    pc = None
    try:
        d = _stooq_csv("d", sym); pc = float(d[-2]["Close"]) if len(d) > 1 else None
    except Exception: pass
    base = pc or o
    return {"price": p, "change_pct": (p - base) / base * 100 if base else None, "symbol": sym, "currency": "USD", "source": "Stooq", "as_of": now()}
def _stooq_candles(a):
    sym = stooq_sym(a)
    if not sym: raise RuntimeError("stooq: no symbol mapping")
    def ts(r):
        t = r.get("Time") or "00:00:00"
        return int(datetime.datetime.strptime(f'{r["Date"]} {t}', "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp())
    bars = lambda rows: [[ts(r), r4(float(r["Open"])), r4(float(r["High"])), r4(float(r["Low"])), r4(float(r["Close"]))] for r in rows if r.get("Close") not in (None, "", "N/D")]
    out = {}
    try: h = bars(_stooq_csv("60", sym))
    except Exception: h = []
    d = bars(_stooq_csv("d", sym))
    out["1D"] = h[-24:] if h else d[-5:]
    out["1W"] = h[-120:] if h else d[-10:]
    out["1M"] = d[-180:]
    return out
def norm(asset):
    a = asset.upper().strip()
    if a in ALIAS: return ALIAS[a]
    t = label_ticker(asset)
    if t: return t
    m = re.fullmatch(r"([A-Z]{1,5}(?:[.-][A-Z]{1,2})?)\s*\(.*\)", a)  # "QQQ (US Tech 100)" -> QQQ
    if m: return LABEL_TICKER.get(m.group(1), m.group(1))
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
    if a in CNBC_MAP:
        try: return _cnbc(a)
        except Exception as e: log(f"cnbc failed for {a}: {e}; trying Yahoo")
    try: return _yahoo(a)
    except Exception as e: log(f"yahoo failed for {a}: {e}; trying CNBC/Stooq")
    if a not in CNBC_MAP and re.fullmatch(r"[A-Z]{1,5}", a):
        try: return _cnbc(a)
        except Exception as e: log(f"cnbc failed for {a}: {e}")
    try: return _stooq(a)
    except Exception as e:
        log(f"stooq failed for {a}: {e}; trying Nasdaq")
        return _nasdaq(a)
def _nasdaq(a):
    import urllib.request, json as _j
    errs = []
    for cls in ("stocks","etf"):
        try:
            req=urllib.request.Request(f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(a, safe='')}/info?assetclass={cls}",headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            d=_j.load(urllib.request.urlopen(req,timeout=15)).get("data") or {}
            pd=d.get("primaryData") or {}
            p=float(pd["lastSalePrice"].replace("$","").replace(",",""))
            ch=float(pd.get("percentageChange","0").replace("%","").replace("+","") or 0)
            return {"price":p,"change_pct":ch,"symbol":a,"currency":"USD","source":"Nasdaq","as_of":now()}
        except Exception as e: errs.append(f"{cls}: {e}")
    raise RuntimeError("no nasdaq price (" + ", ".join(errs) + ")")
def okx_inst(a): return {"ETHBTC": "ETH-BTC"}.get(a, f"{a}-USDT")
def _okx(a):
    t = get(f"https://www.okx.com/api/v5/market/ticker?instId={okx_inst(a)}", tries=2)["data"][0]
    p, o = float(t["last"]), float(t["sodUtc0"] or t["open24h"])
    if p <= 0: raise RuntimeError("okx: no price")
    return {"price": p, "change_pct": (p - o) / o * 100 if o else None, "symbol": okx_inst(a), "currency": "BTC" if a in PAIRS else "USDT", "source": "OKX", "as_of": now()}
def _okx_hist(a, ts):
    """1m candle at post time from OKX (Binance answers 451 from this host)."""
    k = get(f"https://www.okx.com/api/v5/market/history-candles?instId={okx_inst(a)}&bar=1m&after={(ts+60)*1000}&limit=1", tries=2).get("data") or []
    if k and float(k[0][1]) > 0: return float(k[0][1])
    raise RuntimeError("okx: no candle")
def _binance(a):
    try: return _okx(a)
    except Exception: pass
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
        elif SOURCE_USED.get(a, 'okx' if a in CRYPTO else 'yahoo') == 'okx':
            okb = {"15m": "15m", "1h": "1H", "4h": "4H"}[bi]
            rows = get(f"https://www.okx.com/api/v5/market/candles?instId={okx_inst(a)}&bar={okb}&limit={min(lim, 300)}")["data"][::-1]
            out[k] = [[int(x[0]) // 1000, r4(float(x[1])), r4(float(x[2])), r4(float(x[3])), r4(float(x[4]))] for x in rows]
        elif SOURCE_USED.get(a) == 'binance':
            rows = get(f"https://api.binance.com/api/v3/klines?symbol={bsym(a)}&interval={bi}&limit={lim}")
            out[k] = [[int(x[0]) // 1000, r4(float(x[1])), r4(float(x[2])), r4(float(x[3])), r4(float(x[4]))] for x in rows]
        else:
            sym = YAHOO_MAP.get(a, a)
            try: res = ychart(sym, f"range={yr}&interval={yi}")["chart"]["result"][0]
            except Exception:  # Yahoo 429/404: CNBC chart feed first, then Stooq
                try: return _cnbc_candles(a)
                except Exception: return _stooq_candles(a)
            q = res["indicators"]["quote"][0]
            out[k] = [[t, r4(o), r4(h), r4(l), r4(c)] for t, o, h, l, c in zip(res.get("timestamp", []), q["open"], q["high"], q["low"], q["close"]) if None not in (o, h, l, c)]
    return out
def _cnbc_candles(a):
    """CNBC chart feed (same as baselines): 5D 1-min bars -> 15m/1h, 1M daily bars. Stocks, ETFs, indices, futures."""
    sym = CNBC_HIST.get(a, a); out = {}
    def bars(per):
        b = get(f"https://ts-api.cnbc.com/harmony/app/charts/{per}.json?symbol={urllib.parse.quote(sym)}", tries=2)["barData"]["priceBars"] or []
        return [(int(x["tradeTimeinMills"]) // 1000, float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"])) for x in b if x.get("open") not in (None, "") and x.get("close") not in (None, "")]
    def agg(b, sec):
        g = {}
        for t, o, h, l, c in b:
            k = t // sec * sec
            if k in g: _, o0, h0, l0, _ = g[k]; g[k] = (k, o0, max(h0, h), min(l0, l), c)
            else: g[k] = (k, o, h, l, c)
        return [[t, r4(o), r4(h), r4(l), r4(c)] for t, o, h, l, c in sorted(g.values())]
    m1 = bars("5D"); d = bars("1M")
    if not m1 and not d: raise RuntimeError(f"cnbc: no bars for {sym}")
    out["1D"] = agg(m1, 900)[-96:]; out["1W"] = agg(m1, 3600)[-168:]
    out["1M"] = [[t, r4(o), r4(h), r4(l), r4(c)] for t, o, h, l, c in d][-30:]
    return out
def write_candles(assets):
    d = os.path.join(DATA, "candles"); os.makedirs(d, exist_ok=True); bad = []
    for a in assets:
        if "/" in a: continue  # alias like QQQ/SPY: candles live under the mapped ticker
        fp = os.path.join(d, a + ".json")
        if a not in CRYPTO and a not in KRAKEN and SOURCE_USED.get(a) not in ('binance', 'kraken', 'okx'):
            try:  # Yahoo-sourced (stocks/futures): refresh daily candles at most once per day to avoid 429s
                if json.load(open(fp)).get("as_of", "")[:10] == now()[:10]: continue
            except Exception: pass
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
# ---- Structured spam flags (mirrors SPAM_RULES / stripNeg in filter.js; filter.js prefers these when present) ----
SPAM_TEXT = [(r"telegram", "telegram_promo"), (r"\bvip\b", "vip_promo"), (r"referral|ref link", "referral_link"), (r"affiliate", "affiliate_link"),
    (r"low[- ]follower", "low_follower_account"), (r"thin account|bot account", "thin_bot_account"), (r"cop(y|ied)", "copied_post"),
    (r"duplicate", "duplicate"), (r"after[ _-]the[ _-]fact", "after_the_fact"), (r"\bstale\b", "stale")]
NEG_LIST = re.compile(r"\b(?:no|not|without|never|isn't|is not|not a)\s+(?:an?\s+|any\s+)?[\w-]+(?:\s*(?:/|,|\bor\b|\band\b|&)\s*[\w-]+)*(?:\s+(?:links?|promos?|posts?|accounts?|text|group|groups))?", re.I)
ACCOUNT_DESC = re.compile(r"\b(?:bio|his|her|their|he also|she also|account (?:has|posts)|posts (?:\w+ )?(?:affiliate|referral) links?|has a (?:losing|winning)[\w/ ]* record)\b", re.I)
def strip_neg(t): return NEG_LIST.sub(" ", " ; ".join(seg for seg in re.split(r"[;()]", t or "") if not ACCOUNT_DESC.search(seg)))
# Scan-log fragments describe OTHER accounts the X scanner looked at, not this call ("rejected rest of discovery: Telegram/VIP ...").
SCAN_LOG_SEG = re.compile(r"^\s*(?:rejected|discovery|skipped|rest of|other accounts|also scanned|following(?:/watchlist)?\b(?! *\+)|watchlist\b)", re.I)
def _split_top(t, seps=";|"):
    """Split on ; and | outside parentheses so a log segment keeps its (...) list."""
    out, buf, depth = [], [], 0
    for ch in t or "":
        if ch == "(": depth += 1
        elif ch == ")": depth = max(0, depth - 1)
        if ch in seps and depth == 0: out.append("".join(buf)); buf = []
        else: buf.append(ch)
    out.append("".join(buf)); return out
QUOTE_RE = re.compile(r'"([^"]+)"|\u201c([^\u201d]+)\u201d')
def call_text(r):
    """Only the quoted post text. Spam/keyword rules never read notes, own_notes, scan_log or account-history text:
    an explicit post_text column wins, else the "double-quoted" excerpts inside notes. No quote -> empty (nothing to judge)."""
    if isinstance(r, str): r = {"notes": r}
    if (r.get("post_text") or "").strip(): return r["post_text"]
    return " ; ".join((m.group(1) or m.group(2)).strip() for m in QUOTE_RE.finditer(r.get("notes", "") or ""))
# ---- Conditional calls: entry not triggered yet (limit/zone order, retest, "short if it breaks X"). Shared with tools/resolve_calls.py ----
COND_ENTRY = re.compile(r"limit|zone|retest|pending|close inside|\bif\b|break|trigger|reclaim|on a (?:1|4)?h? ?close|\d\s*-\s*\d", re.I)
COND_TEXT = re.compile(r"\b(?:short|sell|long|buy)\b[^.;]{0,40}\bif (?:it |price |we |btc |gold )?(?:breaks?|loses?|reclaims?|closes?|holds?)|\bon a (?:break|1h close|4h close|daily close)|\b(?:short|sell|buy|long) (?:a push into|the retest|the dip into)|\blimit (?:order|buy|sell)|\bwaiting for\b", re.I)
NOT_COND = re.compile(r"market|~|at scan|implied|cmp|now\b", re.I)
BREAK_ENTRY = re.compile(r"\bbreak|\bloses?\b|\bloss of|\breclaim|\bretake|breakout|breakdown|\b(?:close|hold|push|move)s? (?:above|below)|^\s*(?:above|below)\b|\d\+", re.I)
BREAK_TEXT = re.compile(r"\b(?:short|sell|long|buy)\b[^.;]{0,30}\bif (?:it |price |we )?(?:breaks?|loses?|reclaims?)|\bon a break(?:out|down)?\b", re.I)
def break_condition(r):
    """Entry triggers on a break through the level, judged from the entry field or an explicit 'short if it breaks X'; invalidation clauses don't count."""
    return bool(BREAK_ENTRY.search(r.get("entry") or "") or BREAK_TEXT.search(call_text(r)))
RATIO_RE = re.compile(r"\bratio\b|\bspread\b|\bvs\.?\b|\b(?:GC|SI|CL|NG|HG|BZ|ES|NQ)\s*/\s*(?:GC|SI|CL|NG|HG|BZ|ES|NQ)\b", re.I)
def is_ratio(r):
    """Ratio / spread / relative-value calls (gold/silver ratio, GC/SI, X vs Y): no single tradable price, never resolve against one leg."""
    a = r if isinstance(r, str) else (r.get("asset") or "") + " " + (r.get("direction") or "")
    return bool(RATIO_RE.search(a))
def is_conditional(r):
    e = (r.get("entry") or "").strip(); d = (r.get("direction") or "").lower()
    if "context" in d or not level_nums(e) and "conditional" not in d: return False
    if "conditional" in d: return True
    if NOT_COND.search(e): return False
    return bool(COND_ENTRY.search(e) or COND_TEXT.search(call_text(r)))
FILL_STATE = os.path.join(DATA, "fill-state.json")
try: FILLS = {str(k): v for k, v in json.load(open(FILL_STATE)).items() if not str(k).startswith("_")}
except Exception: FILLS = {}
AFTER_RE = re.compile(r"after[ _-]the[ _-]fact", re.I)
def after_the_fact(r):
    """Explicit after_the_fact column wins; else the phrase in the call's own text, with negations ("not after-the-fact") removed."""
    v = str(r.get("after_the_fact", "")).strip().lower()
    if v in ("1", "true", "yes", "y"): return True
    if v in ("0", "false", "no", "n"): return False
    return bool(AFTER_RE.search(strip_neg(call_text(r))))
def spam_flags(notes):
    nn = strip_neg(call_text(notes)); return [f for p, f in SPAM_TEXT if re.search(p, nn, re.I)]
OVERRIDES = os.path.join(DATA, "spam-overrides.json")  # {"<id>": true|false} manual review results
def add_spam_fields(rows):
    try: ov = {str(k): v for k, v in json.load(open(OVERRIDES)).items() if not str(k).startswith("_")}
    except Exception: ov = {}
    for r in rows:
        r["spam_flags"] = [f.strip() for f in r["spam_flags"].split(";") if f.strip()] if r.get("spam_flags") else spam_flags(r)
        v = r.get("spam_override", ""); v = ov.get(r["id"], v)
        r["spam_override"] = True if v in (True, "true", "spam", "1") else False if v in (False, "false", "not_spam", "0") else None
def add_feed(rows):
    """feed = following | famous | discovery (derived; CSV schema unchanged)."""
    try: calls = {a["handle"].lower() for a in json.load(open(WATCH_ACC)) if a.get("role") == "call"}
    except Exception: calls = set()
    for r in rows:
        n = r.get("notes", "").lower(); acc = r.get("account", "").lstrip("@").lower()
        r["feed"] = "following" if "source following" in n else "famous" if acc in calls else "discovery"
FLOW_RE = re.compile(r"options? flow|unusual (?:options )?(?:volume|activity)|type=(?:unusual[-_ ]options|options?[-_ ]flow)", re.I)
LOWCONF_FOLLOWERS = 5000
STALE_MIN = 45  # site shows stale banner when pricesUpdatedAt or ledgerUpdatedAt is older than this
def add_kind(rows):
    """kind = flow (options-flow alert) | news (early-signal/context) | call; low_confidence = account under 5k followers (shown, not hidden)."""
    for r in rows:
        n = r.get("notes") or ""; d = r.get("direction") or ""
        news = bool(re.match(r"early[- ]signal", n, re.I) or "(context)" in d.lower())
        r["kind"] = "flow" if FLOW_RE.search(d + " | " + r.get("account", "") + " | " + " ".join(re.findall(r"type=[\w-]+", n))) else "news" if news else "call"
        r["low_confidence"] = r.get("followers") is not None and r["followers"] < LOWCONF_FOLLOWERS
def _ts_utc(r):
    try:
        from zoneinfo import ZoneInfo
        return int(datetime.datetime.strptime(r["logged_at_lisbon"], "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Europe/Lisbon")).timestamp())
    except Exception: return None
def _hist(asset, ts):
    """Price at post time. Tries every source; on total failure raises with every reason joined."""
    a = norm(asset); errs = []
    if a in CRYPTO:
        try: return _okx_hist(a, ts), "OKX"
        except Exception as e: errs.append(f"okx: {e}")
        try:
            k = get(f"https://api.binance.com/api/v3/klines?symbol={bsym(a)}&interval=1m&startTime={ts*1000}&limit=1", tries=1)
            if k and float(k[0][1]) > 0: return float(k[0][1]), "Binance"
            errs.append("binance: no candle")
        except Exception as e: errs.append(f"binance: {e}")
        try: return _okx_hist(a, ts), "OKX"
        except Exception as e: errs.append(f"okx: {e}")
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
    for name, fn in (("cnbc", _chist), ("yahoo", _yhist), ("nasdaq hist", _nhist)):
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
            req = urllib.request.Request(f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(sym, safe='')}/historical?assetclass={cls}&fromdate={f}&todate={t}&limit=10", headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
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
CNBC_HIST = {**CNBC_MAP, "KOSPI": ".KS11", "SKHYNIX": "000660-KR", "UK100": ".FTSE", "USDCAD": "CAD=", "GBPUSD": "GBP=", "EURUSD": "EUR=", "DXY": ".DXY"}
_CH = {}
def _chist(a, ts):
    """Price at post time from CNBC charts (5D = 1-min bars for ~10 days, 1M = daily bars for a year). No key, no 429s."""
    sym = CNBC_HIST.get(a, a)
    for per in ("5D", "1M"):
        k = (sym, per)
        if k not in _CH:
            try: _CH[k] = get(f"https://ts-api.cnbc.com/harmony/app/charts/{per}.json?symbol={urllib.parse.quote(sym)}", tries=2)["barData"]["priceBars"] or []
            except Exception: _CH[k] = []
        bars = [(int(b["tradeTimeinMills"]) // 1000, float(b["open"]), float(b["close"])) for b in _CH[k] if b.get("open") not in (None, "")]
        if not bars or bars[0][0] > ts: continue
        step = 86400 if per == "1M" else 60
        at = [o for t, o, c in bars if ts <= t < ts + step * (1 if per == "5D" else 1)]
        if at: return at[0], f"CNBC {'1m' if per == '5D' else 'daily (open)'}"
        before = [c for t, o, c in bars if t < ts]
        after = [o for t, o, c in bars if t >= ts]
        if per == "5D" and after and before: return after[0], "CNBC 1m (next bar)"  # market closed at post time: next traded price
        if per == "1M" and before: return before[-1], "CNBC daily (close)"
    raise RuntimeError(f"cnbc: no bars for {sym}")
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
    try: live = {k: (v or {}).get("price") for k, v in json.load(open(os.path.join(DATA, "prices.json")))["prices"].items()}
    except Exception: live = {}
    sane = lambda a, b: bool(a) and bool(b) and 1/3 <= a / b <= 3  # catches ticker clashes (Gold vs GOLD stock, STRK token vs STRK stock)
    for r in rows:
        if level_nums(r.get("entry")) or not r.get("asset"): continue
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
        lp = live.get(r["asset"])
        if lp and not sane(cache[key]["price"], lp):
            r["baseline_rejected"] = f'{cache[key]["source"]} {cache[key]["price"]} vs live {lp}'; continue
        c0 = cache[key]
        if "locked_pct" in c0 and c0.get("locked_price") and not sane(c0["locked_price"], c0["price"]):
            r["baseline_rejected"] = f'lock {c0["locked_price"]} vs baseline {c0["price"]}'; continue
        r["baseline"] = cache[key]["price"]; r["baseline_source"] = cache[key]["source"]
        # fixed scoring point: price 7 days after post, locked once and never changed
        c = cache[key]; ts = _ts_utc(r)
        if "locked_pct" not in c and ts and time.time() >= ts + 7 * 86400:
            try:
                px7, _ = _hist(r["asset"], ts + 7 * 86400)
                if not sane(px7, c["price"]): raise RuntimeError(f"lock price {px7} not within 3x of baseline {c['price']}")
                d = -1 if is_short(r.get("direction")) else 1
                c["locked_pct"] = round(d * (px7 - c["price"]) / c["price"] * 100, 4); c["locked_price"] = px7
                c["locked_at"] = datetime.datetime.fromtimestamp(ts + 7 * 86400).astimezone().isoformat(timespec="minutes"); changed = True
            except Exception as e: log(f"lock {key} failed: {str(e)[:400]}")
        if "locked_pct" in c: r["locked_pct"] = c["locked_pct"]; r["locked_at"] = c["locked_at"]
    if changed: write_json(bp, cache)
def pick(asset, ref):
    """Fetch price; if a ledger entry level exists, the price must be within 3x of it (catches ticker clashes,
    e.g. NEAR token vs NEAR stock). Tries the default source, then the other one; otherwise raises -> n/a."""
    a = norm(asset); tried = []
    if is_label(asset) and not label_ticker(asset): return {"price": None, "nonpriceable": True, "note": NP_LABEL, "source": NP_LABEL, "as_of": now()}
    if a in NONPRICE: return {"price": None, "nonpriceable": True, "note": NP_NOTE, "source": NP_NOTE, "as_of": now()}
    order = [None, 'binance', 'alt', 'yahoo'] if a not in KRAKEN else [None]
    for src in order:
        try: p = fetch(a, src)
        except Exception as e: tried.append(f"{src or 'default'}: {str(e)[:40]}"); continue
        if ref is None or ref <= 0 or 1/3 <= p["price"] / ref <= 3:
            if a != asset.upper(): p["symbol"] = f'{p.get("symbol")} (from {asset.upper()})'
            SOURCE_USED[a] = 'kraken' if p["source"] == "Kraken" else 'binance' if p["source"] == "Binance" else 'okx' if p["source"] == "OKX" else 'yahoo'
            return p
        tried.append(f"{p['source']} {p['price']} far from entry {ref:g}")
        if ref is None: break
    raise RuntimeError("no matching price: " + "; ".join(tried))
def poster_notes(n):
    """Part of notes about the posting account: stops before scan recaps / rejected-discovery lists naming other accounts."""
    return re.split(r"\b(?:rest of|discovery (?:all )?rejected|rejected|following (?:feed|timeline)|watchlist commentary)\b", n or "", maxsplit=1, flags=re.I)[0]


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
    # 7-day lock for calls with no levels: close them in the ledger (no network; tools/resolve_calls.py --no-levels)
    if not ARGS:
        try:
            p = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "resolve_calls.py"), "--no-levels", "--apply"],
                               capture_output=True, text=True, timeout=120)
            n = re.search(r"(\d+) to close", p.stdout or ""); log(f"no-level 7-day lock: {n.group(1) if n else '?'} closed" + (f"; err {p.stderr[-300:]}" if p.returncode else ""))
        except Exception as e: log(f"no-level 7-day lock failed: {e}")
    try:
        with open(SRC, newline="", encoding="utf-8") as f: rows = []
        with open(SRC, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
                if not r.get("id"): continue
                r["after_the_fact"] = after_the_fact(r)
                r["call_notes"] = call_text(r)
                r["ratio_call"] = is_ratio(r)  # resolver skips these
                r["conditional"] = is_conditional(r)  # entry is a limit/zone/break trigger
                r["entry_filled"] = FILLS.get(r["id"], {}).get("filled") if r["conditional"] else None  # data/fill-state.json from tools/resolve_calls.py
                r["waiting_for_entry"] = bool(r["conditional"] and r.get("status") == "open" and not r["entry_filled"])
                m = re.search(r"\bexit_close=([\d.]+)", r.get("notes", ""))  # expired by time limit: that day's close (tools/resolve_calls.py)
                if m and r.get("status") == "expired":
                    r["exit_price"] = float(m.group(1)); en = level_nums(r.get("entry"))
                    if en: e0 = sum(en[:2]) / len(en[:2]); r["exit_pct"] = round((-1 if is_short(r.get("direction")) else 1) * (r["exit_price"] - e0) / e0 * 100, 4)
                m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*([km]?)\s+followers\b", poster_notes(r.get("notes", "")), re.I)  # posting account only
                if r.get("followers", "").replace(",", "").isdigit(): r["followers"] = int(r["followers"].replace(",", ""))
                else: r["followers"] = int(float(m.group(1).replace(",", ".")) * {"": 1, "k": 1e3, "m": 1e6}[m.group(2).lower()]) if m else None
                r["source"] = "X" if any(d in r.get("post_url", "") for d in ("x.com", "twitter.com")) else "other"
                rows.append(r)
    except Exception as e:
        log(f"ERROR reading ledger {SRC}: {e}"); return 1
    add_feed(rows); add_kind(rows); add_spam_fields(rows); add_splits(rows); add_baselines(rows)
    for r in rows:
        if r.get("exit_price") is not None and r.get("exit_pct") is None and r.get("baseline"):
            r["exit_pct"] = round((-1 if is_short(r.get("direction")) else 1) * (r["exit_price"] - r["baseline"]) / r["baseline"] * 100, 4)
    clusters = mark_clusters(rows)
    farm = sorted({a for c in clusters for a in c["accounts"]})
    def _iso(x):
        try:
            from zoneinfo import ZoneInfo
            return datetime.datetime.strptime(x, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Europe/Lisbon")).isoformat()
        except Exception: return None
    lu = max((t for t in (_iso(r.get("logged_at_lisbon", "")) for r in rows) if t), default=None)
    try: pu = json.load(open(os.path.join(DATA, "prices.json"))).get("fetched_at")
    except Exception: pu = None
    out = {"generated_at": now(), "ledgerUpdatedAt": lu, "pricesUpdatedAt": pu, "staleAfterMin": STALE_MIN, "calls": rows, "clusters": clusters, "spam_farm_accounts": farm}
    lp = os.path.join(DATA, "ledger.json")
    try:
        old = json.load(open(lp)); same = {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in out.items() if k != "generated_at"}
    except Exception: same = False
    write_json(lp, out)  # always rewrite so generated_at = last successful sync (stale banner reads it)
    log(f"ledger: {len(rows)} calls, {len(clusters)} copy clusters, farm={farm}{' (unchanged)' if same else ''}")
    if LEDGER_ONLY: return 0
    try: watch = json.load(open(os.path.join(DATA, "watchlist.json")))
    except Exception: watch = []
    ppath = os.path.join(DATA, "prices.json")
    try: old = json.load(open(ppath)).get("prices", {})
    except Exception: old = {}
    refs = {}
    for r in rows:
        n = level_nums(r.get("entry"))
        if n and r.get("asset"): refs.setdefault(r["asset"].upper(), sum(n[:2]) / len(n[:2]))
    ctx = {}
    for r in rows:
        if r.get("asset"):
            k = r["asset"].upper(); c = bool(re.match(r"early[- ]signal", r.get("notes") or "", re.I) or "(context)" in (r.get("direction") or "").lower())
            ctx[k] = ctx.get(k, True) and c
    CONTEXT_ONLY.update(k for k, v in ctx.items() if v)
    prices, ok, bad = {}, [], []
    for asset in sorted({r["asset"].upper() for r in rows if r.get("asset")} | {w.upper() for w in watch}):
        try:
            prices[asset] = pick(asset, refs.get(asset)); ok.append(asset)
        except Exception as e:
            if asset in CONTEXT_ONLY:  # early-signal context row that isn't a priceable ticker: not a failure
                prices[asset] = {"price": None, "nonpriceable": True, "note": NP_LABEL, "source": NP_LABEL, "as_of": now(), "error": str(e)[:120]}; continue
            prev = old.get(asset) or {}
            ref = refs.get(asset)
            if prev.get("price") is not None and ref and not (1/3 <= prev["price"] / ref <= 3): prev = {}  # don't keep a mismatched old price
            prices[asset] = {**prev, "stale": prev.get("price") is not None, "error": str(e)[:120]} if prev.get("price") is not None else {"price": None, "error": str(e)[:120]}
            bad.append(asset)
    for asset in list(bad):  # alias (e.g. QQQ/SPY) failed but its mapped ticker priced: reuse it
        m = norm(asset)
        if m != asset and prices.get(m, {}).get("price") is not None:
            prices[asset] = {**prices[m], "symbol": f'{prices[m].get("symbol")} (from {asset})'}; bad.remove(asset); ok.append(asset)
    write_json(ppath, {"fetched_at": now(), "pricesUpdatedAt": now(), "staleAfterMin": STALE_MIN, "prices": prices, "ok": ok, "failed": bad})
    log(f"prices ok={ok} failed={bad}")
    out["pricesUpdatedAt"] = json.load(open(ppath))["fetched_at"]; write_json(lp, out)  # stale banner reads both ages from ledger.json
    # candles only for symbols with open calls + portfolio + watch symbols (not every asset ever logged)
    try: port = [str(x.get("asset") or x.get("symbol") or x) if isinstance(x, dict) else str(x) for x in json.load(open(os.path.join(DATA, "portfolio.json")))]
    except Exception: port = []
    want = {r["asset"].upper() for r in rows if r.get("asset") and r.get("status") == "open"} | {w.upper() for w in watch} | {p.upper() for p in port}
    write_candles(sorted(a for a in want if prices.get(a, {}).get("price") is not None and not prices[a].get("nonpriceable") and not prices[a].get("stale")))
    return 0
if __name__ == "__main__": sys.exit(main())
