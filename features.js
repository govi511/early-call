// ===== Early score (heuristic, 0-100) =====
function earlyScore(c,l){let s=50;const why=[];const e=lvl(c.entry),st=lvl(c.stop),t=lvl(c.target),n=(c.notes||'').toLowerCase();
 if(e!=null&&st!=null&&t!=null){s+=15;why.push('+15 clear buy/exit/target');const rr=Math.abs(t-e)/Math.abs(e-st);if(isFinite(rr)){if(rr>=2){s+=10;why.push(`+10 reward ${rr.toFixed(1)}× the risk`)}else if(rr<1){s-=10;why.push(`−10 reward only ${rr.toFixed(1)}× the risk`)}}}else{s-=15;why.push('−15 missing price levels')}
 if(c.after_the_fact){s-=35;why.push('−35 posted after the fact')}
 if(/affiliate|ref link|promo/.test(n)){s-=10;why.push('−10 affiliate')}
 if(/unclear|never filled/.test(n)||c.status==='unclear'){s-=10;why.push('−10 unclear')}
 if(c.status==='open'&&l.p!=null){if(Math.abs(l.move)<=1){s+=15;why.push('+15 price still near buy level')}else if(l.toTgt!=null&&l.toTgt<=0){s-=20;why.push('−20 target already hit')}}
 if(c.status==='hit_target'){s+=10;why.push('+10 hit target')}if(c.status==='stopped'){s-=5;why.push('−5 stopped')}
 s=Math.max(0,Math.min(100,s));return{s,why}}
function earlyHTML(c,l){const{s,why}=earlyScore(c,l);const col=s>=65?'var(--up)':s>=40?'var(--warn)':'var(--dn)';
 return`<div class="row" style="margin-top:8px" title="${why.join(' · ')}"><span class="mut">Early score (how timely &amp; clear)</span><span style="flex:1;margin:0 8px" class="meter"><i style="width:${s}%;background:${col}"></i></span><b style="color:${col}">${s}</b></div><details class="why show"><summary>Why this score</summary>${why.map(w=>`<div>${esc(w)}</div>`).join('')}</details>`}
// ===== Hype meter per account =====
function renderHype(){if(!LEDGER)return;const by={};LEDGER.calls.forEach(c=>(by[c.account]??=[]).push(c));
 $('#hype').innerHTML=Object.entries(by).map(([a,cs])=>{const days=new Set(cs.map(c=>c.logged_at_lisbon.slice(0,10))).size,perDay=cs.length/Math.max(days,1);
  const flags=cs.filter(c=>/affiliate|unclear|never filled/.test((c.notes||'').toLowerCase())).length,res=cs.filter(c=>['hit_target','stopped'].includes(c.status)),wr=res.length?res.filter(c=>c.status==='hit_target').length/res.length:null;
  const assets=new Set(cs.map(c=>c.asset)).size;let h=Math.min(30,perDay*10)+flags/cs.length*30+(wr==null?10:(1-wr)*25)+Math.min(15,(assets-1)*5);h=Math.round(Math.min(100,h));
  const col=h>=60?'var(--dn)':h>=35?'var(--warn)':'var(--up)';
  return`<div class="card"><div class="row"><b>${esc(a)}</b><b style="color:${col}">${h>=60?'🔥 High hype':h>=35?'⚠️ Medium':'✅ Low'} · ${h}</b></div><div class="meter" style="margin:8px 0"><i style="width:${h}%;background:${col}"></i></div>
  <div class="mut">${cs.length} calls over ${days} day(s) (${perDay.toFixed(1)}/day) · ${assets} assets · ${flags} flagged (affiliate/unclear) · win rate ${wr==null?'n/a':Math.round(wr*100)+'%'} on ${res.length} resolved</div></div>`}).join('')}
// ===== Alerts with live status =====
rAl=function(){const a=ls('ec-alerts');$('#al-list').innerHTML=a.map((x,i)=>{const p=PRICES[x.asset]?.price;const hit=p==null?null:x.dir==='above'?p>=x.level:p<=x.level;
 return`<tr><td><b>${esc(x.asset)}</b></td><td class="${x.dir==='above'?'up':'dn'}">${x.dir==='above'?'▲':'▼'} ${x.level}</td><td>${p==null?'<span class="mut">n/a*</span>':p.toLocaleString('en-US',{maximumFractionDigits:4})}</td><td>${hit==null?'':hit?'<b class="up">TRIGGERED</b>':`<span class="mut">${((x.level-p)/p*100).toFixed(2)}% away</span>`}</td><td><button class="btn g" onclick="delAl(${i})">✕</button></td></tr>`}).join('')||'<tr><td class="mut">No alerts yet.</td></tr>'};
