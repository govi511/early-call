// ===== Quality filter (see FILTER_RULES.md) — loaded before app.js renders =====
const SPAM_RULES=[[/telegram/i,'Telegram promo'],[/\bvip\b/i,'VIP promo'],[/referral|ref link/i,'referral link'],[/affiliate/i,'affiliate link'],[/low[- ]follower/i,'low-follower account'],[/thin account|bot account/i,'thin/bot account'],[/cop(y|ied)/i,'copied post'],[/duplicate/i,'duplicate'],[/after[ _-]the[ _-]fact/i,'after the fact'],[/\bstale\b/i,'stale']];
// Shared short-direction rule (mirrors is_short in refresh.py)
const isShort=d=>{d=String(d||'').trim().toLowerCase();return/^(short|bear|put|hike)/.test(d)||d.includes('short')};window.isShort=isShort;
// One scored call per source link: earliest row wins
const dupOfLink=c=>{if(!c.post_url||typeof LEDGER==='undefined'||!LEDGER)return null;const f=LEDGER.calls.filter(o=>o.post_url===c.post_url).sort((a,b)=>String(a.logged_at_lisbon).localeCompare(String(b.logged_at_lisbon))||(+a.id)-(+b.id))[0];return f&&f!==c?f:null};
const normEntry=e=>String(e||'').replace(/\s+/g,'').toLowerCase();
function spamWhy(c){const n=c.notes||'',why=SPAM_RULES.filter(([re])=>re.test(n)).map(r=>r[1]);
 const m=n.match(/\b(\d+) followers\b/i);if(m&&+m[1]<50)why.push(`only ${m[1]} followers`);
 if(/^(filtered|excluded)$/.test(c.status||''))why.push('excluded by rule ('+c.status+')');
 if(c.after_the_fact)why.push('after the fact');
 if(c.copy_of)why.push(`copy of #${c.copy_of}`);
 if(c.spam_farm||(typeof LEDGER!=='undefined'&&LEDGER&&(LEDGER.spam_farm_accounts||[]).includes(c.account)))why.push('spam-farm account (copy-paste cluster)');
 // identical asset+direction+entry already posted by a different account earlier in the ledger
 const e=normEntry(c.entry);if(e&&typeof LEDGER!=='undefined'&&LEDGER){const first=LEDGER.calls.find(o=>o.asset===c.asset&&isShort(o.direction)===isShort(c.direction)&&normEntry(o.entry)===e);if(first&&first.account!==c.account&&first!==c)why.push(`duplicate of ${first.account}`)}
 return[...new Set(why)]}
const _spamCache=new WeakMap();
const isSpam=c=>{if(!_spamCache.has(c))_spamCache.set(c,spamWhy(c).length>0);return _spamCache.get(c)};
const isEarlySignal=c=>/early[- ]signal/i.test(c.notes||'');
// Calls that count toward win rates / leaderboard: not spam, not early-signal rows
const countsForRecord=c=>!isSpam(c)&&!isEarlySignal(c)&&!dupOfLink(c);
function srcOf(c){const n=(c.notes||'').toLowerCase();return/early[- ]signal|\bsec\b|filing|13f|form 4/.test(n)?['Early signal','filing']:/source following|watchlist/.test(n)?['Following','watchlist']:/source discovery/.test(n)?['X search','x']:null}
function srcHTML(c){const s=srcOf(c);return s?`<span class="src ${s[1]}">${s[0]}</span>`:''}
const MIN_CLOSED=10;
function recordOf(acc){const r=(typeof LEDGER!=='undefined'&&LEDGER?LEDGER.calls:[]).filter(c=>c.account===acc&&countsForRecord(c)&&(c.locked_pct!=null||['hit_target','stopped'].includes(c.status)&&(typeof callRes!=='function'||callRes(c).p!=null)));const w=r.filter(c=>c.locked_pct!=null?c.locked_pct>0:c.status==='hit_target').length;return{n:r.length,w,rate:r.length>=MIN_CLOSED?w/r.length:null}}
function winrateHTML(acc){const r=recordOf(acc);return r.rate==null?`<span class="winrate" title="${r.n}/${MIN_CLOSED} closed calls before a win rate is shown">Win rate <b>new</b> · ${r.n}/${MIN_CLOSED} closed</span>`:`<span class="winrate" title="${r.w} of ${r.n} closed calls hit target">Win rate <b>${Math.round(r.rate*100)}%</b></span>`}
const FEED=()=>localStorage.getItem('ec-feed')||'all';
function feedOf(c){if(c.feed)return c.feed;return /source following/i.test(c.notes||'')?'following':'discovery'}
