// ===== GG BOT: trader record chip (hits–stops) next to the account on each card =====
(()=>{const mark=()=>{if(typeof LEDGER==='undefined'||!LEDGER)return;const R={};LEDGER.calls.forEach(c=>{if(typeof isSpam==='function'&&isSpam(c))return;const a='@'+String(c.account||'').replace(/^@/,'');const r=R[a]||(R[a]={w:0,l:0});if(c.status==='hit_target')r.w++;else if(c.status==='stopped')r.l++});
 document.querySelectorAll('#feed .card[data-id]').forEach(el=>{const sp=[...el.querySelectorAll(':scope>.row>span.mut')].pop();if(!sp||sp.querySelector('.rec'))return;const m=(sp.textContent||'').match(/^\s*(@\w+)/);if(!m)return;const r=R[m[1]];if(!r||r.w+r.l===0)return;
  const b=document.createElement('span');b.className='rec '+(r.w>r.l?'up':r.w<r.l?'dn':'');b.title=r.w+' targets hit, '+r.l+' stopped';b.textContent=r.w+'–'+r.l;sp.before(b)})};
 const wrap=()=>{if(typeof renderSignals!=='function'||renderSignals._rc)return;const o=renderSignals;window.renderSignals=renderSignals=function(){const r=o.apply(this,arguments);try{mark()}catch(e){}return r};renderSignals._rc=1;mark()};
 document.readyState==='loading'?addEventListener('DOMContentLoaded',wrap):wrap()})();
