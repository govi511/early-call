#!/usr/bin/env python3
"""Run: python3 tests/test_suffix_ratio.py - K/M suffixes expand (#654, #683); ratio calls priced as ratio of USD legs (#697)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import refresh as R, resolve_calls as RC

def test_suffixes():
    assert R.level_nums("80K") == [80000]
    assert R.level_nums("reclaim of 80K as sign of strength") == [80000]
    assert R.level_nums("20k+") == [20000]
    assert R.level_nums("1.2M") == [1200000]
    assert R.level_nums("76.9K") == [76900]
    assert R.level_nums("spot accumulation 72K-current") == [72000]
    assert RC.nums("20k+") == [20000]
    assert R.level_nums("15m close 7700") == [7700]  # bare m stays a timeframe

def test_ratio():
    p = R.ratio_price("SOL/ETH", {"SOL": {"price": 94.25}, "ETH": {"price": 2250.0}})
    assert abs(p["price"] - 94.25 / 2250) < 1e-12 and p["price"] != 94.25
    R.pick = lambda a, ref: (_ for _ in ()).throw(RuntimeError("no"))
    q = R.ratio_price("SOL/ETH", {"SOL": {"price": 94.25}})
    assert q["price"] is None and q["unpriced"]
    assert R.is_ratio({"asset": "SOL/ETH", "direction": "bearish SOL vs ETH"})

if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"): f()
    print("ok")
