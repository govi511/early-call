# Early Call — spam / quality filter rules

Implemented in `filter.js`. A call is **filtered** (hidden by default on Signals, excluded from the summary strip) if ANY rule matches. Toggle **"Show filtered (N)"** to see them; each shows a red `filtered` badge whose tooltip lists the reasons.

## Note keywords (case-insensitive, in the ledger `notes` column)
| Pattern | Reason |
|---|---|
| `telegram` | Telegram promo |
| `vip` (whole word) | VIP promo |
| `referral`, `ref link` | referral link |
| `affiliate` | affiliate link |
| `low-follower`, `low follower` | low-follower account |
| `thin account`, `bot account` | thin/bot account |
| `copy`, `copied` | copied post |
| `duplicate` | duplicate |
| `after the fact` / `after_the_fact` / `after-the-fact` | posted after the move |
| `stale` (whole word) | stale/recycled call |
| `N followers` with N < 50 | low-follower account |

Also filtered if the ledger's `after_the_fact` flag is true.

## Duplicates
If another account posted the same **asset + direction + entry** (entry compared with whitespace removed) **earlier in the ledger**, the later copy is filtered as `duplicate of @first`. The earliest poster is kept (unless another rule hits it).

## Copy-paste clusters (computed in `refresh.py` when building ledger.json)
Fingerprint = asset + direction + numbers in entry/stop/target (labels ignored). Same fingerprint from **different accounts within 48h** of the earliest post → every later post gets `copy_of: <earliest id>`, and every account in the cluster is listed in `spam_farm_accounts`. All calls from spam-farm accounts are filtered (`spam-farm account`), including the earliest.

## Where spam is excluded
Filtered calls are excluded from the summary strip, leaderboard, win rates and hype meter. Rows whose notes contain `early-signal` are additionally excluded from win rates and the leaderboard (they are not trade calls). The ledger CSV itself is never changed.

## Badges
- Source `<span class="src …">`: `watchlist` = Following (notes "source following"/"watchlist"), `x` = X search ("source discovery"), `filing` = Early signal ("early-signal", SEC/filing/13F/Form 4).
- `<span class="winrate">`: `Win rate <b>NN%</b>` only once the account has **≥10 closed calls** (hit_target + stopped); otherwise `Win rate <b>new</b> · n/10 closed`. Leaderboard ranks (#1, #2…) follow the same rule; unranked accounts are listed after, by closed-call count.
- Filtered cards get class `hidden-spam` when "Show filtered" is on.
