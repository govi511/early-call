// Live crypto prices in the browser: Binance every 30s (Kraken for XMR / fallback), overlaid on prices.json
(function(){
 const LIVE={};let liveAt=null,timer=null;const KR={XMR:'XMRUSD'};
 const isCrypto=a=>{const s=String((PRICES[a]||{}).source||'');return /^(Binance|Kraken)/.test(s)||a in KR};
 const refOf=a=>{if(!LEDGER)return null;for(const c of LEDGER.calls){if(c.asset!==a)continue;const e=lvl(c.entry);if(e)return e;if(c.baseline)return c.baseline}return null};
 const sane=(a,p)=>{const r=refOf(a);return !r||(p<=r*3&&p>=r/3)};
 window.applyLive=()=>{for(const[a,p]of Object.entries(LIVE)){if(!PRICES[a]||!isCrypto(a))continue;PRICES[a]={...PRICES[a],price:p.price,source:p.src+' live',stale:false}}};
 const el=document.createElement('span');el.className='mut';el.id='livepx';el.style.marginLeft='6px';
 window.livePxLabel=()=>{const pu=$('#pupd');if(pu&&!el.isConnected)pu.after(el);el.textContent=liveAt?'· crypto updated '+Math.round((Date.now()-liveAt)/1000)+'s ago':''};
 async function tick(){if(document.hidden||!LEDGER)return;const assets=Object.keys(PRICES).filter(a=>a[0]!=='_'&&isCrypto(a));if(!assets.length)return;let got=0;
  try{const r=await fetch('https://api.binance.com/api/v3/ticker/price');if(r.ok){const m=new Map((await r.json()).map(x=>[x.symbol,+x.price]));
   assets.forEach(a=>{if(a in KR)return;const p=m.get(a+'USDT');if(p&&sane(a,p)){LIVE[a]={price:p,src:'Binance'};got++}})}}catch(e){}
  for(const a of assets.filter(a=>!a.includes('/')&&(a in KR||!LIVE[a]))){const pair=KR[a]||a+'USD';try{const r=await fetch('https://api.kraken.com/0/public/Ticker?pair='+pair);const j=await r.json();const t=j.result&&Object.values(j.result)[0];const p=t&&+t.c[0];if(p&&sane(a,p)){LIVE[a]={price:p,src:'Kraken'};got++}}catch(e){}}
  if(got){liveAt=Date.now();applyLive();renderSignals();typeof rAl==='function'&&rAl()}}
 const start=()=>{clearInterval(timer);timer=setInterval(tick,30000);tick()};
 document.addEventListener('visibilitychange',()=>{if(document.hidden)clearInterval(timer);else start()});
 setInterval(()=>livePxLabel(),1000);setTimeout(start,1200);
 document.getElementById('seg').addEventListener('click',e=>{const b=e.target.closest('button[data-f]');if(!b)return;localStorage.setItem('ec-feed',b.dataset.f);renderSignals()});
})();
