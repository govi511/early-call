#!/usr/bin/env python3
"""Run: python3 tests/test_levels.py - dates and percentages are never price levels (#508, #523)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import refresh as R, resolve_calls as RC

def test_dates_dropped():
    assert R.level_nums("expire between 7295 and 7910 by Oct 30") == [7295, 7910]
    assert R.level_nums("by October 30th, 2026: 120") == [120]
    assert R.level_nums("30 Oct 7700") == [7700]
    assert R.level_nums("2026-10-30 close 81200") == [81200]

def test_percentages_dropped():
    assert R.level_nums("10-20% bounce") == []
    assert R.level_nums("+3% to +5% (session)") == []
    assert R.level_nums("5% move, 120 target") == [120]

def test_real_levels_kept():
    for s, n in [("17/22/28", [17, 22, 28]), ("85000-86000 / 90000", [85000, 86000, 90000]), ("7783 / 7803 ES", [7783, 7803]),
                 ("4.30 (range low)", [4.3]), ("81,200", [81200]), ("115 strike (Mar calls)", [115]), ("400-410 strikes (Oct 28 calls)", [400, 410])]:
        assert R.level_nums(s) == n, (s, R.level_nums(s))

def test_shared_parser():
    assert RC.nums("expire between 7295 and 7910 by Oct 30") == R.level_nums("expire between 7295 and 7910 by Oct 30")

def test_508_523_not_judged():
    r508 = {"id": "508", "direction": "neutral (iron condor, options)", "entry": "~7640 (SPX at entry)", "stop": "", "target": "expire between 7295 and 7910 by Oct 30", "asset": "SPX"}
    r523 = {"id": "523", "direction": "long (short-term bounce)", "entry": "~0.143 (market)", "stop": "below recent lows (~0.139)", "target": "10-20% bounce", "asset": "BAT"}
    assert RC.judge(r508) is None and RC.judge(r523) is None  # no network: returns before fetching bars

def test_commodity_labels_priceable():
    assert R.YAHOO_MAP[R.norm("XAUUSD (GOLD)")] == "GC=F" and R.YAHOO_MAP[R.norm("WTI CRUDE OIL (CL)")] == "CL=F"

if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); print("ok", k)
    print("ALL LEVEL TESTS PASSED")