const _lp=loadPrices;loadPrices=()=>_lp().then(()=>{rAl();renderHype()});
setTimeout(()=>{rAl();renderHype()},800);setInterval(loadPrices,5*60*1000);
// ===== CFD risk / position calculator (ESMA retail caps) =====
const CAPS={'Major FX':30,'Minor FX / gold / major index':20,'Commodities (ex-gold) / minor index':10,'Stocks':5,'Crypto':2};
$('#cf-cls').innerHTML=Object.entries(CAPS).map(([k,v])=>`<option value="${v}">${k} (max ${v}:1)</option>`).join('');$('#cf-cls').value=5;
function cfd(){const bal=+$('#cf-bal').value,rk=+$('#cf-r').value,e=+$('#cf-e').value,s=+$('#cf-s').value,lev=+$('#cf-l').value,cap=+$('#cf-cls').value,t=+$('#cf-t').value;const w=[];
 if(!bal||!e||!s||e===s||!lev){$('#cf-out').innerHTML='<p class="mut">Fill balance, entry, stop and leverage.</p>';return}
 const risk=bal*rk/100,dist=Math.abs(e-s),units=risk/dist,notional=units*e,margin=notional/lev,liq=100/lev,stopPct=dist/e*100;
 if(lev>cap)w.push(`Leverage ${lev}:1 exceeds the retail cap of ${cap}:1 for this class — the broker won't allow it.`);
 if(lev>5)w.push(`High leverage (${lev}:1): a ${liq.toFixed(1)}% move against you wipes out the margin.`);
 if(rk>2)w.push(`Risking ${rk}% per trade is aggressive — most traders cap at 1–2%.`);
 if(margin>bal*0.5)w.push(`Margin €${margin.toFixed(2)} is over half your balance.`);
 if(margin>bal)w.push('Not enough balance for this position size.');
 if(stopPct>=liq)w.push('Your stop is beyond the margin wipe-out distance — you could be closed out before the stop.');
 const rr=t?Math.abs(t-e)/dist:null;
 $('#cf-out').innerHTML=`<div class="lv"><div><small>Units</small>${units.toFixed(4)}</div><div><small>Position value</small>${eur(notional)}</div><div><small>Margin needed</small>${eur(margin)}</div><div><small>Loss at stop</small><span class="dn">${eur(risk)}</span></div><div><small>Stop distance</small>${stopPct.toFixed(2)}%</div><div><small>${rr?'Gain at target':'Margin wipe-out'}</small>${rr?`<span class="up">${eur(risk*rr)}</span> (R:R ${rr.toFixed(1)})`:liq.toFixed(1)+'% move'}</div></div>
 ${w.map(x=>`<div class="warn" style="margin:6px 0">⚠️ ${x}</div>`).join('')||'<p class="up">Within typical risk limits.</p>'}<p class="mut">Overnight financing fees and spreads not included. 70–80% of retail CFD accounts lose money.</p>`}
document.querySelectorAll('#risk input,#risk select').forEach(i=>i.oninput=cfd);cfd();
// ===== Events + Tesla/SpaceX page =====
function evCard(e){const d=e.date?new Date(e.date+'T12:00'):null;const tc={Confirmed:'var(--up)',Unconfirmed:'var(--warn)',Tentative:'var(--warn)',TBA:'var(--mut)'}[e.tag]||'var(--mut)';const days=d?Math.ceil((d-new Date())/864e5):null;
 return`<div class="card row"><div style="text-align:center;min-width:54px">${d?`<div class="mut">${d.toLocaleDateString('en-GB',{month:'short'})}</div><div class="big">${d.getDate()}</div>`:'<div class="big">?</div>'}</div><div style="flex:1"><b>${esc(e.title)}</b><div class="mut">${esc(e.detail)}</div>${days!=null&&days>=0?`<div class="mut" style="color:var(--acc)">in ${days} day(s)</div>`:''}</div><span class="tag" style="color:${tc}">${esc(e.tag)}</span></div>`}
fetch('data/events.json').then(r=>r.json()).then(ev=>{$('#ev').innerHTML=ev.filter(e=>e.date).map(evCard).join('');
 const ts=ev.filter(e=>e.co==='tesla'||e.co==='spacex'),pt=PRICES.TSLA;$('#tsxl').innerHTML=ts.map(evCard).join('');
 const t=()=>{const p=PRICES.TSLA;$('#tsx-px').innerHTML=`<div class="lv"><div><small>TSLA now</small>${p?.price?'$'+p.price.toFixed(2):'n/a'}</div><div><small>Your Tesla</small>€244.00</div><div><small>Your SpaceX</small>€389.02</div></div><p class="mut">SpaceX live price not tracked yet (ticker not configured). A Tesla–SpaceX merger would concentrate both positions into one stock.</p>`};t();setTimeout(t,1500)});
