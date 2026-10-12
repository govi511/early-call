const $=s=>document.querySelector(s),eur=v=>'€'+v.toLocaleString('pt-PT',{minimumFractionDigits:2,maximumFractionDigits:2});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#nav button,section').forEach(e=>e.classList.remove('on'));b.classList.add('on');$('#'+b.dataset.t).classList.add('on')});
// Signals + leaderboard + live prices
let LEDGER=null,PRICES={};
const nums=s=>(String(s).match(/\d+(?:\.\d+)?/g)||[]).map(Number);
const lvl=s=>{const n=nums(String(s).replace(/\(.*?\)/g,''));return n.length?(n.length>1?(n[0]+n[1])/2:n[0]):null};
const pct=v=>v==null||!isFinite(v)?'n/a':(v>0?'+':'')+v.toFixed(2)+'%';
const cls=v=>v==null?'':v>=0?'up':'dn';
function live(c){const p=PRICES[c.asset]?.price,e=lvl(c.entry),s=lvl(c.stop),t=lvl(c.target),d=c.direction==='short'?-1:1;
 if(p==null||e==null)return{p:null};return{p,move:d*(p-e)/e*100,toStop:s==null?null:d*(p-s)/p*100,toTgt:t==null?null:d*(t-p)/p*100,prog:(s==null||t==null||t===s)?null:Math.max(0,Math.min(1,(p-s)/(t-s)))}}
const SIMPLE=()=>localStorage.getItem('ec-simple')==='1';
function renderSignals(){if(!LEDGER)return;const simple=SIMPLE();$('#simple').checked=simple;$('#sum').style.display=simple?'none':'';const sc=c=>typeof earlyScore==='function'?earlyScore(c,live(c)).s:0;const calls=[...LEDGER.calls].reverse().filter(c=>!simple||c.status==='open').map((c,i)=>({c,i,o:c.status==='open'?0:1,s:sc(c)})).sort((a,b)=>a.o-b.o||(a.o===0?b.s-a.s:a.i-b.i)).map(x=>x.c);
 const open=calls.filter(c=>c.status==='open').map(c=>({c,l:live(c)})),ok=open.filter(o=>o.l.p!=null);
 const avg=ok.length?ok.reduce((s,o)=>s+o.l.move,0)/ok.length:null,sorted=[...ok].sort((a,b)=>b.l.move-a.l.move);
 const bw=o=>o?`${esc(o.c.asset)} <span class="${cls(o.l.move)}">${pct(o.l.move)}</span>`:'n/a';
 $('#sum').innerHTML=`<div><small>Open calls</small><b>${open.length}</b></div><div><small>Average change (open calls)</small><b class="${cls(avg)}">${pct(avg)}</b></div><div><small>Doing best</small><b>${bw(sorted[0])}</b></div><div><small>Doing worst</small><b>${bw(sorted[sorted.length-1])}</b></div>`;
 $('#pupd').textContent=PRICES._at?'Prices '+PRICES._at.replace('T',' ').slice(0,16)+' PT':'Prices n/a';
 $('#feed').innerHTML=calls.map(c=>{const l=live(c),pi=PRICES[c.asset]||{};return`<div class="card" data-id="${esc(c.id)}"><div class="row"><div><span class="asset">${esc(c.asset)}</span>${isNew(c)?' <span class="new-badge">NEW</span>':''} <span class="badge ${c.direction==='short'?'short':'long'}">${esc(c.direction)}</span></div><b class="st-${esc(c.status)}">● ${esc(c.status.replace('_',' '))}</b></div>
 <div class="headline">${esc(c.asset)} ${l.p==null?'n/a':`<span class="${cls(l.move)}">${pct(l.move)}</span>`} · ${esc(c.status.replace('_',' '))}</div>
 <div class="spark" data-asset="${esc(c.asset)}" data-id="${esc(c.id)}"></div>
 <div class="row" style="margin-top:6px"><div><small class="mut">Price now</small> <b style="font-size:17px">${l.p==null?'n/a':l.p.toLocaleString('en-US',{maximumFractionDigits:4})}</b> <span class="${cls(l.move)}" style="font-weight:700">${l.p==null?'':pct(l.move)+' since buy price'}</span></div><span class="tag" title="${esc(pi.symbol||'')}">${esc(pi.source||'no price')}</span></div>
 ${simple?'':earlyHTML(c,l)}<div class="lv"><div><small>Bought at</small>${esc(c.entry)}</div><div><small>Exit if loss</small>${esc(c.stop)}</div><div><small>Take profit at</small>${esc(c.target)}</div></div>
 <div class="bar">${l.prog==null?'':`<i style="left:${(l.prog*100).toFixed(1)}%"></i>`}</div><div class="row mut" style="margin:4px 0 8px"><span>Loss if stopped: ${l.p==null?'n/a':pct(l.toStop)} away</span><span>Gain to target: ${l.p==null?'n/a':pct(l.toTgt)}</span></div>
 ${c.notes?`<div class="mut">📝 ${esc(c.notes)}</div>`:''}<div class="row" style="margin-top:8px"><span class="mut">${esc(c.account)} · ${esc(c.logged_at_lisbon)} PT${c.resolved_at?' · resolved '+esc(c.resolved_at):''}</span><span><span class="tag">${esc(c.source)}</span>${c.after_the_fact?' <span class="tag" style="color:var(--warn)">after-the-fact</span>':''} <a href="${esc(c.post_url)}" target="_blank" rel="noopener">Post ↗</a></span></div></div>`}).join('')||'<p class="mut">No calls yet.</p>'}
