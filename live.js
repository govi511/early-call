// ===== Live automation: polling (60s), NEW badges, live indicator =====
(function(){
 // minimal functional CSS only (animations); visual styling belongs to style.css
 const st=document.createElement('style');st.textContent='@keyframes ec-pulse{0%,100%{opacity:1}50%{opacity:.25}}.live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#21c37a;margin-right:6px;animation:ec-pulse 1.6s ease-in-out infinite}';
 document.head.prepend(st);
 // NEW badges: ids seen before this page load
 const SEEN_KEY='ec-seen-ids';let seen0=null;try{seen0=JSON.parse(localStorage.getItem(SEEN_KEY))}catch(e){}
 window.isNew=c=>seen0!==null&&!seen0.includes(String(c.id));
 const saveSeen=()=>{if(LEDGER)localStorage.setItem(SEEN_KEY,JSON.stringify(LEDGER.calls.map(c=>String(c.id))))};
 // first visit ever: everything counts as seen (no flood of NEW)
 // live indicator replaces manual refresh button
 const rp=$('#rp');if(rp)rp.style.display='none';
 const ind=document.createElement('span');ind.className='live';ind.innerHTML='<span class="live-dot"></span><span class="live-text">Live</span>';
 (rp?rp.parentNode:$('#signals')).appendChild(ind);
 let lastOk=Date.now();
 function tickLabel(){const at=PRICES._at?new Date(PRICES._at):null;const m=at?Math.max(0,Math.round((Date.now()-at)/60000)):null;
  const fresh=!!(lastOk&&Date.now()-lastOk<150000&&m!=null&&m<=20);
  ind.querySelector('.live-text').textContent=m==null?'Delayed · waiting for data':`${fresh?'Live':'Delayed'} · updated ${m<1?'just now':m+'m ago'}`;
  ind.querySelector('.live-dot').style.background=fresh?'':'#f5b73b';ind.classList.toggle('stale',!fresh)}
 async function poll(){try{await loadLedger();await loadPrices();lastOk=Date.now()}catch(e){}tickLabel();saveSeen()}
 // first poll: if no stored ids yet, mark everything seen before rendering
 if(seen0===null){window.isNew=()=>false}
 setTimeout(()=>{tickLabel();if(seen0===null){saveSeen();seen0=LEDGER?LEDGER.calls.map(c=>String(c.id)):[];window.isNew=c=>!seen0.includes(String(c.id))}},1500);
 setInterval(poll,60000);setInterval(tickLabel,15000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll()});
})();
