// ===== Quality filter (see FILTER_RULES.md) — loaded before app.js renders =====
const SPAM_RULES=[[/telegram/i,'Telegram promo'],[/\bvip\b/i,'VIP promo'],[/referral|ref link/i,'referral link'],[/affiliate/i,'affiliate link'],[/low[- ]follower/i,'low-follower account'],[/thin account|bot account/i,'thin/bot account'],[/cop(y|ied)/i,'copied post'],[/duplicate/i,'duplicate'],[/after[ _-]the[ _-]fact/i,'after the fact'],[/\bstale\b/i,'stale']];
const normEntry=e=>String(e||'').replace(/\s+/g,'').toLowerCase();
function spamWhy(c){const n=c.notes||'',why=SPAM_RULES.filter(([re])=>re.test(n)).map(r=>r[1]);
 const m=n.match(/\b(\d+) followers\b/i);if(m&&+m[1]<50)why.push(`only ${m[1]} followers`);
 if(c.after_the_fact)why.push('after the fact');
 // identical asset+direction+entry already posted by a different account earlier in the ledger
 const e=normEntry(c.entry);if(e&&typeof LEDGER!=='undefined'&&LEDGER){const first=LEDGER.calls.find(o=>o.asset===c.asset&&o.direction===c.direction&&normEntry(o.entry)===e);if(first&&first.account!==c.account&&first!==c)why.push(`duplicate of ${first.account}`)}
 return[...new Set(why)]}
const isSpam=c=>spamWhy(c).length>0;
function srcOf(c){const n=(c.notes||'').toLowerCase();return/early[- ]signal/.test(n)?'Early signal':/source following/.test(n)?'Following':/source discovery/.test(n)?'X search':'—'}
function winrateOf(acc){if(typeof LEDGER==='undefined'||!LEDGER)return'';const r=LEDGER.calls.filter(c=>c.account===acc&&['hit_target','stopped'].includes(c.status));return r.length?`${r.filter(c=>c.status==='hit_target').length}/${r.length} wins`:'no resolved calls'}
