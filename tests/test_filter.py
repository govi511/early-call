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
    "notes": 'source discovery; "Join my Telegram VIP group for the BTC long, entry 100 (posted after the fact)"'}

def test_439_not_flagged():
    assert R.spam_flags(ROW_439) == [], R.spam_flags(ROW_439)
    assert R.after_the_fact(ROW_439) is False

def test_promo_flagged():
    f = R.spam_flags(PROMO)
    assert "telegram_promo" in f and "vip_promo" in f, f
    assert R.after_the_fact(PROMO) is True

def test_negation_and_explicit_flag():
    assert R.after_the_fact({"notes": '"entry posted live, not after-the-fact"'}) is False
    assert R.after_the_fact({"notes": "scanner: posted after the fact"}) is False  # note text is never read
    assert R.after_the_fact({"notes": "clean", "after_the_fact": "true"}) is True
    assert R.spam_flags({"notes": "x", "post_text": "Telegram signal"}) == ["telegram_promo"]
    assert R.spam_flags({"notes": "x", "own_notes": "Telegram signal"}) == []
    assert R.spam_flags({"notes": "clean call", "scan_log": "Telegram VIP"}) == []


REGRESSION = {
    '430': 'source following; "Plan: short the retest of 82,970-83,349 on a 1H close inside the zone. Target is the equal lows at 81,505. A 1H close above 83,420 invalidates" (09:00 Lisbon); BTC ~82,100 at scan (zone ~1% above); R:R ~5; pending limit; pedrosilva has referral links and mixed/losing record; alerted; not financial advice | RESOLVED expired 16:30 Lisbon: pedrosilva cancelled it himself (https://x.com/pedrosilva/status/2113291976569139335 ""My morning short plan is off the table"" after BTC dumped on Trump/Iran rumors); the 82,970-83,349 retest zone never filled (BTC high since post ~82,4xx, low 81,257), so no trade/no P/L; his 50s video gives no new setup (shows the old short ~82,450-82,650, entry 82,500, 1H-close invalidation 82,750, target 80,854, marked invalid; Toobit sponsor banner); cancellation alerted',
    '441': 'source following; "$SPCX got the dip under yesterday\'s low I was waiting for. I\'m buying 154.65-155.70 and expecting the US session to carry it to 159.80 first, then back to yesterday\'s 166 high" (14:15 Lisbon, premarket); no stop given; SPCX ~151.5 at scan (already ~2% below the buy zone, day low 150.86); SPCX not confirmed as a T212 CFD and pedrosilva has referral links and a mixed/losing record, so not alerted; not financial advice | 20:08 check: regular-session high 154.22 never reached the 154.65 buy zone; SPCX sold off to ~144.95 (day low 144.50); targets not hit, effectively unfilled',
    '477': 'source following; conditional plan: "No Daily Update today, so here\'s my $BTC plan. Short a push into the 4H FVG at 82,227-82,625 on a 1H close inside. The first bounce overnight already got sold. Target: daily equal lows at 80,809. A 1H close above 82,955 invalidates. A wick isn\'t enough." (07:40 Lisbon); BTC ~81,780 at scan (15m high since post 81,984), entry zone ~0.5-1% above, pending; alerted with caveat: account has referral/affiliate links and weak record in ledger (2 hit_target, 5 stopped, 6 expired). Discovery rejected: Jenniy_XAUUSD levels-only (no direction); rest <5k followers / Telegram / WhatsApp / VIP / link-in-bio gold signal spam (Fxmoontrading, Maviatader, Wangly_XAU, goldmindupdates, Jaklee786, babu_channa1, sniper10728, Aliveb678, AliraScottFX, UniGrow99, SNIPERTRADlez, trad76541, XauusdJohn, Maeve_fxgold_, Farahhkhan95/Ali_naaaa15 duplicate, CoachWill1424/VotlRVA ETH duplicate, SyndicateSig members); following timeline news only (WhaleInsider ETH ETF outflow $110.5M, Kalshi Musk $76M GOP donation, Russian diesel tanker to US after Trump-Putin deal, MarioNawfal China gold buying vs Goldman estimate, bubbleboi BESI chatter); watchlist: DaanCrypto stablecoin supply commentary only; #452 BTC short still open (high 81,984 < 82,150 stop); #473 gold limit unfilled (low ~4018); #476 gold touched 4028.2 at 07:00 candle then fell to ~4018 (zone barely tagged, left open); not financial advice',
    '346': 'source following (also watchlist); role call; "$BTC - Update Give us that pump to $84,000 tonight" = bullish BTC, target 84,000 tonight; no entry/stop (scored from price at post time, BTC ~82,800 OKX); duplicate thesis of alerted #323 (DaanCrypto 84k equal highs), wishful wording, so not alerted; not financial advice | 16:13 Lisbon scan: target 84,000 hit today 15:00 Lisbon hour (high 84,749.5 OKX), later than the "tonight" he said',
    '227': "early-signal; type=context; Axios/N12 (17:07-17:27Z): Netanyahu discussed renewed strikes on Iran with Trump last week, may seek strikes before Israel's Oct 27 election; Trump 'we'll make a decision on Iran very soon' (Kalshi 16:30Z); IRGC navy chief: awaiting US ships near Hormuz 'to sink them' (17:32Z); Trump Truth Social warns Houthis over Saudi attacks/oil prices (16:05Z); Yemen council says Bab al-Mandeb shipping safe. Odds did NOT react sharply: Polymarket US-Iran ceasefire thru Oct 31 ~80.5% (-1pt 1h), Israel-Iran thru Oct 31 ~84.5% (-1pt), WTI hit $95 in Oct ~89.5% (+3.5pt 1h, continuation of #215/#223), $100 in Oct ~44.5%. Also: Bloomberg via WatcherGuru: Trump admin official ordered regulators to withdraw insider-trading referral on March 23 oil bets before Iran announcement (context). Not alerted (no sharp odds move). Public news; not financial advice",
    '495': 'source discovery; ~7.7k followers, since 2019-06; passes follower/age rules but post carries #Roboforex broker hashtag (possible affiliate) and R:R only 1:1.22 - log only, not alerted; posted 16:30 Lisbon, XAUT ~4006 at scan (above entry zone, near stop zone); rejected rest of discovery: copy-paste XAUUSD buy/sell signal spam from <5k accounts (Dropship_XAU, NaomiTheePony free group link, chariman_go, kingof635593, FX_Elsie1, Mickjohnsonfx Telegram, Druckenmilczoo, trad76541, Marinafx002 link-in-bio, bandofrmdaO1 WhatsApp, KHAN_TRADES_02 BTC/gold CMP swing), Finora_EN AI bot on small alts, TIQCrypto TG/news, Digiwealthhq after-the-fact target-done post, conclavedao agent bot; not financial advice | 18:09 scan: entry 3995.63-3997.39 never filled after post (XAUT 16:30 low 3998.4), then stop zone exceeded (highs 4009.4-4009.6 at 16:45-17:45) - expired unfilled, no P/L; not alerted',
}

