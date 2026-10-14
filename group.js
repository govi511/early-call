// ===== GG BOT: group feed by trader — 3 newest per account, then "+N more from @x" =====
(function(){
 const MAX=3,open=new Set();
 function group(){const f=document.getElementById('feed');if(!f)return;const cards=[...f.querySelectorAll(':scope>.card')];const cnt={},last={};
  f.querySelectorAll('.grp-more-btn').forEach(b=>b.remove());
  cards.forEach(c=>{const a=([...c.querySelectorAll(':scope>.row>span.mut')].pop()||{}).textContent||'';const acc=(a.match(/^\s*(@[\w]+)/)||['',''])[1];if(!acc)return;cnt[acc]=(cnt[acc]||0)+1;c.dataset.acc=acc;const hide=cnt[acc]>MAX&&!open.has(acc);c.classList.toggle('grp-hidden',hide);if(cnt[acc]===MAX)last[acc]=c});
  Object.entries(last).forEach(([acc,c])=>{const extra=cnt[acc]-MAX;if(extra<=0)return;const b=document.createElement('button');b.className='grp-more-btn';b.textContent=open.has(acc)?`Show fewer from ${acc}`:`+${extra} more from ${acc}`;b.onclick=()=>{open.has(acc)?open.delete(acc):open.add(acc);group()};c.after(b)})}
 const wrap=()=>{if(typeof renderSignals!=='function'||renderSignals._g)return;const o=renderSignals;window.renderSignals=renderSignals=function(){const r=o.apply(this,arguments);try{group()}catch(e){}return r};renderSignals._g=1;group()};
 wrap();setTimeout(wrap,500);
})();