function loadPrices(){return fetch('data/prices.json?t='+Date.now()).then(r=>r.json()).then(d=>{PRICES=d.prices||{};PRICES._at=d.fetched_at}).catch(()=>{PRICES={}}).then(renderSignals)}

$('#simple').onchange=e=>{localStorage.setItem('ec-simple',e.target.checked?'1':'0');renderSignals()};
function loadLedger(){return fetch('data/ledger.json?t='+Date.now()).then(r=>r.json()).then(d=>{LEDGER=d;
 $('#gen').textContent='Ledger '+d.generated_at.replace('T',' ').slice(0,16);loadPrices();
 const acc={};d.calls.forEach(c=>{const a=acc[c.account]??={hit:0,stop:0,other:0,atf:0};c.status==='hit_target'?a.hit++:c.status==='stopped'?a.stop++:a.other++;if(c.after_the_fact)a.atf++});
 $('#lb').innerHTML=Object.entries(acc).sort((x,y)=>(y[1].hit/(y[1].hit+y[1].stop||1))-(x[1].hit/(x[1].hit+x[1].stop||1))).map(([n,a])=>{const r=a.hit+a.stop;return`<tr><td><b>${esc(n)}</b>${r<5?' <span class="badge" style="background:rgba(245,183,59,.15);color:var(--warn)">small sample</span>':''}</td><td><b>${r?Math.round(a.hit/r*100)+'%':'—'}</b> <span class="mut">(${r} resolved)</span></td><td class="up">${a.hit}</td><td class="dn">${a.stop}</td><td>${a.other}</td><td>${a.atf}</td></tr>`}).join('');
})}
loadLedger().catch(e=>$('#feed').innerHTML='<p class="mut">Could not load data/ledger.json — run refresh.py and serve over http.</p>');
// Portfolio
const H=[['SpaceX',389.02,'#2f9bff'],['Tesla',244.00,'#ff4d5e'],['Cyber segurança pie',107.06,'#21c37a'],['Pelosi pie',96.70,'#a66bff'],['Bancos tugas pie',49.14,'#f5b73b'],['iShares NASDAQ 100',29.63,'#20c5d6'],['iShares S&P 500 IT',29.36,'#ff8a3d']];
const tot=H.reduce((s,h)=>s+h[1],0),musk=(389.02+244)/tot*100;
$('#ptotal').textContent=eur(tot);
$('#pwarn').innerHTML=`<div class="warn">⚠️ Concentration: SpaceX + Tesla (Musk-linked) = <b>${musk.toFixed(0)}%</b> of the portfolio. A single bad headline hits two-thirds of your money.</div>`;
$('#ptab').innerHTML=H.map(h=>`<tr><td><span style="color:${h[2]}">●</span> ${h[0]}</td><td>${eur(h[1])}</td><td class="mut">${(h[1]/tot*100).toFixed(1)}%</td></tr>`).join('');
const C=window.Chart;Chart&&(Chart.defaults.color='#8a96a6');
C&&new Chart($('#donut'),{type:'doughnut',data:{labels:H.map(h=>h[0]),datasets:[{data:H.map(h=>h[1]),backgroundColor:H.map(h=>h[2]),borderWidth:0}]},options:{cutout:'68%',maintainAspectRatio:false,plugins:{legend:{display:false}}}});
$('#pj-s').value=tot.toFixed(0);let pjc;
function proj(){const s=+$('#pj-s').value||0,m=+$('#pj-m').value||0,y=+$('#pj-y').value,n=y*12;const sc=[[-25,'#ff4d5e'],[8,'#2f9bff'],[25,'#21c37a']];
 const series=sc.map(([r])=>{const mr=Math.pow(1+r/100,1/12)-1;let v=s,a=[v];for(let i=0;i<n;i++){v=v*(1+mr)+m;a.push(v)}return a});
 $('#pj-out').innerHTML=sc.map(([r],i)=>`<tr><td class="${r<0?'dn':'up'}">${r>0?'+':''}${r}%/yr</td><td>${eur(s+m*n)}</td><td><b>${eur(series[i][n])}</b></td></tr>`).join('');
 if(!C)return;pjc&&pjc.destroy();pjc=new Chart($('#pjc'),{type:'line',data:{labels:[...Array(n+1).keys()].map(i=>'M'+i),datasets:sc.map(([r,c],i)=>({label:(r>0?'+':'')+r+'%',data:series[i],borderColor:c,pointRadius:0,tension:.2}))},options:{maintainAspectRatio:false,scales:{x:{grid:{color:'#1c232d'}},y:{grid:{color:'#1c232d'}}}}})}
