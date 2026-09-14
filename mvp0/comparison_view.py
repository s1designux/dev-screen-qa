"""Read-only image comparison controls shared by draft and inspection views."""
CSS = '''
.cv-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 10px;font-size:12px;flex-shrink:0}
.cv-tools button,.cv-dialog button{font:inherit;padding:6px 12px;border:1px solid #d1d5db;border-radius:8px;background:white;cursor:pointer;color:#374151}
.cv-tools button[aria-pressed=true]{background:#111827;color:white}.cv-tools label{display:flex;align-items:center;gap:5px;margin:0}.cv-tools input{width:95px!important;padding:0!important}
.cv-segments{display:inline-flex;gap:2px;padding:3px;background:#e9edf2;border:1px solid #d1d5db;border-radius:9px}.cv-tools .cv-segments button{border:0;border-radius:6px;background:transparent;min-width:70px}.cv-tools .cv-segments button[aria-pressed=true]{background:white;color:#111827;box-shadow:0 1px 3px #11182726}.cv-segments button:focus-visible{outline:2px solid #2563eb;outline-offset:1px}
.cv-tools [hidden]{display:none!important}.cv-help{color:#657085;font-size:12px}.cv-merged>:first-child{display:none!important}.cv-merged{grid-template-columns:minmax(0,1fr)!important}
.cv-glass{position:absolute;inset:0;width:100%;height:100%;z-index:2;touch-action:none;outline-offset:-3px}.cv-glass[hidden]{display:none}
.cv-dialog{width:min(1100px,92vw);max-height:90vh;overflow:auto;border:1px solid #d1d5db;border-radius:12px;padding:20px;color:#374151;background:white}
.cv-pop{pointer-events:auto!important;box-shadow:0 12px 40px #0f172a40}
.cv-pop-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 0 8px;font-size:12px;color:#374151}
.cv-pop-note{margin:0 0 8px;font-size:12px;color:#b45309}
.cv-pop-x{font:inherit;line-height:1;padding:2px 8px;border:1px solid #d1d5db;border-radius:6px;background:white;color:#374151;cursor:pointer}
.cv-hover{position:fixed;z-index:1000;pointer-events:none;width:min(520px,calc(100vw - 24px));padding:12px;border:1px solid #cbd5e1;border-radius:12px;background:white;box-shadow:0 8px 32px #0f172a33}.cv-hover[hidden]{display:none}.cv-hover .cv-parts{gap:10px}.cv-hover p{margin:0 0 6px}.cv-dialog::backdrop{background:#11182766}.cv-dialog header{padding:0 0 12px;display:flex;justify-content:space-between}.cv-parts{display:grid;grid-template-columns:1fr 1fr;gap:16px}.cv-parts canvas{width:100%;height:auto;background:#fafafa;border:1px solid #e5e7eb}.cv-parts p{font-size:12px}
'''
JS = r'''
(function(){
 const pair=document.querySelector('.cols')||document.querySelector('main.detail .compare');
 if(!pair)return;
 const panes=pair.querySelectorAll('.pane'),d=panes[0]?.querySelector('.canvas img'),v=panes[1]?.querySelector('.canvas img');
 if(!d||!v)return;
 const host=v.parentElement;host.style.position='relative';const tools=document.createElement('div');tools.className='cv-tools';
 tools.innerHTML='<div class="cv-segments" role="group" aria-label="비교 보기 방식"><button type="button" data-mode="side" aria-pressed="true">나란히</button><button type="button" data-mode="over" aria-pressed="false">겹쳐보기</button></div><button type="button" data-mode="crop" aria-pressed="false">부분 확대</button><label hidden>디자인 농도 <input aria-label="디자인 농도" type="range" min="0" max="100" value="50"></label><button type="button" data-reset hidden>위치 초기화</button><span class="cv-help" role="status"></span>';
 const workspace=pair.closest('.app-workspace');(workspace||pair).before(tools);
 const glass=document.createElement('canvas');glass.className='cv-glass';glass.hidden=true;glass.tabIndex=0;glass.setAttribute('aria-label','비교 이미지. 겹쳐보기에서 드래그 또는 방향키로 디자인 이동');host.append(glass);
 const dialog=document.createElement('dialog');dialog.className='cv-dialog';dialog.innerHTML='<header><b>부분 확대 비교</b><button type="button">닫기</button></header><p class="cv-help">화면 너비를 기준으로 같은 배율로 표시합니다. 자동으로 요소 위치를 맞춘 결과는 아닙니다.</p><div class="cv-parts"><section><p>디자인</p><canvas></canvas></section><section><p>개발</p><canvas></canvas></section></div>';document.body.append(dialog);dialog.querySelector('button').onclick=()=>dialog.close();
 const hover=document.createElement('div');hover.className='cv-hover';hover.hidden=true;hover.innerHTML='<div class="cv-parts"><section><p>디자인</p><canvas></canvas></section><section><p>개발</p><canvas></canvas></section></div>';document.body.append(hover);
 const pop=document.createElement('div');pop.className='cv-hover cv-pop';pop.hidden=true;pop.innerHTML='<div class="cv-pop-head"><b class="cv-pop-title">비교</b><button type="button" class="cv-pop-x" aria-label="닫기">닫기</button></div><p class="cv-pop-note" hidden></p><div class="cv-parts"><section><p>디자인</p><canvas></canvas></section><section><p>개발</p><canvas></canvas></section></div>';document.body.append(pop);
 pop.querySelector('.cv-pop-x').onclick=()=>{pop.hidden=true;};
 let lastPt={x:innerWidth/2,y:innerHeight/2};
 document.addEventListener('pointerdown',e=>{lastPt={x:e.clientX,y:e.clientY};if(!pop.hidden&&!pop.contains(e.target))pop.hidden=true;},true);
 document.addEventListener('keydown',e=>{if(e.key==='Escape')pop.hidden=true;});
 function placePop(){pop.hidden=false;pop.style.left='0px';pop.style.top='0px';const r=pop.getBoundingClientRect();
  const left=Math.max(12,Math.min(innerWidth-r.width-12,lastPt.x-r.width/2));let top=lastPt.y-r.height-16;
  if(top<12)top=Math.min(innerHeight-r.height-12,lastPt.y+22);
  pop.style.left=left+'px';pop.style.top=Math.max(12,top)+'px';}
 let mode='side',dx=0,dy=0,start=null;
 const key='qa-view-offset:'+location.pathname+location.search+':'+d.getAttribute('src')+':'+v.getAttribute('src');
 try{const p=JSON.parse(localStorage.getItem(key));if(p&&Number.isFinite(p.x)&&Number.isFinite(p.y)){dx=p.x;dy=p.y;}}catch(e){}
 const help=tools.querySelector('.cv-help'),slider=tools.querySelector('input');
 function save(){try{localStorage.setItem(key,JSON.stringify({x:dx,y:dy}));}catch(e){}}
 function fit(){const w=host.clientWidth,h=host.clientHeight,s=Math.min(w/v.naturalWidth,h/v.naturalHeight);return {w,h,s,x:(w-v.naturalWidth*s)/2,y:(h-v.naturalHeight*s)/2};}
 function paint(){if(!v.naturalWidth||!d.naturalWidth)return;const f=fit();glass.width=f.w;glass.height=f.h;const c=glass.getContext('2d');if(mode==='over'){c.globalAlpha=Number(slider.value)/100;const scale=v.naturalWidth/d.naturalWidth;c.drawImage(d,f.x+dx*f.s,f.y+dy*f.s,v.naturalWidth*f.s,d.naturalHeight*scale*f.s);}if(mode==='crop'&&start?.end){c.strokeStyle='#2563eb';c.lineWidth=2;c.strokeRect(start.p.x,start.p.y,start.end.x-start.p.x,start.end.y-start.p.y);}}
 function setMode(m){mode=m;hover.hidden=true;start=null;pair.classList.toggle('cv-merged',m==='over');glass.hidden=m==='side';glass.style.cursor=m==='crop'?'crosshair':'move';tools.querySelector('label').hidden=m!=='over';tools.querySelector('[data-reset]').hidden=m!=='over';tools.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===m||(b.dataset.mode==='side'&&m==='crop'))));help.textContent=m==='over'?'드래그·방향키로 맞추기 · 이 브라우저에 보기 위치만 저장 · 검수 내용은 유지':m==='crop'?'개발 이미지에 마우스를 올리면 해당 부분을 확대합니다.':'번호나 검수 카드를 누르면 해당 부분을 확대합니다.';requestAnimationFrame(paint);}
 tools.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode==='crop'&&mode==='crop'?'side':b.dataset.mode));slider.oninput=paint;tools.querySelector('[data-reset]').onclick=()=>{dx=dy=0;save();paint();};
 function point(e){const r=glass.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top};}
 function blankCanvas(c){try{const g=c.getContext('2d'),n=Math.min(48,c.width),m=Math.min(48,c.height);
  const t=document.createElement('canvas');t.width=n;t.height=m;const tg=t.getContext('2d');tg.drawImage(c,0,0,n,m);
  const d=tg.getImageData(0,0,n,m).data;for(let i=0;i<d.length;i+=4){if(d[i]<236||d[i+1]<236||d[i+2]<236)return false;}return true;}catch(e){return false;}}
 // ── 밀린 자리 가늠: 두 그림의 '가로줄 무늬'를 견줘, 이 요소가 시안에서 몇 줄 밀렸는지 찾는다 ──
 const PW=320;let profCache=null;
 function profileOf(im){const h=Math.max(1,Math.round(im.naturalHeight*PW/im.naturalWidth));
  const c=document.createElement('canvas');c.width=PW;c.height=h;const g=c.getContext('2d',{willReadFrequently:true});
  g.fillStyle='#fff';g.fillRect(0,0,PW,h);g.drawImage(im,0,0,PW,h);
  const t=g.getImageData(0,0,PW,h).data,out=new Float32Array(h);
  for(let y=0;y<h;y++){let sum=0;for(let x=0;x<PW;x++){const i=(y*PW+x)*4;sum+=255-(t[i]+t[i+1]+t[i+2])/3;}out[y]=sum;}
  return{p:out,h:h,k:PW/im.naturalWidth};}
 function profiles(){if(profCache)return profCache;
  if(!d.naturalWidth||!v.naturalWidth)return{d:null,v:null};   // 그림이 아직 안 떴으면 기억해 두지 않는다
  try{profCache={d:profileOf(d),v:profileOf(v)};}catch(e){return{d:null,v:null};}return profCache;}
 function zncc(a,ao,b,bo,n){let sa=0,sb=0;for(let i=0;i<n;i++){sa+=a[ao+i];sb+=b[bo+i];}
  const ma=sa/n,mb=sb/n;let num=0,da=0,db=0;
  for(let i=0;i<n;i++){const x=a[ao+i]-ma,y=b[bo+i]-mb;num+=x*y;da+=x*x;db+=y*y;}
  return (da<1e-6||db<1e-6)?0:num/Math.sqrt(da*db);}
 function guessShift(devY,devH){   // 개발 그림의 그 줄이 시안에서 몇 줄(320폭 기준) 밀렸는지. 못 찾으면 null
  const P=profiles();if(!P.d||!P.v)return null;
  const pad=Math.max(10,Math.round(P.v.h*0.03));
  const r0=Math.max(0,Math.round(devY*P.v.k)-pad),r1=Math.min(P.v.h,Math.round((devY+devH)*P.v.k)+pad),n=r1-r0;
  if(n<8||n>P.d.h)return null;
  let best=null;
  for(let t=0;t<=P.d.h-n;t++){const sc=zncc(P.v.p,r0,P.d.p,t,n)-Math.abs(t-r0)/P.d.h*0.12;
   if(!best||sc>best.sc)best={sc:sc,t:t};}
  return (best&&best.sc>0.5)?best.t-r0:null;}
 function fitBox(b,ratio){let w=b.w,h=b.h;if(w/h<ratio)w=h*ratio;else h=w/ratio;return{x:b.x+b.w/2-w/2,y:b.y+b.h/2-h/2,w:w,h:h};}
 function crop(box,target=dialog,dbox){if(!v.naturalWidth||!d.naturalWidth)return false;const x=Math.max(0,box.x),y=Math.max(0,box.y),w=Math.min(v.naturalWidth,box.x+box.w)-x,h=Math.min(v.naturalHeight,box.y+box.h)-y;if(w<3||h<3)return false;
 const scale=d.naturalWidth/v.naturalWidth;const factor=Math.min(1400/w,1400/h,Math.max(1,400/w)),outW=Math.max(1,Math.round(w*factor)),outH=Math.max(1,Math.round(h*factor));
 const db=dbox?fitBox(dbox,w/h):null;   // 시안 쪽 자리를 알면 그 자리를 자른다(위아래로 밀린 화면도 제 짝끼리 보이게)
 target.querySelectorAll('canvas').forEach((c,i)=>{c.width=outW;c.height=outH;const ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,outW,outH);
  if(i)ctx.drawImage(v,x,y,w,h,0,0,outW,outH);
  else if(db)ctx.drawImage(d,db.x,db.y,db.w,db.h,0,0,outW,outH);
  else ctx.drawImage(d,(x-dx)*scale,(y-dy)*scale,w*scale,h*scale,0,0,outW,outH);});
 if(target===dialog&&!dialog.open)dialog.showModal();return true;}
 function showHover(e){const f=fit(),p=point(e);if(p.x<f.x||p.y<f.y||p.x>f.x+v.naturalWidth*f.s||p.y>f.y+v.naturalHeight*f.s){hover.hidden=true;return;}const w=Math.min(v.naturalWidth,160/f.s),h=Math.min(v.naturalHeight,110/f.s);crop({x:Math.max(0,Math.min(v.naturalWidth-w,(p.x-f.x)/f.s-w/2)),y:Math.max(0,Math.min(v.naturalHeight-h,(p.y-f.y)/f.s-h/2)),w,h},hover);hover.hidden=false;const r=hover.getBoundingClientRect();hover.style.left=Math.max(12,Math.min(innerWidth-r.width-12,e.clientX+20))+'px';hover.style.top=Math.max(12,e.clientY+r.height+24<innerHeight?e.clientY+20:e.clientY-r.height-20)+'px';}
 glass.onpointerleave=()=>{hover.hidden=true;};window.addEventListener('scroll',()=>{hover.hidden=true;},true);window.addEventListener('blur',()=>{hover.hidden=true;});
 glass.onpointerdown=e=>{if(mode!=='over'||e.button!==0)return;glass.focus();glass.setPointerCapture(e.pointerId);start={p:point(e),dx,dy};};
 glass.onpointermove=e=>{if(mode==='crop'){showHover(e);return;}if(!start)return;const p=point(e);if(mode==='over'){const f=fit();dx=start.dx+(p.x-start.p.x)/f.s;dy=start.dy+(p.y-start.p.y)/f.s;}else start.end=p;paint();};
 glass.onpointerup=e=>{if(!start)return;const a=start.p,b=point(e),f=fit();start=null;if(mode==='over')save();else if(mode==='crop')crop({x:(Math.min(a.x,b.x)-f.x)/f.s,y:(Math.min(a.y,b.y)-f.y)/f.s,w:Math.abs(b.x-a.x)/f.s,h:Math.abs(b.y-a.y)/f.s});paint();};
 glass.onpointercancel=()=>{start=null;paint();};glass.onkeydown=e=>{if(e.key==='Escape'){setMode('side');return;}if(mode!=='over')return;const n=e.shiftKey?10:1;const moves={ArrowLeft:[-n,0],ArrowRight:[n,0],ArrowUp:[0,-n],ArrowDown:[0,n]};if(!moves[e.key])return;e.preventDefault();dx+=moves[e.key][0];dy+=moves[e.key][1];save();paint();};
 window.qaCompareIssue=function(id){
  const g=document.getElementById('box-'+id)||document.getElementById('abox-'+id);if(!g)return;
  const rect=g.tagName.toLowerCase()==='rect'?g:g.querySelector('rect'),svg=rect&&rect.ownerSVGElement;if(!rect||!svg)return;
  const b=svg.viewBox.baseVal,kx=v.naturalWidth/b.width,ky=v.naturalHeight/b.height;
  const card=document.getElementById('issue-'+id)||document.getElementById('cand-'+id);
  const no=card?((card.querySelector('.pinno')||{}).textContent||'').trim():'';
  pop.querySelector('.cv-pop-title').textContent=no?('번호 '+no+' — 디자인 · 개발 나란히 보기'):'디자인 · 개발 나란히 보기';
  const bx=(Number(rect.getAttribute('x'))-20)*kx,by=(Number(rect.getAttribute('y'))-20)*ky,
        bw=(Number(rect.getAttribute('width'))+40)*kx,bh=(Number(rect.getAttribute('height'))+40)*ky;
  const ref=window.qaDesignRef,db=(window.qaDesignBox||{})[id],al=window.qaAlign;
  let dbox=null;
  if(db&&ref&&ref.w){const kd=d.naturalWidth/ref.w;dbox={x:(db[0]-20)*kd,y:(db[1]-20)*kd,w:(db[2]+40)*kd,h:(db[3]+40)*kd};}
  else{const sx=d.naturalWidth/v.naturalWidth,g=guessShift(by,bh);
   if(g!==null){const P=profiles();dbox={x:bx*sx,y:(by*P.v.k+g)/P.d.k,w:bw*sx,h:bh*sx};}   // 밀린 만큼 가늠해서
   else if(al&&al.s)dbox={x:bx*al.s+al.tx,y:by*al.s+al.ty,w:bw*al.s,h:bh*al.s};}           // 안 되면 화면 전체 맞춤값으로
  if(!crop({x:bx,y:by,w:bw,h:bh},pop,dbox))return;
  const cs=pop.querySelectorAll('canvas'),note=pop.querySelector('.cv-pop-note');
  const empty=blankCanvas(cs[0])&&blankCanvas(cs[1]);
  note.textContent=empty?'이 자리는 두 그림 모두 비어 있어요 — 핀 자리와 올린 그림이 어긋났을 수 있어요.':'';
  note.hidden=!empty;
  placePop();};
 new ResizeObserver(paint).observe(host);d.addEventListener('load',paint);v.addEventListener('load',paint);setMode('side');
})();
'''
