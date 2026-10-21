// ===== Task 5 UX: news toggle, auto-expiry, grouped consensus cards =====
(function(){
 const nb=document.getElementById('newsbtn');
 if(nb)nb.onclick=e=>{e.preventDefault();localStorage.setItem('ec-shownews',localStorage.getItem('ec-shownews')==='1'?'0':'1');renderSignals()};
 // --- auto-expiry: open calls with no hit close as "expired" after 72h (crypto) or at the end of their stated timeframe ---
 const CRYPTO_SRC=/okx|binance|kraken|gate|coingecko/i;
 const tsOf=c=>Date.parse(String(c.logged_at_lisbon||'').replace(' ','T'));
 function deadline(c){const t=tsOf(c);if(!t)return null;const txt=[c.target,c.stop,c.entry,c.notes].join(' ').toLowerCase();
  if(/\b(for today|today only|intraday|today)\b/.test(txt)){const d=new Date(t);d.setHours(23,59,0,0);return+d}
  let m=txt.match(/\b(?:within|next|in)\s+(\d{1,3})\s*(h|hrs?|hours?|d|days?|w|weeks?)\b/);
  if(m){const n=+m[1],u=m[2][0];return t+n*(u==='h'?36e5:u==='d'?864e5:6048e5)}
  if(/\bthis week\b/.test(txt))return t+6048e5;
  const crypto=CRYPTO_SRC.test((PRICES[c.asset]||{}).source||'');
  return crypto?t+72*36e5:null}
 function expire(){if(!LEDGER)return;const now=Date.now();
  LEDGER.calls.forEach(c=>{if(c.status!=='open'||c.locked_pct!=null||c._expChecked===now)return;const d=deadline(c);
   if(d&&now>d){c.status='expired';c.auto_expired=true;c.resolved_at=c.resolved_at||new Date(d).toISOString().slice(0,10)}})}
 window.autoExpireDeadline=deadline;
 // --- grouped consensus: several accounts, same asset + direction, within 24h ---
 const open=new Set();
 function consensus(){const f=document.getElementById('feed');if(!f||!LEDGER)return;f.querySelectorAll('.cons-card').forEach(x=>x.remove());f.querySelectorAll('.cons-hidden').forEach(x=>x.classList.remove('cons-hidden'));
  const cs=LEDGER.calls.filter(c=>c.status==='open'&&countsForRecord(c)&&tsOf(c)).sort((a,b)=>tsOf(a)-tsOf(b)),used=new Set(),groups=[];
  cs.forEach(a=>{if(used.has(a))return;const g=cs.filter(b=>!used.has(b)&&b.asset.toUpperCase()===a.asset.toUpperCase()&&isShort(b.direction)===isShort(a.direction)&&tsOf(b)-tsOf(a)>=0&&tsOf(b)-tsOf(a)<=864e5);
   if(new Set(g.map(x=>x.account)).size>=2){g.forEach(x=>used.add(x));groups.push(g)}});
  groups.reverse().forEach(g=>{const key=g.map(x=>x.id).join(','),cards=g.map(x=>f.querySelector(`:scope>.card[data-id="${CSS.escape(String(x.id))}"]`)).filter(Boolean);if(cards.length<2)return;
   const accs=[...new Set(g.map(x=>x.account))],sh=isShort(g[0].direction);
   const el=document.createElement('div');el.className='card cons-card';
   el.innerHTML=`<div class="row"><div><span class="badge ${sh?'short':'long'}">${sh?'short':'long'}</span> <b>${esc(g[0].asset)}</b> <span class="mut">consensus</span></div><span class="mut">${accs.length} accounts · 24h</span></div><div class="cons-list">${g.map(x=>`<span>${esc(x.account)} <small class="mut">${esc(String(x.logged_at_lisbon).slice(5,16))}</small></span>`).join('')}</div><button class="btn g cons-tg">${open.has(key)?'Hide calls':'Show '+cards.length+' calls'}</button>`;
   el.querySelector('.cons-tg').onclick=()=>{open.has(key)?open.delete(key):open.add(key);consensus()};
   cards[0].before(el);if(!open.has(key))cards.forEach(c=>c.classList.add('cons-hidden'))})}
 const wrap=()=>{if(typeof renderSignals!=='function'||renderSignals._u5)return;const o=renderSignals;window.renderSignals=renderSignals=function(){expire();const r=o.apply(this,arguments);try{consensus()}catch(e){console.warn(e)}return r};renderSignals._u5=1;try{renderSignals()}catch(e){}};
 wrap();setTimeout(wrap,700);
})();