['#pj-s','#pj-m','#pj-y'].forEach(i=>$(i).oninput=proj);proj();
// Monthly plan
(()=>{const plan=[['SpaceX',200],['Tesla',80],['S&P 500 index',120]];
 const target={'SpaceX':50,'Tesla':22.5,'S&P 500 index':17.5,'Other (pies + ETFs)':10};
 const cur={'SpaceX':389.02,'Tesla':244,'S&P 500 index':0,'Other (pies + ETFs)':107.06+96.70+49.14+29.63+29.36};
 const after={...cur};plan.forEach(([k,v])=>after[k]+=v*12);const ta=Object.values(after).reduce((a,b)=>a+b,0);
 $('#plan').innerHTML=`<h2>Monthly plan · €400/mo</h2><div class="lv">${plan.map(([k,v])=>`<div><small>${k}</small>${eur(v)}</div>`).join('')}</div>
 <p class="mut">Target: ~70–75% SpaceX + Tesla (high-conviction), rest diversified. Note: the iShares S&P 500 IT ETF you hold is tech-only, not a broad S&P 500 index.</p>
 <table><thead><tr><th>Bucket</th><th>Current</th><th>After 12 mo*</th><th>Target</th></tr></thead><tbody>${Object.keys(target).map(k=>`<tr><td>${k}</td><td>${(cur[k]/tot*100).toFixed(1)}%</td><td>${(after[k]/ta*100).toFixed(1)}%</td><td><b>${target[k]}%</b></td></tr>`).join('')}
 <tr><td><b>SpaceX + Tesla</b></td><td><b>${musk.toFixed(1)}%</b></td><td><b>${((after.SpaceX+after.Tesla)/ta*100).toFixed(1)}%</b></td><td><b>72.5%</b></td></tr></tbody></table>
 <p class="mut">*Deposits only, assuming no price changes.</p>`})();
