// ===== Price charts: SVG sparkline per card (light) + tap-to-open lightweight-charts modal =====
(function(){
 const UP='#34d399',DN='#ff6b78',GRID='#2a2a2a',CACHE={},TTL=60000;
 function getCandles(a){const c=CACHE[a];if(c&&Date.now()-c.t<TTL)return c.p;
  const p=fetch('data/candles/'+encodeURIComponent(a)+'.json?t='+Math.floor(Date.now()/TTL)).then(r=>r.ok?r.json():null).catch(()=>null);CACHE[a]={t:Date.now(),p};return p}
 const callById=id=>LEDGER&&LEDGER.calls.find(c=>String(c.id)===String(id));
 const levels=c=>[['Bought at',lvl(c.entry),'#e5e5e5'],['Exit if loss',lvl(c.stop),DN],['Take profit',lvl(c.target),UP]].filter(x=>x[1]!=null);
 function spark(el){const c=callById(el.dataset.id);getCandles(el.dataset.asset).then(d=>{const rows=d&&d['1D'];if(!rows||rows.length<2){el.innerHTML='<span class="mut" style="font-size:11px">chart n/a</span>';return}
  const W=300,H=72,cl=rows.map(r=>r[4]),lv=c?levels(c).map(x=>x[1]):[];let mn=Math.min(...cl),mx=Math.max(...cl);
  // include levels only if they're reasonably near, so the line isn't flattened
  lv.forEach(v=>{if(v>mn*0.9&&v<mx*1.1){mn=Math.min(mn,v);mx=Math.max(mx,v)}});const pad=(mx-mn)*0.08||1;mn-=pad;mx+=pad;
  const y=v=>(H-(v-mn)/(mx-mn)*H).toFixed(1),x=i=>(i/(cl.length-1)*W).toFixed(1),_e=c?lvl(c.entry):null,col=(_e!=null?(/short/i.test(c.direction||"")?cl[cl.length-1]<=_e:cl[cl.length-1]>=_e):cl[cl.length-1]>=cl[0])?UP:DN;
  const pts=cl.map((v,i)=>x(i)+','+y(v)).join(' ');
  const lines=c?levels(c).filter(l=>l[1]>=mn&&l[1]<=mx).map(l=>`<line x1="0" x2="${W}" y1="${y(l[1])}" y2="${y(l[1])}" stroke="${l[2]}" stroke-width="1" stroke-dasharray="4 3" opacity=".8"/><text x="${W-2}" y="${Math.max(9,y(l[1])-3)}" text-anchor="end" font-size="9" fill="${l[2]}">${l[0]}</text>`).join(''):'';
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" width="100%" height="100%" aria-label="24h price"><title>Colour = change since entry · tap card for bigger chart</title>${lines}<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`})}
 // lazy sparks: only render when card scrolls into view
 const io='IntersectionObserver' in window?new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){io.unobserve(e.target);spark(e.target)}}),{rootMargin:'200px'}):null;
 const _rs=renderSignals;renderSignals=function(){_rs();document.querySelectorAll('#feed .spark').forEach(el=>{const r=el.getBoundingClientRect();(!io||(r.top<innerHeight+200&&r.bottom>-200&&r.width>0))?spark(el):io.observe(el)})};
 // modal
 let LW=null;const loadLW=()=>LW||(LW=new Promise((ok,no)=>{const s=document.createElement('script');s.src='https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js';s.onload=()=>ok(window.LightweightCharts);s.onerror=no;document.head.appendChild(s)}));
 const modal=document.createElement('div');modal.className='chart-modal';modal.style.display='none';
 modal.innerHTML='<div class="panel"><div class="row"><b class="cm-title"></b><button class="btn g cm-close" aria-label="Close">✕</button></div><div class="ranges"><button data-r="1D" class="on">1D</button><button data-r="1W">1W</button><button data-r="1M">1M</button></div><div class="chartbox"></div><div class="mut cm-legend" style="font-size:12px;margin-top:6px"></div></div>';
 document.body.appendChild(modal);
 Object.assign(modal.style,{position:'fixed',inset:'0',zIndex:50,background:'rgba(0,0,0,.7)',alignItems:'center',justifyContent:'center',padding:'12px'});
 let chart=null,cur=null;const box=modal.querySelector('.chartbox');
 function close(){modal.style.display='none';if(chart){chart.remove();chart=null}}
 modal.querySelector('.cm-close').onclick=close;modal.onclick=e=>{if(e.target===modal)close()};document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
 modal.querySelectorAll('.ranges button').forEach(b=>b.onclick=()=>{modal.querySelectorAll('.ranges button').forEach(x=>x.classList.toggle('on',x===b));draw(b.dataset.r)});
 async function draw(r){const c=cur;if(chart){chart.remove();chart=null}box.innerHTML='<p class="mut">Loading…</p>';
  let L,d;try{[L,d]=await Promise.all([loadLW(),getCandles(c.asset)])}catch(e){box.innerHTML='<p class="mut">Chart library could not load (offline?).</p>';return}
  const rows=d&&d[r];if(!rows||!rows.length){box.innerHTML='<p class="mut">No chart data for this asset (n/a).</p>';return}
  box.innerHTML='';const h=box.clientHeight||Math.min(380,Math.round(window.innerHeight*0.5));
  chart=L.createChart(box,{height:h,width:box.clientWidth||320,layout:{background:{color:'transparent'},textColor:'#9ca3af'},grid:{vertLines:{color:GRID},horzLines:{color:GRID}},rightPriceScale:{borderColor:GRID},timeScale:{borderColor:GRID,timeVisible:r!=='1M'},crosshair:{mode:0}});
  const lv=levels(c).map(x=>x[1]);const s=chart.addCandlestickSeries({autoscaleInfoProvider:orig=>{const r=orig();if(!r||!r.priceRange)return r;let{minValue:mn,maxValue:mx}=r.priceRange;lv.forEach(v=>{if(v>mn*0.85&&v<mx*1.15){mn=Math.min(mn,v);mx=Math.max(mx,v)}});return{...r,priceRange:{minValue:mn,maxValue:mx}}},upColor:UP,downColor:DN,borderUpColor:UP,borderDownColor:DN,wickUpColor:UP,wickDownColor:DN});
  s.setData(rows.map(x=>({time:x[0],open:x[1],high:x[2],low:x[3],close:x[4]})));
  levels(c).forEach(([t,p,col])=>s.createPriceLine({price:p,color:col,lineWidth:1,lineStyle:2,axisLabelVisible:true,title:t}));
  chart.timeScale().fitContent();
  modal.querySelector('.cm-legend').textContent=`Data as of ${(d.as_of||'').replace('T',' ').slice(0,16)} PT · dashed lines: buy, exit-if-loss, take-profit`}
 window.addEventListener('resize',()=>{if(chart)chart.applyOptions({width:box.clientWidth})});
 document.getElementById('feed').addEventListener('click',e=>{if(e.target.closest('a,summary,details,button,input'))return;const card=e.target.closest('.card[data-id]');if(!card)return;
  cur=callById(card.dataset.id);if(!cur)return;modal.querySelector('.cm-title').textContent=`${cur.asset} · ${cur.direction} · ${cur.account}`;
  modal.style.display='flex';modal.querySelectorAll('.ranges button').forEach(x=>x.classList.toggle('on',x.dataset.r==='1D'));draw('1D')});
})();
