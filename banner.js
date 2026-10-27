// v47: one-line "data behind" banner above #feed. Reuses health.js (body.stale = prices >60m red) plus PRICES._at / LEDGER.generated_at age >45m.
(()=>{const LIM=45,age=t=>t?Math.round((Date.now()-new Date(t))/60000):null;
 const run=()=>{const f=document.getElementById('feed');if(!f)return;let b=document.querySelector('.stale-banner');
  if(!b){b=document.createElement('div');b.className='stale-banner';b.setAttribute('role','status');f.parentNode.insertBefore(b,f)}
  const P=typeof PRICES!=='undefined'&&PRICES||{},L=typeof LEDGER!=='undefined'&&LEDGER||{};
  const pm=age(L.pricesUpdatedAt||P.pricesUpdatedAt||P._pricesUpdatedAt||P._at),lm=age(L.ledgerUpdatedAt||P.ledgerUpdatedAt||L.generated_at);
  const m=Math.max(pm||0,lm||0),on=document.body.classList.contains('stale')||m>LIM;
  b.classList.toggle('on',on);if(on)b.textContent='Data is '+(m>=120?Math.round(m/60)+'h':m+' min')+' behind — refreshing soon'};
 setTimeout(run,2000);setInterval(run,30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(run,2600)})})();