// Alerts
const ls=(k,v)=>v===undefined?JSON.parse(localStorage.getItem(k)||'[]'):localStorage.setItem(k,JSON.stringify(v));
function rAl(){const a=ls('ec-alerts');$('#al-list').innerHTML=a.map((x,i)=>`<tr><td><b>${esc(x.asset)}</b></td><td class="${x.dir==='above'?'up':'dn'}">${x.dir==='above'?'▲ above':'▼ below'} ${x.level}</td><td class="mut">${esc(x.at)}</td><td><button class="btn g" onclick="delAl(${i})">✕</button></td></tr>`).join('')||'<tr><td class="mut">No alerts yet.</td></tr>'}
window.delAl=i=>{const a=ls('ec-alerts');a.splice(i,1);ls('ec-alerts',a);rAl()};
$('#al-add').onclick=()=>{const asset=$('#al-a').value.trim().toUpperCase(),level=+$('#al-l').value;if(!asset||!level)return;const a=ls('ec-alerts');a.push({asset,level,dir:$('#al-d').value,at:new Date().toLocaleDateString('pt-PT')});ls('ec-alerts',a);$('#al-a').value=$('#al-l').value='';rAl()};rAl();
// Journal
let edit=-1;const pl=t=>t.exit===''||t.exit==null?null:(t.side==='long'?1:-1)*(t.exit-t.entry)/t.entry*t.size;
function rJ(){const j=ls('ec-journal');let tot=0,w=0,c=0;
 $('#j-list').innerHTML=j.map((t,i)=>{const p=pl(t);if(p!=null){tot+=p;c++;if(p>0)w++}return`<tr><td><b>${esc(t.asset)}</b></td><td><span class="badge ${t.side}">${t.side}</span></td><td>${t.entry}</td><td>${t.exit===''?'<span class="mut">open</span>':t.exit}</td><td class="${p>0?'up':p<0?'dn':''}">${p==null?'—':eur(p)}</td><td style="white-space:nowrap"><button class="btn g" onclick="edJ(${i})">✎</button> <button class="btn g" onclick="delJ(${i})">✕</button></td></tr>`}).join('')||'<tr><td class="mut" colspan="6">No practice trades yet.</td></tr>';
 $('#j-pl').textContent=eur(tot);$('#j-pl').className='big '+(tot>=0?'up':'dn');$('#j-wr').textContent=c?Math.round(w/c*100)+'% ('+w+'/'+c+')':'—'}
window.delJ=i=>{const j=ls('ec-journal');j.splice(i,1);ls('ec-journal',j);rJ()};
window.edJ=i=>{const t=ls('ec-journal')[i];edit=i;$('#j-a').value=t.asset;$('#j-s').value=t.side;$('#j-e').value=t.entry;$('#j-x').value=t.exit;$('#j-q').value=t.size;$('#j-add').textContent='Update'};
$('#j-add').onclick=()=>{const t={asset:$('#j-a').value.trim().toUpperCase(),side:$('#j-s').value,entry:+$('#j-e').value,exit:$('#j-x').value===''?'':+$('#j-x').value,size:+$('#j-q').value||0};if(!t.asset||!t.entry)return;const j=ls('ec-journal');edit>=0?j[edit]=t:j.push(t);edit=-1;$('#j-add').textContent='Save';ls('ec-journal',j);['#j-a','#j-e','#j-x'].forEach(s=>$(s).value='');rJ()};rJ();

if(location.hash){const b=document.querySelector(`#nav button[data-t="${location.hash.slice(1)}"]`);b&&b.click()}
if(location.hash==='#plan'){document.querySelector('#nav button[data-t="port"]').click();setTimeout(()=>document.getElementById('plan').scrollIntoView(),300)}
{const t=new URLSearchParams(location.search).get('tab');const b=t&&document.querySelector(`#nav button[data-t="${t}"]`);b&&b.click()}
