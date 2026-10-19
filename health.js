// ===== GG BOT: data health on the Live dot (green / amber / red + tap for details) =====
(function(){
 const NOPX=/^(OIL|S&P|SPX|ALT|ALTS|MARKET|CRYPTO)\b|\//i;
 let failed=[];const UNCOVERED=new Set(['BULL','HMM','STONK']);// no price source exists; don't keep the dot amber forever
 const sheet=document.createElement('div');sheet.className='hsheet';sheet.innerHTML='<div class="hs-card"><div class="hs-head"><b>Data health</b><button class="hs-x" aria-label="Close">✕</button></div><div class="hs-body"></div></div>';
 document.body.appendChild(sheet);
 sheet.onclick=e=>{if(e.target===sheet||e.target.classList.contains('hs-x'))sheet.classList.remove('on')};
 function missing(){if(!LEDGER)return[];const s=new Set();LEDGER.calls.forEach(c=>{if(c.status!=='open'||!c.asset||NOPX.test(c.asset)||(typeof NP==='function'&&NP(c))||UNCOVERED.has(String(c.asset).toUpperCase()))return;const p=PRICES[c.asset];if(!p||p.price==null)s.add(c.asset)});return[...s].sort()}
 function age(){return PRICES._at?Math.max(0,Math.round((Date.now()-new Date(PRICES._at))/60000)):null}
 function apply(){const ind=document.querySelector('.live');if(!ind)return;const m=age(),miss=missing();
  const lvl=m==null||m>60?'red':(m>20||miss.length)?'amber':'green';
  ind.dataset.h=lvl;const dot=ind.querySelector('.live-dot');dot.style.background=lvl==='green'?'':lvl==='amber'?'#f5b73b':'#f87171';
  const t=ind.querySelector('.live-text');let base=t.textContent.split(' · ').slice(0,2).join(' · ');
  if(lvl==='red'&&m!=null)base='Stale · updated '+(m>=120?Math.round(m/60)+'h':m+'m')+' ago';if(m!=null&&m>=360)base='Paused · no update for '+(m>=2880?Math.round(m/1440)+'d':Math.round(m/60)+'h')+' · bot usage may be out';
  t.textContent=base+(miss.length?` · ${miss.length} no price`:'');
  ind.setAttribute('role','button');ind.tabIndex=0;ind.onclick=open;
  ind._miss=miss;ind._m=m}
 function open(){const ind=document.querySelector('.live'),miss=ind._miss||[],m=ind._m;
  const srcs={};Object.entries(PRICES).forEach(([k,v])=>{if(k[0]==='_'||!v||!v.source)return;const s=v.source.replace(/ \(.*\)/,'');const a=v.as_of?new Date(v.as_of):null;if(!srcs[s]||a>srcs[s])srcs[s]=a});
  const fmt=d=>d?d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Lisbon'})+' PT':'—';
  sheet.querySelector('.hs-body').innerHTML=`<div class="hs-row"><span>Last price refresh</span><b>${m==null?'never':m<1?'just now':m+'m ago'}</b></div>`+
   `<div class="hs-sec">Open calls with no price (${miss.length})</div>`+(miss.length?`<div class="hs-chips">${miss.map(a=>`<span>${esc(a)}</span>`).join('')}</div>`:'<div class="mut">All open calls have a live price.</div>')+
   `<div class="hs-sec">Sources, last worked</div>`+Object.entries(srcs).sort().map(([s,a])=>`<div class="hs-row"><span>${esc(s)}</span><b>${fmt(a)}</b></div>`).join('');
  sheet.classList.add('on')}
 setTimeout(apply,1800);setInterval(apply,15000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(apply,2500)});
})();
