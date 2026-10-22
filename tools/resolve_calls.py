#!/usr/bin/env python3
"""Resolve open ledger calls that have numeric levels, strictly from real candles.
Closes a call only if price actually hit target or stop after the post (and after the entry filled,
when the entry is a limit level/zone). Same-bar target+stop = ambiguous -> stays open.
Prints proposed changes; --apply writes them to the ledger CSV (atomic, backup kept)."""
import csv, sys, os, re, time, shutil, datetime, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refresh as R
L = "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
def nums(s):
    s = re.sub(r"\(.*?\)", "", s or ""); s = re.sub(r"(\d),(?=\d{3}\b)", r"\1", s)
    s = re.sub(r"\b\d{1,2}:\d{2}\b|\b\d+[- ](?:day|week|hour|h|d|w)\b", " ", s, flags=re.I)
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
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
    short = R.is_short(r["direction"]); ts = R._ts_utc(r)
    b, src = bars(r["asset"], ts)
    if not b: return ("open", "no bars since post", src)
    stop_close = "close" in r["stop"].lower()
    entry_txt = r["entry"].lower()
    limit = en and not re.search(r"market|~|at scan|implied", entry_txt)
    i0 = 0
    if limit:
        lo, hi = min(en[:2]), max(en[:2]); close_fill = "close" in entry_txt
        for i, (t, o, h, l, c) in enumerate(b):
            ok = (lo <= c <= hi) if close_fill else (l <= hi if not short else h >= lo)
            if ok: i0 = i; break
        else: return ("open", f"entry {lo:g}-{hi:g} not filled yet", src)
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
def main():
    apply = "--apply" in sys.argv
    rows = list(csv.DictReader(open(L, encoding="utf-8"))); fields = list(rows[0].keys())
    changes = []
    for r in rows:
        if r["status"] != "open" or "context" in r["direction"].lower(): continue
        try: j = judge(r)
        except Exception as e: j = ("open", f"price error: {e}", "-")
        if j is None: continue
        print(f'#{r["id"]} {r["account"]} {r["asset"]} {r["direction"]} e={r["entry"]!r} s={r["stop"]!r} t={r["target"]!r} -> {j[0]}: {j[1]} [{j[2]}]')
        if j[0] in ("hit_target", "stopped"): changes.append((r, j))
    print(f"\n{len(changes)} to close")
    if apply and changes:
        for r, j in changes:
            r["status"] = j[0]; r["resolved_at"] = datetime.datetime.fromtimestamp(j[3]).strftime("%Y-%m-%d")
            r["notes"] = (r["notes"] + f"; resolved {datetime.datetime.now():%Y-%m-%d %H:%M} Lisbon from {j[2]}: {j[1]}").lstrip("; ")
        shutil.copy(L, f"/workspace/call-ledger.backup-{int(time.time())}.csv")
        tmp = L + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
        os.replace(tmp, L); print("applied")
if __name__ == "__main__": main()
