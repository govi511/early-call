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
function renderHype(){if(!LEDGER)return;const by={};LEDGER.calls.filter(c=>!isSpam(c)).forEach(c=>(by[c.account]??=[]).push(c));
 $('#hype').innerHTML=Object.entries(by).map(([a,cs])=>{const days=new Set(cs.map(c=>c.logged_at_lisbon.slice(0,10))).size,perDay=cs.length/Math.max(days,1);
  const flags=cs.filter(c=>/affiliate|unclear|never filled/.test((c.notes||'').toLowerCase())).length,res=cs.filter(c=>['hit_target','stopped'].includes(c.status)),wr=res.length?res.filter(c=>c.status==='hit_target').length/res.length:null;
  const assets=new Set(cs.map(c=>c.asset)).size;let h=Math.min(30,perDay*10)+flags/cs.length*30+(wr==null?10:(1-wr)*25)+Math.min(15,(assets-1)*5);h=Math.round(Math.min(100,h));
  const col=h>=60?'var(--dn)':h>=35?'var(--warn)':'var(--up)';
  return`<div class="card"><div class="row"><b>${esc(a)}</b><b style="color:${col}">${h>=60?'🔥 High hype':h>=35?'⚠️ Medium':'✅ Low'} · ${h}</b></div><div class="meter" style="margin:8px 0"><i style="width:${h}%;background:${col}"></i></div>
  <div class="mut">${cs.length} calls over ${days} day(s) (${perDay.toFixed(1)}/day) · ${assets} assets · ${flags} flagged (affiliate/unclear) · win rate ${wr==null?'n/a':Math.round(wr*100)+'%'} on ${res.length} resolved</div></div>`}).join('')}
const _lp=loadPrices;loadPrices=()=>_lp().then(()=>{rAl();renderHype();renderLeader()});
setTimeout(()=>{rAl();renderHype()},800);
// ===== Events (incl. Tesla & SpaceX) =====
function evCard(e){const d=e.date?new Date(e.date+'T12:00'):null,tbc=e.tag==='TBC';const days=d?Math.ceil((d-new Date())/864e5):null;const co={tesla:'Tesla',spacex:'SpaceX',macro:'Macro'}[e.co]||'';
 return`<div class="card row"><div style="text-align:center;min-width:54px">${d?`<div class="mut">${d.toLocaleDateString('en-GB',{month:'short'})}</div><div class="big">${d.getDate()}</div>`:'<div class="big">?</div>'}</div><div style="flex:1"><b>${esc(e.title)}</b><div class="mut">${esc(e.detail)}</div>${days!=null&&days>=0?`<div class="mut" style="color:var(--txt)">in ${days} day(s)</div>`:''}${(e.affects||[]).length?`<div class="moves">Could move: ${e.affects.map(a=>`<span class="tag">${esc(a)}</span>`).join('')}</div>`:''}</div><div style="display:flex;flex-direction:column;gap:4px;align-items:flex-end">${co?`<span class="tag">${co}</span>`:''}<span class="tag" style="color:${tbc?'var(--warn)':'var(--up)'}">${tbc?'TBC':'Confirmed'}</span></div></div>`}
function tsxPx_removed(){const p=PRICES.TSLA;$('#tsx-px').innerHTML=`<div class="lv"><div><small>TSLA now</small>${p?.price?'$'+p.price.toFixed(2):'n/a'}</div><div><small>Your Tesla</small>€244.00</div><div><small>Your SpaceX</small>€389.02</div></div><p class="mut">Tesla &amp; SpaceX dates are tagged below. SpaceX live price not tracked.</p>`}
fetch('data/events.json?t='+Date.now()).then(r=>r.json()).then(ev=>{const today=new Date().toISOString().slice(0,10);
 $('#ev').innerHTML=ev.filter(e=>e.date&&e.date>=today&&e.tag!=='TBC').sort((a,b)=>a.date.localeCompare(b.date)).map(evCard).join('')||'<p class="mut">No confirmed events.</p>';
 $('#ev-tbc').innerHTML=ev.filter(e=>e.tag==='TBC'&&(!e.date||e.date>=today)).map(evCard).join('')||'<p class="mut">None.</p>'}).catch(()=>{$('#ev').innerHTML='<p class="mut">Could not load events.</p>'});
