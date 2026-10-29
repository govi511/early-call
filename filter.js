// ===== Quality filter (see FILTER_RULES.md) — loaded before app.js renders =====
const SPAM_RULES=[[/telegram/i,'Telegram promo'],[/\bvip\b/i,'VIP promo'],[/referral|ref link/i,'referral link'],[/affiliate/i,'affiliate link'],[/low[- ]follower/i,'low-follower account'],[/thin account|bot account/i,'thin/bot account'],[/cop(y|ied)/i,'copied post'],[/duplicate/i,'duplicate'],[/after[ _-]the[ _-]fact/i,'after the fact'],[/\bstale\b/i,'stale']];
// Shared short-direction rule (mirrors is_short in refresh.py)
const isShort=d=>{d=String(d||'').trim().toLowerCase();return/^(short|bear|put|hike)/.test(d)||d.includes('short')};window.isShort=isShort;
// One scored call per source link: earliest row wins
const dupOfLink=c=>{if(c.split_of||!c.post_url||typeof LEDGER==='undefined'||!LEDGER)return null;const f=LEDGER.calls.filter(o=>o.post_url===c.post_url&&!o.split_of).sort((a,b)=>String(a.logged_at_lisbon).localeCompare(String(b.logged_at_lisbon))||(+a.id)-(+b.id))[0];return f&&f!==c?f:null};
const normEntry=e=>String(e||'').replace(/\s+/g,'').toLowerCase();
// Negation covers whole lists: "no Telegram/VIP/referral in post", "no spam, referral or VIP text"
const NEG_LIST=/\b(?:no|not|without|never|isn't|is not|not a)\s+(?:an?\s+|any\s+)?[\w-]+(?:\s*(?:\/|,|\bor\b|\band\b|&)\s*[\w-]+)*(?:\s+(?:links?|promos?|posts?|accounts?|text|group|groups))?/gi;
// Clauses that describe the account (bio, history) rather than this post: "note his referral links", "bio carries ...", "posts affiliate links"
const ACCOUNT_DESC=/\b(?:bio|his|her|their|he also|she also|account (?:has|posts)|posts (?:\w+ )?(?:affiliate|referral) links?|has a (?:losing|winning)[\w\/ ]* record)\b/i;
const stripNeg=t=>String(t).split(/[;()]/).filter(seg=>!ACCOUNT_DESC.test(seg)).join(' ; ').replace(NEG_LIST,' ');
function spamWhy(c){const n=c.notes||'';
 // manual override wins: true/"spam" forces hidden, false/"not_spam" clears every spam reason (news rows still stay news)
 const ov=c.spam_override;const lov=typeof localStorage!=='undefined'&&localStorage.getItem&&localStorage.getItem('ec-notspam-'+c.id);
 if(ov===false||ov==='not_spam'||lov)return(c.kind!=='flow'&&(/^early-signal/i.test(n)||/\(context\)/i.test(c.direction||'')))?['news post, not a buy/sell call']:[];
 const why=[];if(ov===true||ov==='spam')why.push('manual spam override');
 // structured flags (refresh.py) when present, text rules otherwise
 if(Array.isArray(c.spam_flags))c.spam_flags.forEach(f=>why.push(String(f).replace(/_/g,' ')));
 else{const nn=stripNeg(c.call_notes??'');SPAM_RULES.filter(([re])=>re.test(nn)).forEach(r=>why.push(r[1]));String(c.spam_flags||'').split(/[;,]/).map(x=>x.trim()).filter(Boolean).forEach(f=>why.push(f.replace(/_/g,' ')))}
 if(c.kind!=='flow'&&(/^early-signal/i.test(n)||/\(context\)/i.test(c.direction||'')))why.push('news post, not a buy/sell call');
 const m=c.followers!==undefined?(c.followers!=null?[0,c.followers]:null):n.match(/\b(\d+) followers\b/i);if(m&&+m[1]<50)why.push(`only ${m[1]} followers`);
 if(/^(filtered|excluded)$/.test(c.status||''))why.push('excluded by rule ('+c.status+')');
 // under 5k followers: shown with low_confidence (c.low_confidence / .lowconf), no longer hidden
 if(c.after_the_fact)why.push('after the fact');
 if(c.copy_of)why.push(`copy of #${c.copy_of}`);
 if(c.spam_farm||(typeof LEDGER!=='undefined'&&LEDGER&&(LEDGER.spam_farm_accounts||[]).includes(c.account)))why.push('spam-farm account (copy-paste cluster)');
 // identical asset+direction+entry already posted by a different account earlier in the ledger
 const e=normEntry(c.entry);if(e&&typeof LEDGER!=='undefined'&&LEDGER){const first=LEDGER.calls.find(o=>o.asset===c.asset&&isShort(o.direction)===isShort(c.direction)&&normEntry(o.entry)===e);if(first&&first.account!==c.account&&first!==c)why.push(`duplicate of ${first.account}`)}
 return[...new Set(why)]}
// words in the notes that triggered the text rules (shown when the reason chip is tapped)
function spamWords(c){const nn=stripNeg(c.call_notes??''),out=[];SPAM_RULES.forEach(([re])=>{const m=nn.match(re);if(m)out.push(m[0])});return[...new Set(out)]}
const _spamCache=new WeakMap();
const isSpam=c=>{if(!_spamCache.has(c))_spamCache.set(c,spamWhy(c).length>0);return _spamCache.get(c)};
const isEarlySignal=c=>/early[- ]signal/i.test(c.notes||'');
// Calls that count toward win rates / leaderboard: not spam, not early-signal rows
const countsForRecord=c=>!c.split_into&&c.status!=='not_filled'&&!isSpam(c)&&!isEarlySignal(c)&&!dupOfLink(c);
function srcOf(c){const n=(c.notes||'').toLowerCase();return/early[- ]signal|\bsec\b|filing|13f|form 4/.test(n)?['Early signal','filing']:/source following|watchlist/.test(n)?['Following','watchlist']:/source discovery/.test(n)?['X search','x']:null}
function srcHTML(c){const s=srcOf(c);return s?`<span class="src ${s[1]}">${s[0]}</span>`:''}
const MIN_CLOSED=10;
// Outlier guard: a single call moving more than ±OUTLIER_PCT % is almost always a bad price/level read; left out of averages, records and sorting until checked
const OUTLIER_PCT=300;
const callPct=c=>{if(c.exit_pct!=null)return c.exit_pct;if(c.locked_pct!=null)return c.locked_pct;if(typeof callRes==='function'){const r=callRes(c);if(r.p!=null)return r.p;if(r.ne&&typeof SP==='function')return SP(c)}return null};
const isOutlier=c=>{const v=callPct(c);return v!=null&&isFinite(v)&&Math.abs(v)>OUTLIER_PCT};
const OUTLIER_TIP=c=>`Move of ${callPct(c).toFixed(0)}% is beyond ±${OUTLIER_PCT}% — likely a bad price or level read. Left out of averages, win rate and ranking until checked.`;
function recordOf(acc){const r=(typeof LEDGER!=='undefined'&&LEDGER?LEDGER.calls:[]).filter(c=>c.account===acc&&countsForRecord(c)&&!isOutlier(c)&&(c.locked_pct!=null||['hit_target','stopped'].includes(c.status)&&(typeof callRes!=='function'||callRes(c).p!=null)));const w=r.filter(c=>c.locked_pct!=null?c.locked_pct>0:c.status==='hit_target').length;const x=(typeof LEDGER!=='undefined'&&LEDGER?LEDGER.calls:[]).filter(c=>c.account===acc&&countsForRecord(c)&&c.status==='expired'&&c.locked_pct==null).length;return{n:r.length,w,x,rate:r.length>=MIN_CLOSED?w/r.length:null}}
function winrateHTML(acc){const r=recordOf(acc);return r.rate==null?`<span class="winrate" title="${r.n}/${MIN_CLOSED} closed calls before a win rate is shown">Win rate <b>new</b> · ${r.n}/${MIN_CLOSED} closed${r.x?' · '+r.x+' expired':''}</span>`:`<span class="winrate" title="${r.w} of ${r.n} closed calls hit target${r.x?`; ${r.x} expired (neither win nor loss)`:''}">Win rate <b>${Math.round(r.rate*100)}%</b></span>`}
const FEED=()=>localStorage.getItem('ec-feed')||'all';
function feedOf(c){if(c.feed)return c.feed;return /source following/i.test(c.notes||'')?'following':'discovery'}
const isLowConf=c=>c.low_confidence===true||(c.low_confidence==null&&c.followers!=null&&c.followers<5000);window.isLowConf=isLowConf;
