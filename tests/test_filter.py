#!/usr/bin/env python3
"""Run: python3 tests/test_filter.py  — spam text rules must judge only the call's own text."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import refresh as R

ROW_439 = {"id": "439", "account": "@Bitcoin_World20", "entry": "80300 (limit)", "stop": "79300", "target": "85000",
    "notes": 'source discovery; "Trying this #BTC long Entry - 80.3k SL - 79.3k TP - 85k" (12:47 Lisbon); ~11.8k followers, '
             'no Telegram/VIP/referral seen - passes rules; discovery not alerted; rejected rest of discovery: signal sellers '
             '(AlexGoldHunter VIP, gen_hula free group), Telegram/VIP groups, copy-paste gold clones (YShirley_XAUUSD), after-the-fact (Crypto__Haris); not financial advice'}
PROMO = {"id": "9001", "account": "@promo", "entry": "100", "stop": "90", "target": "120",
    "notes": 'source discovery; "Join my Telegram VIP group for the BTC long, entry 100" ; posted after the fact'}

def test_439_not_flagged():
    assert R.spam_flags(ROW_439) == [], R.spam_flags(ROW_439)
    assert R.after_the_fact(ROW_439) is False

def test_promo_flagged():
    f = R.spam_flags(PROMO)
    assert "telegram_promo" in f and "vip_promo" in f, f
    assert R.after_the_fact(PROMO) is True

def test_negation_and_explicit_flag():
    assert R.after_the_fact({"notes": "entry posted live, not after-the-fact"}) is False
    assert R.after_the_fact({"notes": "clean", "after_the_fact": "true"}) is True
    assert R.spam_flags({"notes": "x", "own_notes": "Telegram signal"}) == ["telegram_promo"]
    assert R.spam_flags({"notes": "clean call", "scan_log": "Telegram VIP"}) == []

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
    print("ALL FILTER TESTS PASSED")
