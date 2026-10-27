// v49: one-line "prices old" banner above #feed. Keys ONLY on the prices timestamp (pricesUpdatedAt, fallback PRICES._at) >75m, or body.stale from health.js. Ledger time deliberately ignored (goes quiet in off-hours).
(()=>{const LIM=75,age=t=>t?Math.round((Date.now()-new Date(t))/60000):null;
 const run=()=>{const f=document.getElementById('feed');if(!f)return;let b=document.querySelector('.stale-banner');
  if(!b){b=document.createElement('div');b.className='stale-banner';b.setAttribute('role','status');f.parentNode.insertBefore(b,f)}
  const P=typeof PRICES!=='undefined'&&PRICES||{},L=typeof LEDGER!=='undefined'&&LEDGER||{};
  const m=age(L.pricesUpdatedAt||P.pricesUpdatedAt||P._pricesUpdatedAt||P._at),on=document.body.classList.contains('stale')||(m!=null&&m>LIM);
  b.classList.toggle('on',on);if(on)b.textContent=m==null?'Prices are out of date — refreshing soon':'Prices are '+(m>=120?Math.round(m/60)+'h':m+' min')+' old — refreshing soon'};
 setTimeout(run,2000);setInterval(run,30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(run,2600)})})();
