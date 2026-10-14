// ===== GG BOT: "Best right now" strip — famous, has levels, open, recent (≤48h), not spam =====
(function(){
 const H=48;
 function pick(){if(!LEDGER)return[];const now=Date.now();return LEDGER.calls.filter(c=>{if(c.status!=='open'||feedOf(c)!=='famous'||!c.entry||!(c.stop||c.target))return false;if(typeof isSpam==='function'&&isSpam(c))return false;const t=Date.parse(String(c.logged_at_lisbon).replace(' ','T'));return t&&now-t<H*36e5}).sort((a,b)=>String(b.logged_at_lisbon).localeCompare(String(a.logged_at_lisbon))).slice(0,3)}
 function ago(c){const h=(Date.now()-Date.parse(String(c.logged_at_lisbon).replace(' ','T')))/36e5;return h<1?'just now':h<24?Math.floor(h)+'h old':Math.floor(h/24)+'d old'}
 function render(){const f=document.getElementById('feed');if(!f)return;let el=document.getElementById('best');const L=pick();
  if(!L.length){el&&el.remove();return}
  if(!el){el=document.createElement('div');el.id='best';const sum=document.getElementById('sum');(sum||f).before(el)}
  el.innerHTML='<div class="best-h">Best right now</div><div class="best-row">'+L.map(c=>{const l=live(c);const mv=l&&l.move!=null?`<span class="${cls(l.move)}">${pct(l.move)}</span>`:'';return`<a class="best-card" href="#" data-id="${esc(c.id)}"><div class="best-top"><b>${esc(c.asset)}</b> <span class="badge ${isShort(c.direction)?'short':'long'}">${esc(c.direction)}</span></div><div class="best-mv">${mv}</div><div class="best-why">Has levels · ${ago(c)} · ${esc(c.account)}</div></a>`}).join('')+'</div>';
  el.querySelectorAll('.best-card').forEach(a=>a.onclick=e=>{e.preventDefault();const card=document.querySelector(`#feed .card[data-id="${a.dataset.id}"]`);if(card){card.classList.remove('grp-hidden');card.scrollIntoView({behavior:'smooth',block:'center'});card.classList.add('best-flash');setTimeout(()=>card.classList.remove('best-flash'),1500)}})}
 const wrap=()=>{if(typeof renderSignals!=='function'||renderSignals._b)return;const o=renderSignals;window.renderSignals=renderSignals=function(){const r=o.apply(this,arguments);try{render()}catch(e){}return r};renderSignals._b=1;renderSignals._g=o._g;render()};
 wrap();setTimeout(wrap,600);
})();
