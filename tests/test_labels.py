#!/usr/bin/env python3
"""Run: python3 tests/test_labels.py - index labels map to a price source; multi-ticker labels split into per-ticker calls."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import refresh as R

def test_index_labels():
    for a, t in [("US 500 (ES futures levels)", "ES"), ("US 500 (ES Dec-26 futures)", "ES"), ("ES", "ES"), ("SPX", "SPX"), ("US 500", "SPX"), ("SPY (US 500)", "SPY")]:
        assert R.norm(a) == t, (a, R.norm(a))
    assert R.YAHOO_MAP["ES"] == "ES=F" and R.CNBC_MAP["ES"] == "@SP.1" and R.STOOQ_MAP["ES"] == "es.f"
    assert R.YAHOO_MAP["SPX"] == "^GSPC"

def test_split():
    assert R.split_tickers({"asset": "AAPL/TSLA/SPCX", "kind": "call"}) == ["AAPL", "TSLA", "SPCX"]
    assert R.split_tickers({"asset": "ETH/BTC", "kind": "call"}) == []          # ratio pair alias, not split
    assert R.split_tickers({"asset": "Oil/WTI", "kind": "call"}) == []          # same instrument
    assert R.split_tickers({"asset": "AAPL/TSLA/SPCX", "kind": "news"}) == ["AAPL", "TSLA", "SPCX"]  # derived rows keep kind=news
    assert R.split_tickers({"asset": "US 500 (ES futures levels)", "kind": "call"}) == []
    rows = [{"id": "464", "asset": "AAPL/TSLA/SPCX", "kind": "call", "entry": "200", "stop": "190", "target": "220", "status": "hit_target"}]
    R.add_splits(rows)
    assert [r["id"] for r in rows] == ["464", "464-AAPL", "464-TSLA", "464-SPCX"]
    assert rows[0]["asset"] == "AAPL/TSLA/SPCX" and rows[0]["split_into"] == ["464-AAPL", "464-TSLA", "464-SPCX"]
    assert rows[1]["entry"] == "200" and rows[1]["status"] == "hit_target"
    assert rows[2]["entry"] == "" and rows[2]["status"] == "open" and rows[2]["split_of"] == "464"

if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); print("ok", k)
