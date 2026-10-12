const $=s=>document.querySelector(s),eur=v=>'€'+v.toLocaleString('pt-PT',{minimumFractionDigits:2,maximumFractionDigits:2});
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function showTab(t){if(!document.getElementById(t))return;document.querySelectorAll('main>section').forEach(e=>e.classList.toggle('on',e.id===t));document.querySelectorAll('.tabbar button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));scrollTo(0,0)}
document.querySelectorAll('.tabbar button').forEach(b=>b.onclick=()=>showTab(b.dataset.t));
// Signals + leaderboard + live prices
let LEDGER=null,PRICES={};
const nums=s=>(String(s).match(/\d+(?:\.\d+)?/g)||[]).map(Number);
const lvl=s=>{const n=nums(String(s).replace(/\(.*?\)/g,''));return n.length?(n.length>1?(n[0]+n[1])/2:n[0]):null};
const pct=v=>v==null||!isFinite(v)?'n/a':(v>0?'+':'')+v.toFixed(2)+'%';
const cls=v=>v==null?'':v>=0?'up':'dn';
function live(c){const p=PRICES[c.asset]?.price,e=lvl(c.entry),s=lvl(c.stop),t=lvl(c.target),d=c.direction==='short'?-1:1;
 if(p==null||e==null)return{p:null};return{p,move:d*(p-e)/e*100,toStop:s==null?null:d*(p-s)/p*100,toTgt:t==null?null:d*(t-p)/p*100,prog:(s==null||t==null||t===s)?null:Math.max(0,Math.min(1,(p-s)/(t-s)))}}
const SIMPLE=()=>localStorage.getItem('ec-simple')==='1';
function renderSignals(){if(!LEDGER)return;const simple=SIMPLE();$('#simple').checked=simple;$('#sum').style.display=simple?'none':'';const sc=c=>typeof earlyScore==='function'?earlyScore(c,live(c)).s:0;const showSpam=localStorage.getItem('ec-showspam')==='1',nSpam=LEDGER.calls.filter(isSpam).length;$('#showspam').checked=showSpam;$('#spamlbl').textContent=`Show filtered (${nSpam})`;const calls=[...LEDGER.calls].reverse().filter(c=>(!simple||c.status==='open')&&(showSpam||!isSpam(c))).map((c,i)=>({c,i,o:c.status==='open'?0:1,s:sc(c)})).sort((a,b)=>a.o-b.o||(a.o===0?b.s-a.s:a.i-b.i)).map(x=>x.c);
 const open=calls.filter(c=>c.status==='open'&&!isSpam(c)).map(c=>({c,l:live(c)})),ok=open.filter(o=>o.l.p!=null);
 const avg=ok.length?ok.reduce((s,o)=>s+o.l.move,0)/ok.length:null,sorted=[...ok].sort((a,b)=>b.l.move-a.l.move);
 const bw=o=>o?`${esc(o.c.asset)} <span class="${cls(o.l.move)}">${pct(o.l.move)}</span>`:'n/a';
 $('#sum').innerHTML=`<div><small>Open calls</small><b>${open.length}</b></div><div><small>Average change (open calls)</small><b class="${cls(avg)}">${pct(avg)}</b></div><div><small>Doing best</small><b>${bw(sorted[0])}</b></div><div><small>Doing worst</small><b>${bw(sorted[sorted.length-1])}</b></div>`;
 $('#pupd').textContent=PRICES._at?'Prices '+PRICES._at.replace('T',' ').slice(0,16)+' PT':'Prices n/a';
 $('#feed').innerHTML=calls.map(c=>{const l=live(c),pi=PRICES[c.asset]||{};return`<div class="card${isSpam(c)?' hidden-spam':''}" data-id="${esc(c.id)}"><div class="row"><div><span class="asset">${esc(c.asset)}</span>${isSpam(c)?` <span class="badge" title="${esc(spamWhy(c).join('; '))}" style="background:rgba(255,107,120,.15);color:#ff6b78">filtered</span>`:''} ${srcHTML(c)} ${winrateHTML(c.account)}${isNew(c)?' <span class="new-badge">NEW</span>':''} <span class="badge ${c.direction==='short'?'short':'long'}">${esc(c.direction)}</span></div><b class="st-${esc(c.status)}">● ${esc(c.status.replace('_',' '))}</b></div>
 <div class="headline">${esc(c.asset)} ${l.p==null?'n/a':`<span class="${cls(l.move)}">${pct(l.move)}</span>`} · ${esc(c.status.replace('_',' '))}</div>
 <div class="spark" data-asset="${esc(c.asset)}" data-id="${esc(c.id)}"></div>
 <div class="row" style="margin-top:6px"><div><small class="mut">Price now</small> <b style="font-size:17px">${l.p==null?'n/a':l.p.toLocaleString('en-US',{maximumFractionDigits:4})}</b> <span class="${cls(l.move)}" style="font-weight:700">${l.p==null?'':pct(l.move)+' since buy price'}</span></div><span class="tag" title="${esc(pi.symbol||'')}">${esc(pi.source||'no price')}</span></div>
 ${simple?'':earlyHTML(c,l)}<div class="lv"><div><small>Bought at</small>${esc(c.entry)}</div><div><small>Exit if loss</small>${esc(c.stop)}</div><div><small>Take profit at</small>${esc(c.target)}</div></div>
 <div class="bar">${l.prog==null?'':`<i style="left:${(l.prog*100).toFixed(1)}%"></i>`}</div><div class="row mut" style="margin:4px 0 8px"><span>Loss if stopped: ${l.p==null?'n/a':pct(l.toStop)} away</span><span>Gain to target: ${l.p==null?'n/a':pct(l.toTgt)}</span></div>
 ${c.notes?`<div class="mut">📝 ${esc(c.notes)}</div>`:''}<div class="row" style="margin-top:8px"><span class="mut">${esc(c.account)} · ${esc(c.logged_at_lisbon)} PT${c.resolved_at?' · resolved '+esc(c.resolved_at):''}</span><span><span class="tag">${esc(c.source)}</span>${c.after_the_fact?' <span class="tag" style="color:var(--warn)">after-the-fact</span>':''} <a href="${esc(c.post_url)}" target="_blank" rel="noopener">Post ↗</a></span></div></div>`}).join('')||'<p class="mut">No calls yet.</p>';renderLeader()}
function loadPrices(){return fetch('data/prices.json?t='+Date.now()).then(r=>r.json()).then(d=>{PRICES=d.prices||{};PRICES._at=d.fetched_at}).catch(()=>{PRICES={}}).then(renderSignals)}

$('#showspam').onchange=e=>{localStorage.setItem('ec-showspam',e.target.checked?'1':'0');renderSignals()};
$('#simple').onchange=e=>{localStorage.setItem('ec-simple',e.target.checked?'1':'0');renderSignals()};
function loadLedger(){return fetch('data/ledger.json?t='+Date.now()).then(r=>r.json()).then(d=>{LEDGER=d;
 $('#gen').textContent='Ledger '+d.generated_at.replace('T',' ').slice(0,16);loadPrices();
})}

// Leaderboard (FOMO style, live)
const ST={open:'open',hit_target:'hit',stopped:'stopped',unclear:'expired',expired:'expired'};
function callRes(c){const e=lvl(c.entry),d=c.direction==='short'?-1:1;let x=null;
 if(c.status==='open')x=PRICES[c.asset]?.price??null;else if(c.status==='hit_target')x=lvl(c.target);else if(c.status==='stopped')x=lvl(c.stop);
 return{e,x,p:e&&x!=null?d*(x-e)/e*100:null}}
const fmtP=v=>v==null?'n/a':v.toLocaleString('en-US',{maximumFractionDigits:v<10?4:2});
const LBPREV={};
const avFail=img=>{const s=document.createElement('div');s.className='lb-avatar';s.style.cssText='display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff';s.textContent=img.alt;img.replaceWith(s)};
function renderLeader(){if(!LEDGER||!$('#lb'))return;const by={};LEDGER.calls.filter(c=>!isSpam(c)).forEach(c=>(by[c.account]??=[]).push(c));
 const rows=Object.entries(by).map(([n,cs])=>{const r=recordOf(n),res=cs.map(c=>({c,...callRes(c)})).reverse(),v=res.filter(x=>x.p!=null);return{n,cs:res,r,avg:v.length?v.reduce((s,x)=>s+x.p,0)/v.length:null}});
 const byAvg=(a,b)=>(b.avg??-1e9)-(a.avg??-1e9);
 const ranked=rows.filter(o=>o.r.rate!=null).sort((a,b)=>b.r.rate-a.r.rate||byAvg(a,b)),fresh=rows.filter(o=>o.r.rate==null).sort(byAvg);
 const item=(o,i)=>{const h=o.n.replace(/^@/,''),ini=(h[0]||'?').toUpperCase();return`<div class="lb-row" data-acc="${esc(o.n)}"><div class="lb-rank">${i==null?'–':i+1}</div><img class="lb-avatar" src="https://unavatar.io/x/${encodeURIComponent(h)}" alt="${esc(ini)}" loading="lazy" onerror="avFail(this)"><div class="lb-name"><b>${esc(h)}</b><small>@${esc(h)} · ${o.r.rate!=null?'win rate '+Math.round(o.r.rate*100)+'%':'win rate new ('+o.r.n+'/10 closed)'} · ${o.cs.length} calls</small></div><div class="lb-pnl ${cls(o.avg)}" title="Average % per call">${pct(o.avg)}</div></div>
 <div class="lb-calls">${o.cs.filter(x=>x.p!=null).map(x=>`<span class="lb-call ${cls(x.p)}">${esc(x.c.asset)} ${pct(x.p)}</span>`).join('')||'<span class="mut">No priced calls yet</span>'}</div>
 <details class="lbd"${LBOPEN.has(o.n)?' open':''} data-acc="${esc(o.n)}"><summary>All calls (${o.cs.length})</summary>${o.cs.map(x=>`<div class="lbr"><div><b>${esc(x.c.asset)}</b> <span class="badge ${x.c.direction==='short'?'short':'long'}">${esc(x.c.direction)}</span><div class="mut">Entry ${esc(x.c.entry)} → ${x.c.status==='open'?'now':'exit'} ${fmtP(x.x)}</div></div><div style="text-align:right"><b class="${cls(x.p)}">${pct(x.p)}</b><div class="stp st-${esc(x.c.status)}">${ST[x.c.status]||esc(x.c.status)}</div></div></div>`).join('')}</details>`};
 $('#lb').innerHTML=`<div class="lb">${ranked.map(item).join('')||'<p class="mut">No account has 10 closed calls yet.</p>'}</div>${fresh.length?`<div class="lb-section">New callers</div><div class="lb">${fresh.map(o=>item(o,null)).join('')}</div>`:''}`;
 rows.forEach(o=>{const p=LBPREV[o.n];if(p!=null&&o.avg!=null&&Math.abs(o.avg-p)>1e-9){const el=document.querySelector(`.lb-row[data-acc="${CSS.escape(o.n)}"]`);el&&el.classList.add(o.avg>p?'flash-up':'flash-dn');el&&setTimeout(()=>el.classList.remove('flash-up','flash-dn'),1200)}LBPREV[o.n]=o.avg})}
const LBOPEN=new Set();document.addEventListener('toggle',e=>{const d=e.target;if(d.classList&&d.classList.contains('lbd'))d.open?LBOPEN.add(d.dataset.acc):LBOPEN.delete(d.dataset.acc)},true);
loadLedger().catch(e=>$('#feed').innerHTML='<p class="mut">Could not load data/ledger.json — run refresh.py and serve over http.</p>');
// Portfolio
const H=[['SpaceX',389.02,'#2f9bff'],['Tesla',244.00,'#ff4d5e'],['Cyber segurança pie',107.06,'#21c37a'],['Pelosi pie',96.70,'#a66bff'],['Bancos tugas pie',49.14,'#f5b73b'],['iShares NASDAQ 100',29.63,'#20c5d6'],['iShares S&P 500 IT',29.36,'#ff8a3d']];
const tot=H.reduce((s,h)=>s+h[1],0),musk=(389.02+244)/tot*100;
$('#ptotal').textContent=eur(tot);
$('#pwarn').innerHTML=`<div class="warn">⚠️ Concentration: SpaceX + Tesla (Musk-linked) = <b>${musk.toFixed(0)}%</b> of the portfolio. A single bad headline hits two-thirds of your money.</div>`;
$('#ptab').innerHTML=H.map(h=>`<tr><td><span style="color:${h[2]}">●</span> ${h[0]}</td><td>${eur(h[1])}</td><td class="mut">${(h[1]/tot*100).toFixed(1)}%</td></tr>`).join('');
const C=window.Chart;Chart&&(Chart.defaults.color='#8a96a6');
C&&new Chart($('#donut'),{type:'doughnut',data:{labels:H.map(h=>h[0]),datasets:[{data:H.map(h=>h[1]),backgroundColor:H.map(h=>h[2]),borderWidth:0}]},options:{cutout:'68%',maintainAspectRatio:false,plugins:{legend:{display:false}}}});
const PJ=JSON.parse(localStorage.getItem('ec-proj')||'{}');$('#pj-s').value=PJ.s??tot.toFixed(0);$('#pj-m').value=PJ.m??'';if(PJ.y)$('#pj-y').value=PJ.y;let pjc;
function proj(){const s=+$('#pj-s').value||0,m=+$('#pj-m').value||0,y=+$('#pj-y').value,n=y*12;const sc=[[-25,'#ff4d5e'],[8,'#2f9bff'],[25,'#21c37a']];
 const series=sc.map(([r])=>{const mr=Math.pow(1+r/100,1/12)-1;let v=s,a=[v];for(let i=0;i<n;i++){v=v*(1+mr)+m;a.push(v)}return a});
 $('#pj-out').innerHTML=sc.map(([r],i)=>`<tr><td class="${r<0?'dn':'up'}">${r>0?'+':''}${r}%/yr</td><td>${eur(s+m*n)}</td><td><b>${eur(series[i][n])}</b></td></tr>`).join('');
 if(!C)return;pjc&&pjc.destroy();pjc=new Chart($('#pjc'),{type:'line',data:{labels:[...Array(n+1).keys()].map(i=>'M'+i),datasets:sc.map(([r,c],i)=>({label:(r>0?'+':'')+r+'%',data:series[i],borderColor:c,pointRadius:0,tension:.2}))},options:{maintainAspectRatio:false,scales:{x:{grid:{color:'#1c232d'}},y:{grid:{color:'#1c232d'}}}}})}
['#pj-s','#pj-m','#pj-y'].forEach(i=>$(i).oninput=()=>{localStorage.setItem('ec-proj',JSON.stringify({s:$('#pj-s').value,m:$('#pj-m').value,y:$('#pj-y').value}));proj();rebal()});proj();
// How to rebalance (theory) — computed from holdings
function rebal(){const big=H.filter(h=>/SpaceX|Tesla/.test(h[0])),bt=big.reduce((s,h)=>s+h[1],0),m=+$('#pj-m').value||0,tgt=50;
 const need=bt/(tgt/100)-tot,months=m>0&&need>0?Math.ceil(need/m):null;
 $('#rebal').innerHTML=`<h2>How to rebalance (theory)</h2><p>SpaceX + Tesla are <b>${(bt/tot*100).toFixed(0)}%</b> of your portfolio (${eur(bt)} of ${eur(tot)}). A generic way people reduce concentration:</p>
 <ol class="steps"><li><b>Send new money elsewhere.</b> Put new monthly contributions into a broad S&amp;P 500 fund/ETF (not the tech-only one) until a target split is reached — no selling needed.</li><li><b>Set a max % per holding</b> (e.g. 20–25% for any single stock) and a target for the two combined.</li><li><b>Rebalance periodically</b> (e.g. every 6–12 months), not after every headline.</li><li><b>Avoid selling at a loss just to rebalance</b> — redirecting contributions is usually gentler (and taxes/fees matter).</li></ol>
 <div class="lv"><div><small>Example target</small>${tgt}% combined</div><div><small>New money needed*</small>${need>0?eur(need):'already there'}</div><div><small>Months at your monthly</small>${months??(m>0?'0':'enter monthly')}</div></div>
 <p class="mut">*If all new money goes to other holdings and prices don't move. Educational illustration only — not financial advice.</p>`}
rebal();
// Trade size helper
const TS=JSON.parse(localStorage.getItem('ec-ts')||'{}');['bal','risk','e','s'].forEach(k=>{const el=$('#ts-'+k);if(TS[k]!=null)el.value=TS[k];el.oninput=()=>{TS[k]=el.value;localStorage.setItem('ec-ts',JSON.stringify(TS));tsz()}});
function tsz(){const b=+$('#ts-bal').value,r=+$('#ts-risk').value,e=+$('#ts-e').value,s=+$('#ts-s').value;if(!b||!r||!e||!s||e===s){$('#ts-out').innerHTML='<p class="mut">Fill all four fields.</p>';return}
 const risk=b*r/100,u=risk/Math.abs(e-s);$('#ts-out').innerHTML=`<div class="lv"><div><small>Max loss</small><span class="dn">${eur(risk)}</span></div><div><small>Size (units)</small>${u.toLocaleString('en-US',{maximumFractionDigits:4})}</div><div><small>Position value</small>${eur(u*e)}</div></div>${r>2?'<div class="warn">Above 2% risk per trade is aggressive.</div>':''}${u*e>b?'<div class="warn">Position value is bigger than your balance.</div>':''}`}
tsz();
// Alerts
const ls=(k,v)=>v===undefined?JSON.parse(localStorage.getItem(k)||'[]'):localStorage.setItem(k,JSON.stringify(v));
function rAl(){const a=ls('ec-alerts');$('#al-list').innerHTML=a.map((x,i)=>{const p=PRICES[x.asset]?.price,hit=p==null?null:x.dir==='above'?p>=x.level:p<=x.level;
 return`<div class="alr"><div><b>${esc(x.asset)}</b> <span class="mut">${x.dir} ${x.level}</span><div class="mut">Now ${p==null?'n/a':p.toLocaleString('en-US',{maximumFractionDigits:4})}${hit?' · <b class="up">crossed</b>':''}</div></div><button class="btn g" aria-label="Delete" onclick="delAl(${i})">✕</button></div>`}).join('')||'<p class="mut">No alerts yet.</p>'}
window.delAl=i=>{const a=ls('ec-alerts');a.splice(i,1);ls('ec-alerts',a);rAl()};
$('#al-add').onclick=()=>{const asset=$('#al-a').value.trim().toUpperCase(),level=+$('#al-l').value;if(!asset||!level)return;const a=ls('ec-alerts');a.push({asset,level,dir:$('#al-d').value,at:new Date().toLocaleDateString('pt-PT')});ls('ec-alerts',a);$('#al-a').value=$('#al-l').value='';rAl()};rAl();

if(location.hash)showTab(location.hash==='#plan'?'port':location.hash.slice(1))
{const t=new URLSearchParams(location.search).get('tab');t&&showTab(t)}
