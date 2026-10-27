#!/usr/bin/env python3
"""Resolve open ledger calls that have numeric levels, strictly from real candles.
Closes a call only if price actually hit target or stop after the post (and after the entry filled,
when the entry is a limit level/zone). Same-bar target+stop = ambiguous -> stays open.
Prints proposed changes; --apply writes them to the ledger CSV (atomic, backup kept)."""
import csv, sys, os, re, time, shutil, datetime, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refresh as R
L = "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
def nums(s): return R.level_nums(s)  # one shared level parser (drops notes, times, durations, dates, percentages)
_C = {}
def bars(asset, ts):
    """[(t, o, h, l, c)] hourly-ish bars from ts to now. Crypto: OKX 1H. Others: CNBC 1m (aggregated to 1H) or daily."""
    a = R.norm(asset)
    if a in R.CRYPTO:
        if a not in _C:
            out, after = [], None
            for _ in range(20):
                u = f"https://www.okx.com/api/v5/market/history-candles?instId={R.okx_inst(a)}&bar=1H&limit=100" + (f"&after={after}" if after else "")
                d = R.get(u, tries=2).get("data") or []
                if not d: break
                out += d; after = d[-1][0]
                if int(after) // 1000 < ts - 3600: break
            _C[a] = sorted((int(x[0]) // 1000, *map(float, x[1:5])) for x in out)
        return [b for b in _C[a] if b[0] + 3600 > ts], "OKX 1H"
    sym = R.CNBC_HIST.get(a, a)
    for per in ("5D", "1M"):
        k = (sym, per)
        if k not in _C:
            try: _C[k] = R.get(f"https://ts-api.cnbc.com/harmony/app/charts/{per}.json?symbol={sym}", tries=2)["barData"]["priceBars"] or []
            except Exception: _C[k] = []
        b = [(int(x["tradeTimeinMills"]) // 1000, float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"])) for x in _C[k] if x.get("open") not in (None, "")]
        if not b or b[0][0] > ts: continue
        if per == "5D":  # aggregate 1m -> 1H
            g = {}
            for t, o, h, l, c in b:
                if t < ts: continue
                k2 = t // 3600 * 3600
                if k2 in g: _, o0, h0, l0, _ = g[k2]; g[k2] = (k2, o0, max(h0, h), min(l0, l), c)
                else: g[k2] = (k2, o, h, l, c)
            return sorted(g.values()), "CNBC 1m->1H"
        return [x for x in b if x[0] + 86400 > ts], "CNBC daily"
    raise RuntimeError(f"no bars for {sym}")
def judge(r):
    st, tg, en = nums(r["stop"]), nums(r["target"]), nums(r["entry"])
    if not st and not tg: return None
    if re.match(r"\s*neutral", r.get("direction") or "", re.I): return None  # range/condor calls (#508): no up/down target to hit
    short = R.is_short(r["direction"]); ts = R._ts_utc(r)
    b, src = bars(r["asset"], ts)
    if not b: return ("open", "no bars since post", src)
    stop_close = "close" in r["stop"].lower()
    entry_txt = r["entry"].lower()
    cond = R.is_conditional(r)
    limit = (en and not re.search(r"market|~|at scan|implied", entry_txt)) or (cond and en)
    i0 = 0
    if limit:
        lo, hi = min(en[:2]), max(en[:2]); close_fill = "close" in entry_txt
        brk = R.break_condition(r)
        for i, (t, o, h, l, c) in enumerate(b):
            if brk: ok = (c >= hi if not short else c <= lo) if close_fill else (h >= hi if not short else l <= lo)
            else: ok = (lo <= c <= hi) if close_fill else (l <= hi and h >= lo)  # price traded into the zone
            if ok:
                if cond and t > ts + FILL_HOURS * 3600: break  # filled only after the 48h window: counts as not filled
                i0 = i; FILLS[r["id"]] = {"filled": True, "at": t}; break
        else: pass
        if r["id"] not in FILLS or not FILLS[r["id"]].get("filled"):
            FILLS[r["id"]] = {"filled": False, "checked": int(time.time())}
            if cond and time.time() >= ts + FILL_HOURS * 3600:
                return ("not_filled", f"conditional entry {lo:g}-{hi:g} not triggered within {FILL_HOURS}h of the post", src, ts + FILL_HOURS * 3600)
            return ("open", f"entry {lo:g}-{hi:g} not filled yet", src)
    S = st[0] if st else None
    T = (min(tg) if not short else max(tg)) if tg else None  # first target in trade direction
    for t, o, h, l, c in b[i0:]:
        when = datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")
        hitT = T is not None and (h >= T if not short else l <= T)
        sx = c if stop_close else (l if not short else h)
        hitS = S is not None and (sx <= S if not short else sx >= S)
        if hitT and hitS: return ("open", f"target {T:g} and stop {S:g} in same bar {when}: ambiguous", src)
        if hitT: return ("hit_target", f"{'high' if not short else 'low'} {h if not short else l:g} reached target {T:g} (bar {when} Lisbon)", src, t)
        if hitS: return ("stopped", f"{'close' if stop_close else ('low' if not short else 'high')} {sx:g} through stop {S:g} (bar {when} Lisbon)", src, t)
    last = b[-1][4]
    return ("open", f"no level hit; last {last:g}", src)
FILL_HOURS = 48  # conditional calls (limit/zone/break trigger) close as not_filled if the entry hasn't triggered 48h after the post
FILLS = {}
LEVEL_DAYS = 30  # Manager rule: calls with a stop/target and no stated timeframe expire 30 days after the post
MON = {m: i for i, m in enumerate(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}
def timeframe_end(r):
    """Date the call's own stated timeframe ends, or None. Only explicit phrases; ignores segments about other calls (#123, prior)."""
    post = datetime.datetime.strptime(r["logged_at_lisbon"], "%Y-%m-%d %H:%M").date()
    segs = [r.get("target", "")] + [x for x in R._split_top(R.call_text(r)) if not re.search(r"#\d|\bprior\b|earlier post", x, re.I)]
    t = " ; ".join(segs)
    def md(mon, day):
        d = datetime.date(post.year, MON[mon[:3].lower()], int(day))
        return d if d >= post else datetime.date(post.year + 1, d.month, d.day)
    m = re.search(r"\bexpires? after (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* (\d{1,2})\b", t, re.I) or \
        re.search(r"\bby (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* (\d{1,2})\b", t, re.I)
    if m: return md(m.group(1), m.group(2))
    if re.search(r"\bby (?:the )?end of (?:the |this )?week\b|\bfinish this week\b", t, re.I): return post + datetime.timedelta(days=6 - post.weekday())
    if re.search(r"\bby (?:the )?end of (?:the |this )?month\b", t, re.I):
        n = (post.replace(day=28) + datetime.timedelta(days=4)); return n - datetime.timedelta(days=n.day)
    if re.search(r"\bby (?:the )?(?:end of (?:the )?day|close today)\b|\bEOD\b", t): return post
    return None
def day_close(asset, day):
    """Closing price of that calendar day: OKX 1D (UTC) for crypto, CNBC daily bar (last trading day <= day) otherwise."""
    a = R.norm(asset)
    if a in R.CRYPTO:
        end = int(datetime.datetime(day.year, day.month, day.day, tzinfo=datetime.timezone.utc).timestamp()) + 86400
        d = R.get(f"https://www.okx.com/api/v5/market/history-candles?instId={R.okx_inst(a)}&bar=1Dutc&after={end*1000}&limit=1", tries=2).get("data") or []
        if not d: raise RuntimeError("okx: no daily bar")
        return float(d[0][4]), "OKX 1D close"
    sym = R.CNBC_HIST.get(a, a)
    b = R.get(f"https://ts-api.cnbc.com/harmony/app/charts/1M.json?symbol={sym}", tries=2)["barData"]["priceBars"] or []
    b = [x for x in b if x.get("close") not in (None, "") and x["tradeTime"][:8] <= day.strftime("%Y%m%d")]
    if not b: raise RuntimeError(f"cnbc: no daily bar for {sym}")
    return float(b[-1]["close"]), f"CNBC daily close {b[-1]['tradeTime'][:8]}"
def time_limit(r):
    """(end_date, why) if a leveled call's time limit has passed, else None."""
    tf = timeframe_end(r); post = datetime.datetime.strptime(r["logged_at_lisbon"], "%Y-%m-%d %H:%M").date()
    end, why = (tf, "stated timeframe ended") if tf else (post + datetime.timedelta(days=LEVEL_DAYS), f"{LEVEL_DAYS}-day limit passed")
    return (end, why) if end < datetime.date.today() else None
NO_LEVEL_DAYS = 7  # Manager rule: calls with no levels lock after 7 days
def never_filled(r):
    """(True, src) if a conditional entry never triggered between the post and resolved_at (default post+48h), else None."""
    en = nums(r["entry"]); ts = R._ts_utc(r)
    if not en or not ts: return None
    end = ts + FILL_HOURS * 3600
    try: end = max(end, int(datetime.datetime.strptime(r["resolved_at"][:16], "%Y-%m-%d %H:%M").timestamp()))
    except ValueError:
        try: end = max(end, int(datetime.datetime.strptime(r["resolved_at"][:10], "%Y-%m-%d").timestamp()) + 86399)
        except ValueError: pass
    b, src = bars(r["asset"], ts); b = [x for x in b if x[0] <= end]
    if not b: return None
    short = R.is_short(r["direction"]); lo, hi = min(en[:2]), max(en[:2]); close_fill = "close" in r["entry"].lower(); brk = R.break_condition(r)
    for t, o, h, l, c in b:
        if brk: ok = (c >= hi if not short else c <= lo) if close_fill else (h >= hi if not short else l <= lo)
        else: ok = (lo <= c <= hi) if close_fill else (l <= hi and h >= lo)  # price traded into the zone
        if ok: return None
    return (True, src)
def main():
    apply = "--apply" in sys.argv; reclass = "--reclassify-expired" in sys.argv
    rows = list(csv.DictReader(open(L, encoding="utf-8"))); fields = list(rows[0].keys())
    changes = []
    for r in rows:
        if reclass:
            if r["status"] == "expired" and R.is_conditional(r) and not R.is_ratio(r):
                try: f = never_filled(r)
                except Exception as e: print(f'#{r["id"]} price error: {e}'); continue
                if f: changes.append((r, ("not_filled", f"was expired; conditional entry never triggered before {r['resolved_at']}", f[1], None))); print(f'#{r["id"]} {r["asset"]} expired -> not_filled ({f[1]})')
            continue
        if r["status"] != "open" or "context" in r["direction"].lower(): continue
        if R.is_ratio(r): print(f'#{r["id"]} {r["asset"]} skipped: ratio/spread call, no single tradable price'); continue
        if not nums(r["stop"]) and not nums(r["target"]):  # no levels: time limit only, locks 7 days after post
            ts = R._ts_utc(r)
            if ts and time.time() >= ts + NO_LEVEL_DAYS * 86400:
                j = ("expired", f"no levels; {NO_LEVEL_DAYS}-day time limit passed (score locked at post+7d)", "time limit", ts + NO_LEVEL_DAYS * 86400)
                print(f'#{r["id"]} {r["account"]} {r["asset"]} {r["direction"]} -> expired: {j[1]}'); changes.append((r, j))
            continue
        try: j = judge(r)
        except Exception as e: j = ("open", f"price error: {e}", "-")
        if j is None: continue
        if j[0] == "open":  # no level hit: check the time limit
            tl = time_limit(r)
            if tl:
                try:
                    px, src = day_close(r["asset"], tl[0])
                    j = ("expired", f"{tl[1]} {tl[0]}; exit_close={px:g} ({src}); scored by % move from entry", src, int(datetime.datetime.combine(tl[0], datetime.time(23, 59)).timestamp()))
                    changes.append((r, j))
                except Exception as e: j = ("open", f"{tl[1]} {tl[0]} but no close price: {e}", "-")
        print(f'#{r["id"]} {r["account"]} {r["asset"]} {r["direction"]} e={r["entry"]!r} s={r["stop"]!r} t={r["target"]!r} -> {j[0]}: {j[1]} [{j[2]}]')
        if j[0] in ("hit_target", "stopped", "not_filled"): changes.append((r, j))
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    if only: changes = [(r, j) for r, j in changes if j[0] in only[0].split(",")]
    print(f"\n{len(changes)} to close ({sum(j[0] == 'not_filled' for _, j in changes)} not_filled)")
    if apply:
        try: old = json.load(open(R.FILL_STATE))
        except Exception: old = {}
        old.update(FILLS); R.write_json(R.FILL_STATE, old)
    if apply and changes:
        for r, j in changes:
            r["status"] = j[0]
            if j[3] is not None: r["resolved_at"] = datetime.datetime.fromtimestamp(j[3]).strftime("%Y-%m-%d")
            r["notes"] = (r["notes"] + f"; resolved {datetime.datetime.now():%Y-%m-%d %H:%M} Lisbon from {j[2]}: {j[1]}").lstrip("; ")
        os.makedirs(os.path.join(os.path.dirname(L), "backups"), exist_ok=True)
        shutil.copyfile(L, os.path.join(os.path.dirname(L), "backups", f"call-ledger.backup-{int(time.time())}.csv"))
        tmp = L + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
        os.replace(tmp, L); print("applied")
if __name__ == "__main__": main()
