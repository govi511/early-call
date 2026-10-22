#!/usr/bin/env python3
"""Weekly call scorecard from the call ledger. Read-only; never edits the ledger.
Usage: python3 scorecard.py [ledger.csv] [--week-end YYYY-MM-DD] [--recheck]
  --recheck  also run tools/resolve_calls.py (dry run) and list open calls whose target/stop was hit per real candles.
Robust: csv module (quoted commas/newlines), utf-8-sig/CRLF, duplicate ids, bad rows skipped and counted."""
import csv, sys, os, re, datetime, collections, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
DEF = "/cursor/stores/store-9d60204b-cf80-460e-a058-55dafdd15548/call-ledger.csv"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
src = args[0] if args else DEF
we = None
if "--week-end" in sys.argv: we = datetime.date.fromisoformat(sys.argv[sys.argv.index("--week-end") + 1]); args = [a for a in args if a != str(we)]
today = we or datetime.date.today()
wk_start = today - datetime.timedelta(days=today.weekday())  # Monday
try:
    with open(src, encoding="utf-8-sig", newline="") as f: raw = list(csv.DictReader(f))
except Exception as e:
    print(f"SCORECARD ERROR: cannot read ledger {src}: {e}"); sys.exit(1)
rows, bad, seen = [], 0, collections.Counter()
for r in raw:
    try:
        r = {k: (v or "").strip() for k, v in r.items() if k}
        r["_dt"] = datetime.datetime.strptime(r["logged_at_lisbon"][:16], "%Y-%m-%d %H:%M")
        seen[r["id"]] += 1; rows.append(r)
    except Exception: bad += 1
def is_call(r):
    d = r.get("direction", "").lower(); n = r.get("notes", "").lower()
    return "context" not in d and r.get("status") != "filtered" and not n.startswith("early-signal; type=context")
calls = [r for r in rows if is_call(r)]
A = collections.defaultdict(lambda: collections.Counter())
for r in calls:
    a = r["account"] or "(none)"; c = A[a]; st = r["status"] or "open"
    c["all"] += 1; c[st] += 1
    if r["_dt"].date() >= wk_start: c["week"] += 1
    if re.search(r"after[- ]the[- ]fact", r.get("notes", ""), re.I) and not re.search(r"rejected[^;]*after[- ]the[- ]fact", r["notes"], re.I): c["atf"] += 1
def _lv(t):
    t = re.sub(r"\(.*?\)", "", t or ""); t = re.sub(r"(\d),(?=\d{3}\b)", r"\1", t)
    n = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]; return sum(n[:2]) / len(n[:2]) if n else None
def call_pct(r):
    """% move from entry: hit -> first target, stopped -> stop, expired -> exit_close (that day's close). None if unscorable."""
    e = _lv(r.get("entry")); st = r.get("status")
    if not e and st == "expired":  # no entry given: price at post time (data/baselines.json), same as the leaderboard
        try: e = BASE.get(f'{r["id"]}|{r["asset"].upper()}|{r["logged_at_lisbon"]}', {}).get("price")
        except Exception: e = None
    if not e: return None
    if st == "hit_target":
        n = re.findall(r"\d+(?:\.\d+)?", re.sub(r"(\d),(?=\d{3}\b)", r"\1", re.sub(r"\(.*?\)", "", r.get("target") or ""))); x = float(n[0]) if n else None
    elif st == "stopped": x = _lv(r.get("stop"))
    elif st == "expired":
        m = re.search(r"\bexit_close=([\d.]+)", r.get("notes", "")); x = float(m.group(1)) if m else None
    else: return None
    if x is None: return None
    d = -1 if re.match(r"\s*(short|bear|put)", r.get("direction", ""), re.I) or "short" in r.get("direction", "").lower() else 1
    return d * (x - e) / e * 100
try:
    import json; BASE = json.load(open(os.path.join(HERE, "data", "baselines.json")))
except Exception: BASE = {}
PCT = collections.defaultdict(list)
for r in calls:
    p = call_pct(r)
    if p is not None: PCT[r["account"] or "(none)"].append(p)
def avgp(a): v = PCT.get(a); return f"{sum(v)/len(v):+.1f}" if v else "-"
def wr(c): n = c["hit_target"] + c["stopped"]; return (c["hit_target"] / n * 100 if n else None), n
out = [f"EARLY CALL WEEKLY SCORECARD - week {wk_start} to {wk_start + datetime.timedelta(days=6)} (Lisbon)",
       f"Ledger: {len(rows)} rows, {len(calls)} scored calls (context/filtered rows excluded), {sum(c['week'] for c in A.values())} calls this week."]
if bad: out.append(f"Warning: {bad} unreadable rows skipped.")
d = [k for k, v in seen.items() if v > 1]
if d: out.append(f"Warning: duplicate ledger ids {', '.join(d)} (counted as separate calls).")
tot = collections.Counter(); [tot.update(c) for c in A.values()]
w, n = wr(tot)
out.append(f"All accounts: hit {tot['hit_target']} / stopped {tot['stopped']} / expired {tot['expired']} / unclear {tot['unclear']} / open {tot['open']}; win rate {w:.0f}% of {n} resolved." if w is not None else "No resolved calls yet.")
out += ["", "PER ACCOUNT (accounts with a call this week or any resolved call)",
        f"{'account':28} {'wk':>3} {'all':>4} {'hit':>4} {'stop':>4} {'exp':>4} {'uncl':>4} {'open':>4} {'win%':>5} {'avg%':>6} {'ATF':>4}"]
act = {a: c for a, c in A.items() if c["week"] or c["hit_target"] + c["stopped"]}
for a, c in sorted(act.items(), key=lambda x: (-x[1]["week"], -x[1]["all"], x[0].lower())):
    w, n = wr(c)
    out.append(f"{a[:28]:28} {c['week']:>3} {c['all']:>4} {c['hit_target']:>4} {c['stopped']:>4} {c['expired']:>4} {c['unclear']:>4} {c['open']:>4} {(f'{w:.0f}' if w is not None else '-'):>5} {avgp(a):>6} {c['atf']:>4}")
out += ["", "RANKING (win rate = hit / (hit + stopped); ties by more resolved)"]
rk = sorted(((wr(c)[0], wr(c)[1], a) for a, c in A.items() if wr(c)[1]), key=lambda x: (-(x[1] >= 5), -x[0], -x[1], x[2].lower()))
for i, (w, n, a) in enumerate(rk, 1): out.append(f"{i:>2}. {a} - {w:.0f}% ({n} resolved){'  *small sample' if n < 5 else ''}")
out.append("Note: accounts with fewer than 5 resolved calls (*) are ranked below the rest; their win rates are not meaningful yet. Expired/unclear calls are not counted as wins or losses. ATF = after-the-fact posts flagged in notes. avg% = mean % move from entry over hit, stopped and time-expired calls (expired use that day's close).")
if "--recheck" in sys.argv:
    out += ["", "RE-CHECK OF OPEN CALLS WITH LEVELS (real OKX/CNBC candles, dry run - ledger not changed)"]
    try:
        p = subprocess.run([sys.executable, os.path.join(HERE, "tools", "resolve_calls.py")], capture_output=True, text=True, timeout=600)
        hits = [l for l in p.stdout.splitlines() if "-> hit_target" in l or "-> stopped" in l]
        out += hits or ["No open call has hit its target or stop since the last update."]
        if p.returncode: out.append(f"(re-check exited {p.returncode}: {p.stderr.strip()[-300:]})")
    except Exception as e: out.append(f"(re-check failed: {e})")
print("\n".join(out))