def _reg(i):
    f = R.spam_flags({"id": i, "notes": REGRESSION[i]}); assert f == [], (i, f)
    assert R.after_the_fact({"notes": REGRESSION[i]}) is False, i
def test_430_referral_note_not_spam(): _reg("430")
def test_441_referral_note_not_spam(): _reg("441")
def test_477_account_history_and_discovery_rejects_not_spam(): _reg("477")
def test_346_duplicate_thesis_note_not_spam(): _reg("346")
def test_227_referral_in_news_note_not_spam(): _reg("227")
def test_495_broker_hashtag_alone_not_spam(): _reg("495")
def test_note_phrasing_never_hides():
    for n in ("X has referral links", "account has affiliate links; Telegram VIP", "rejected: Telegram/VIP copy-paste clones"):
        assert R.spam_flags({"notes": n}) == [], n

def test_470_ratio_call_skipped():
    r = {"id": "470", "asset": "Gold/Silver ratio (GC/SI)", "direction": "long", "entry": "", "stop": "", "target": "121.7 (chart)"}
    assert R.is_ratio(r) and R.is_ratio("BTC vs ETH") and R.is_ratio("Brent-WTI spread")
    assert not R.is_ratio({"asset": "XAUUSD", "direction": "short"}) and not R.is_ratio("EUR/USD") and not R.is_ratio("Oil/Gold/S&P 500")

def test_followers_only_from_posting_account():
    """#570 (CryptoMichNL ~822k) and #581 + splits (AltcoinSherpa ~264k): 'N followers' of rejected discovery accounts later in notes must not stick."""
    import json, re
    calls = {c["id"]: c for c in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ledger.json")))["calls"]}
    for i in ("570", "581", "581-BAT", "581-STRK"):
        c = calls[i]
        assert not re.search(r"\d\s*[km]?\s+followers", R.poster_notes(c["notes"]), re.I), i
        assert c.get("followers") is None or c["followers"] >= 5000, (i, c.get("followers"))
        assert not c.get("low_confidence") and not c.get("spam_flags"), i
    assert R.poster_notes("source discovery; ~15.2k followers; rejected: foo 12 followers").startswith("source discovery; ~15.2k")

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
    print("ALL FILTER TESTS PASSED")
