// v59 header batch: sticky filter bar, single freshness pill, one-line card header, 'price not tracked' tags (UI only)
(()=>{const q=s=>document.querySelector(s);
 // 1. sticky filter bar: move Show hidden + news into .filters
 const bar=()=>{const w=q('.filters');if(!w||w._h)return;w._h=1;
  const hdr=q('header'),setTop=()=>document.documentElement.style.setProperty('--hdrh',(hdr?hdr.offsetHeight:0)+'px');setTop();addEventListener('resize',setTop);
  const cb=q('#showspam'),lab=cb&&cb.closest('label'),nb=q('#newsbtn');
  if(lab){const chip=document.createElement('label');chip.className='fchip spamchip';chip.append(cb,q('#spamlbl'));w.append(Object.assign(document.createElement('span'),{className:'fdiv'}),chip);lab.remove()}
  if(nb){nb.classList.add('fchip');nb.style.marginLeft='';w.append(nb)}};
 // 2. freshness pill
 let pxAt=null,busy=0;const pAt=()=>{const a=typeof PRICES!=='undefined'&&PRICES._at?+new Date(PRICES._at):null;return Math.max(a||0,pxAt||0)||null};
 const wrapFns=()=>{if(typeof window.applyLive==='function'&&!applyLive._h){const o=applyLive;window.applyLive=function(){pxAt=Date.now();return o.apply(this,arguments)};applyLive._h=1}
  if(typeof window.loadPrices==='function'&&!loadPrices._h){const o=loadPrices;window.loadPrices=loadPrices=async function(){busy++;pill();try{return await o.apply(this,arguments)}finally{busy--;pill()}};loadPrices._h=1}};
 const ago=s=>s<60?s+'s':s<3600?Math.round(s/60)+'m':Math.round(s/3600)+'h';
 function pill(){const ind=q('.live');if(!ind)return;let t=ind.querySelector('.fresh-text');if(!t){t=document.createElement('span');t.className='fresh-text';ind.append(t)}
  const rp=q('#rp'),inflight=busy>0||(rp&&(rp.disabled||rp.classList.contains('busy')));
  if(inflight){t.textContent='Updating prices…';ind.classList.add('updating');return}ind.classList.remove('updating');
  const at=pAt(),h=ind.dataset.h;t.textContent=at?`${h==='red'?'Stale':h==='amber'?'Delayed':'Live'} · ${ago(Math.max(0,Math.round((Date.now()-at)/1000)))}`:'Waiting for prices';
  const lt=ind.querySelector('.live-text');ind.title=(lt?lt.textContent:'')+' — tap for details'}
 // 3+4. cards and leaderboard chips
 const noPx=a=>{const p=typeof PRICES!=='undefined'&&PRICES[a];return !p||p.price==null};
 const tag=()=>Object.assign(document.createElement('span'),{className:'nptrack',textContent:'price not tracked'});
 function cards(){document.querySelectorAll('#feed .card:not(.cons-card):not([data-h1])').forEach(c=>{c.dataset.h1=1;const hl=c.querySelector(':scope>.headline');const tr=c.querySelector(':scope>.row');if(!hl||!tr)return;
   const left=tr.firstElementChild,st=tr.querySelector(':scope>b[class^="st-"]'),a=c.querySelector('.asset'),asset=a?a.textContent:'';
   const mv=hl.querySelector(':scope>.up,:scope>.dn,:scope>span:not(.nopx):not(.mktc):not(.mut)'),mk=hl.querySelector('.mktc');
   const box=document.createElement('span');box.className='hmove';
   if(noPx(asset)&&!mv){if(!hl.querySelector('.mut'))box.append(tag());else box.append(hl.querySelector('.mut'))}else if(mv)box.append(mv);
   const bd=left.querySelector('.badge.long,.badge.short'),h=document.createElement('div');h.className='h1row';
   const dc=document.createElement('span');dc.className='hdir '+(bd&&bd.classList.contains('short')?'short':'long');dc.textContent=bd&&bd.classList.contains('short')?'Short':'Long';
   if(a){a.classList.add('h1asset');h.append(a)}h.append(dc,box);if(st){st.classList.add('h1st');h.append(st)}tr.before(h);tr.classList.add('hmeta');
   if(mk){mk.classList.add('mktc-s');left.after(mk)}hl.remove();
   if(noPx(asset)&&!mv){c.querySelectorAll('.tag').forEach(t=>{if(t.textContent==='no price')t.remove()});
    const pn=[...c.querySelectorAll(':scope>.row')].find(r=>/Price now/.test(r.textContent));if(pn&&!pn.querySelector('.noentry'))pn.remove();else if(pn){const b=pn.querySelector('b');b&&b.remove();pn.querySelector('small')?.remove()}
    const sd=c.querySelector('.stopdist');if(sd&&sd.parentNode&&/no price source|n\/a/.test(sd.parentNode.textContent)&&!/%/.test(sd.parentNode.textContent))sd.parentNode.remove()}})}
 function lb(){document.querySelectorAll('#lb .lb-calls:not([data-h1])').forEach(w=>{w.dataset.h1=1;const seen=new Map();
   w.querySelectorAll('.lb-call.np').forEach(x=>{const m=x.textContent.match(/^(.*) — no price$/);if(!m)return;const k=m[1];
    if(seen.has(k)){const o=seen.get(k);o.n++;o.el.querySelector('.npn').textContent='×'+o.n;(x.closest('a')&&x.closest('a').parentNode===w?x.closest('a'):x).remove();return}
    x.textContent=k+' ';x.classList.add('nptr');x.append(tag(),Object.assign(document.createElement('small'),{className:'npn'}));seen.set(k,{n:1,el:x})})})}
 const run=()=>{try{bar();wrapFns();cards();lb();pill()}catch(e){console.warn(e)}};
 const mo=new MutationObserver(()=>{mo.disconnect();run();obs()}),obs=()=>['#feed','#lb'].forEach(s=>{const e=q(s);e&&mo.observe(e,{childList:true})});
 run();obs();setTimeout(run,800);setTimeout(run,2000);setInterval(pill,1000);
})();
