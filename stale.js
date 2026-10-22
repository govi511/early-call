// ===== GG BOT: per-card stale price label (price older than 60 min) =====
(()=>{const ago=m=>m>=1440?Math.round(m/1440)+'d':m>=60?Math.round(m/60)+'h':m+'m';
 const mark=()=>{if(typeof LEDGER==='undefined'||!LEDGER||typeof PRICES==='undefined')return;
  document.querySelectorAll('#feed .card[data-id]').forEach(el=>{const c=LEDGER.calls.find(x=>String(x.id)===el.dataset.id);if(!c)return;const p=PRICES[c.asset];if(!p||p.nonpriceable||!p.as_of||p.price==null)return;
   const m=Math.round((Date.now()-new Date(p.as_of))/60000);el.classList.toggle('pxold',m>60);let t=el.querySelector('.pxold-tag');
   if(m>60){if(!t){t=document.createElement('div');t.className='pxold-tag';el.prepend(t)}t.textContent='Price from '+ago(m)+' ago'}else t&&t.remove()})};
 const wrap=()=>{if(typeof renderSignals!=='function'||renderSignals._st)return;const o=renderSignals;window.renderSignals=renderSignals=function(){const r=o.apply(this,arguments);try{mark()}catch(e){}return r};renderSignals._st=1;mark()};
 document.readyState==='loading'?addEventListener('DOMContentLoaded',wrap):wrap();setInterval(mark,60000)})();
