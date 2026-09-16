"""Read-only image comparison controls shared by draft and inspection views."""
CSS = '''
.cv-tools{position:relative;display:flex;gap:var(--spacing-8);align-items:center;justify-content:center;flex-wrap:wrap;margin:0 0 var(--spacing-10);font-size:var(--font-size-12);flex-shrink:0}

.cv-tools button[aria-pressed=true]{background:var(--color-button-bg-primary--default);border-color:var(--color-button-border-primary--default);color:var(--color-button-label-primary--default)}.cv-tools label{display:flex;align-items:center;gap:var(--spacing-4);margin:0}.cv-tools input{width:95px!important;padding:0!important}
.cv-segments button:focus-visible{outline:2px solid var(--color-action-primary-default);outline-offset:1px}
.cv-tools [hidden]{display:none!important}.cv-help{color:var(--color-text-caption);font-size:var(--font-size-12)}.cv-merged>:first-child{display:none!important}.cv-merged{grid-template-columns:minmax(0,1fr)!important}
.cv-glass{position:absolute;inset:0;width:100%;height:100%;z-index:2;touch-action:none;outline-offset:-3px}.cv-glass[hidden]{display:none}
.cv-dialog{width:min(1100px,92vw);max-height:90vh;overflow:auto}
.cv-pop{pointer-events:auto!important;box-shadow:var(--shadow-raised)}
.cv-pop-head{display:flex;align-items:center;justify-content:space-between;gap:var(--spacing-8);margin:0 0 var(--spacing-8);font-size:var(--font-size-12);color:var(--color-text-secondary)}
.cv-pop-note{margin:0 0 var(--spacing-8);font-size:var(--font-size-12);color:var(--color-text-state-caution)}
.cv-pop-x{font:inherit;line-height:1;padding:var(--spacing-2) var(--spacing-8);border:1px solid var(--color-border-default);border-radius:var(--radius-6);background:var(--color-surface-default);color:var(--color-text-secondary);cursor:pointer}
.cv-hover{position:fixed;z-index:1000;pointer-events:none;width:min(660px,calc(100vw - 24px));padding:var(--spacing-12);border:1px solid var(--color-border-default);border-radius:var(--radius-12);background:var(--color-surface-default);box-shadow:var(--shadow-raised)}.cv-hover[hidden]{display:none}.cv-hover .cv-parts{gap:var(--spacing-10)}.cv-hover p{margin:0 0 var(--spacing-6)}.cv-dialog::backdrop{background:var(--color-overlay)}.cv-dialog header{padding:0 0 var(--spacing-12);display:flex;justify-content:space-between}.cv-parts{display:grid;grid-template-columns:1fr 1fr;gap:var(--spacing-16)}.cv-parts canvas{width:100%;height:auto;background:var(--color-bg-default);border:1px solid var(--color-border-subtle)}.cv-parts p{font-size:var(--font-size-12)}
'''
JS = r'''
(function(){
 const pair=document.querySelector('.cols')||document.querySelector('main.detail .compare');
 if(!pair)return;
 const panes=pair.querySelectorAll('.pane'),d=panes[0]?.querySelector('.canvas img'),v=panes[1]?.querySelector('.canvas img');
 if(!d||!v)return;
 const host=v.parentElement;host.style.position='relative';const tools=document.createElement('div');tools.className='cv-tools';
 tools.innerHTML='<div class="cv-segments" role="group" aria-label="비교 보기 방식"><button type="button" data-mode="side" aria-pressed="true">나란히</button><button type="button" data-mode="over" aria-pressed="false">겹쳐보기</button></div><button type="button" data-mode="crop" aria-pressed="false">부분 확대</button><label hidden>디자인 농도 <input aria-label="디자인 농도" type="range" min="0" max="100" value="50"></label><button type="button" data-reset hidden>위치 초기화</button>';
 const workspace=pair.closest('.app-workspace');(workspace||pair).before(tools);
 const glass=document.createElement('canvas');glass.className='cv-glass';glass.hidden=true;glass.tabIndex=0;glass.setAttribute('aria-label','비교 이미지. 겹쳐보기에서 드래그 또는 방향키로 디자인 이동');host.append(glass);
 const dialog=document.createElement('dialog');dialog.className='cv-dialog';dialog.innerHTML='<div class="s1-modal-inset"><header><b>부분 확대 비교</b><button type="button">닫기</button></header><p class="cv-help">같은 배율로 놓고, 위아래로 밀린 만큼만 맞춘 조각입니다.</p><div class="cv-parts"><section><p>디자인</p><canvas></canvas></section><section><p>개발</p><canvas></canvas></section></div></div>';document.body.append(dialog);dialog.querySelector('button').onclick=()=>dialog.close();
 const hover=document.createElement('div');hover.className='cv-hover';hover.hidden=true;hover.innerHTML='<div class="cv-parts"><section><p>디자인</p><canvas></canvas></section><section><p>개발</p><canvas></canvas></section></div>';document.body.append(hover);
 const pop=document.createElement('div');pop.className='cv-hover cv-pop';pop.hidden=true;pop.innerHTML='<div class="cv-pop-head"><b class="cv-pop-title">비교</b><button type="button" class="cv-pop-x" aria-label="닫기">닫기</button></div><p class="cv-pop-note" hidden></p><div class="cv-parts"><section><p>디자인</p><canvas></canvas></section><section><p>개발</p><canvas></canvas></section></div>';document.body.append(pop);
 pop.querySelector('.cv-pop-x').onclick=()=>{pop.hidden=true;};
 const 색=(n,f)=>{const x=getComputedStyle(document.documentElement).getPropertyValue(n).trim();return x||f;};   // 캔버스는 var(...)를 못 읽는다 — 값으로 풀어 준다
 let lastPt={x:innerWidth/2,y:innerHeight/2};
 document.addEventListener('pointerdown',e=>{lastPt={x:e.clientX,y:e.clientY};if(!pop.hidden&&!pop.contains(e.target))pop.hidden=true;},true);
 document.addEventListener('keydown',e=>{if(e.key!=='Escape')return;pop.hidden=true;if(mode==='crop')setMode('side');});   // 부분 확대는 Esc 로 빠져나온다
 // 누른 자리에 그대로 띄우면 그 카드의 글을 덮는다 — 카드를 피해 옆(넓은 쪽)에 둔다(river 2026-09-16)
 function placePop(avoid){pop.hidden=false;pop.style.left='0px';pop.style.top='0px';const r=pop.getBoundingClientRect();
  let left=null;
  const a=avoid&&avoid.getBoundingClientRect?avoid.getBoundingClientRect():null;
  if(a&&a.width){
   const 왼자리=a.left-12,오른자리=innerWidth-a.right-12;
   if(왼자리>=r.width+12)left=Math.max(12,a.left-12-r.width);
   else if(오른자리>=r.width+12)left=Math.min(innerWidth-r.width-12,a.right+12);
  }
  if(left===null)left=Math.max(12,Math.min(innerWidth-r.width-12,lastPt.x-r.width/2));
  let top;
  if(a&&a.width)top=Math.min(innerHeight-r.height-12,Math.max(12,a.top));   // 카드 옆이면 카드 머리에 맞춘다
  else{top=lastPt.y-r.height-16;if(top<12)top=Math.min(innerHeight-r.height-12,lastPt.y+22);}
  pop.style.left=left+'px';pop.style.top=Math.max(12,top)+'px';}
 let mode='side',dx=0,dy=0,start=null,autoDy=null,userSet=false;
 const key='qa-view-offset:'+location.pathname+location.search+':'+d.getAttribute('src')+':'+v.getAttribute('src');
 try{const p=JSON.parse(localStorage.getItem(key));if(p&&Number.isFinite(p.x)&&Number.isFinite(p.y)){dx=p.x;dy=p.y;userSet=true;}}catch(e){}   // 사람이 맞춰 둔 자리가 있으면 그것이 이긴다
 const slider=tools.querySelector('input');
 function save(){userSet=true;try{localStorage.setItem(key,JSON.stringify({x:dx,y:dy}));}catch(e){}}
 function fit(){const w=host.clientWidth,h=host.clientHeight,s=Math.min(w/v.naturalWidth,h/v.naturalHeight);return {w,h,s,x:(w-v.naturalWidth*s)/2,y:(h-v.naturalHeight*s)/2};}
 function paint(){if(!v.naturalWidth||!d.naturalWidth)return;const f=fit();glass.width=f.w;glass.height=f.h;const c=glass.getContext('2d');if(mode==='over'){c.globalAlpha=Number(slider.value)/100;const scale=v.naturalWidth/d.naturalWidth;c.drawImage(d,f.x+dx*f.s,f.y+dy*f.s,v.naturalWidth*f.s,d.naturalHeight*scale*f.s);}if(mode==='crop'&&start?.end){c.strokeStyle=색('--color-action-primary-default','#2563eb');c.lineWidth=2;c.strokeRect(start.p.x,start.p.y,start.end.x-start.p.x,start.end.y-start.p.y);}}
 function setMode(m){mode=m;hover.hidden=true;start=null;pair.classList.toggle('cv-merged',m==='over');glass.hidden=m==='side';glass.style.cursor=m==='crop'?'crosshair':'move';tools.querySelector('label').hidden=m!=='over';tools.querySelector('[data-reset]').hidden=m!=='over';tools.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===m||(b.dataset.mode==='side'&&m==='crop'))));requestAnimationFrame(paint);}
 tools.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode==='crop'&&mode==='crop'?'side':b.dataset.mode));slider.oninput=paint;tools.querySelector('[data-reset]').onclick=()=>{dx=0;dy=autoDy||0;userSet=false;try{localStorage.removeItem(key);}catch(e){}paint();};   // 자동으로 맞춘 자리로 되돌린다
 function point(e){const r=glass.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top};}
 function blankCanvas(c){try{const g=c.getContext('2d'),n=Math.min(48,c.width),m=Math.min(48,c.height);
  const t=document.createElement('canvas');t.width=n;t.height=m;const tg=t.getContext('2d');tg.drawImage(c,0,0,n,m);
  const d=tg.getImageData(0,0,n,m).data;for(let i=0;i<d.length;i+=4){if(d[i]<236||d[i+1]<236||d[i+2]<236)return false;}return true;}catch(e){return false;}}
 // ── 밀린 자리 가늠: 두 그림의 '가로줄 무늬'를 견줘, 이 요소가 시안에서 몇 줄 밀렸는지 찾는다 ──
 const PW=320;let profCache=null,shiftCache=null;
 function profileOf(im){const h=Math.max(1,Math.round(im.naturalHeight*PW/im.naturalWidth));
  const c=document.createElement('canvas');c.width=PW;c.height=h;const g=c.getContext('2d',{willReadFrequently:true});
  g.fillStyle=색('--color-surface-default','#fff');g.fillRect(0,0,PW,h);g.drawImage(im,0,0,PW,h);
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
 function bestIn(r0,n,lo,hi){   // 시안 무늬에서 '밀림 lo~hi' 만큼만 훑어 가장 닮은 자리
  const P=profiles();if(!P.d||!P.v)return null;
  const t0=Math.max(0,Math.ceil(r0+lo)),t1=Math.min(P.d.h-n,Math.floor(r0+hi));
  let best=null;
  for(let t=t0;t<=t1;t++){const sc=zncc(P.v.p,r0,P.d.p,t,n);if(!best||sc>best.sc)best={sc:sc,g:t-r0};}
  return best;}
 function inkEdges(p,h){   // 잉크가 있는 첫 줄·마지막 줄. 푸터 잔글씨는 아주 옅어서 문턱을 낮게 잡는다.
  let max=0;for(let i=0;i<h;i++)if(p[i]>max)max=p[i];
  const thr=max*0.01;let a=-1,b=-1;
  for(let i=0;i<h;i++)if(p[i]>thr){if(a<0)a=i;b=i;}
  return{a:a,b:b};}
 // 화면 한 벌에 한 번만 구하는 '이 화면은 이만큼 밀렸다' 후보들. 낱개 요소가 시안 전체를 헤매지 않게 갈 곳을 미리 좁힌다.
 // zone: 'top'=위쪽 내용이 기준, 'bottom'=바닥이 기준(두 그림 높이가 다르면 푸터는 '바닥에서 몇 줄'에 있다), 'any'=화면 전체.
 let dyCache;
 function grayOf(draw,w,h){const t=document.createElement('canvas');t.width=w;t.height=h;
  const g=t.getContext('2d',{willReadFrequently:true});g.fillStyle=색('--color-surface-default','#fff');g.fillRect(0,0,w,h);draw(g);
  const q=t.getContext('2d').getImageData(0,0,w,h).data,out=new Float32Array(w*h);
  for(let i=0;i<out.length;i++)out[i]=(q[i*4]+q[i*4+1]+q[i*4+2])/3;return out;}
 function ncc2(a,b){const n=a.length;let sa=0,sb=0;for(let i=0;i<n;i++){sa+=a[i];sb+=b[i];}
  const ma=sa/n,mb=sb/n;let p=0,x=0,y=0;
  for(let i=0;i<n;i++){const u=a[i]-ma,w=b[i]-mb;p+=u*w;x+=u*u;y+=w*w;}
  return (x<1e-6||y<1e-6)?0:p/Math.sqrt(x*y);}
 function overlayDy(){   // 시안을 위아래로 훑어 그림이 가장 잘 겹치는 자리(개발 그림 픽셀). 뚜렷하지 않으면 0
  if(dyCache!==undefined)return dyCache;
  if(!d.naturalWidth||!v.naturalWidth)return 0;
  try{
   const w=240,h=Math.max(40,Math.round(w*v.naturalHeight/v.naturalWidth)),ky=h/v.naturalHeight,sc=v.naturalWidth/d.naturalWidth;
   const dev=grayOf(g=>g.drawImage(v,0,0,w,h),w,h);
   const des=t=>ncc2(grayOf(g=>g.drawImage(d,0,t*ky,w,d.naturalHeight*sc*ky),w,h),dev);
   const lim=Math.round(v.naturalHeight*0.4),step=Math.max(2,Math.round(lim/40));
   const base=des(0);let best={t:0,s:base};
   for(let t=-lim;t<=lim;t+=step){const s=des(t);if(s>best.s)best={t:t,s:s};}
   const fine=Math.max(1,Math.round(step/4));
   for(let t=best.t-step;t<=best.t+step;t+=fine){const s=des(t);if(s>best.s)best={t:t,s:s};}
   dyCache=(best.s<0.2||best.s<base+0.05)?0:best.t;   // 어느 자리나 비슷하면 흔들지 않는다
  }catch(e){dyCache=0;}
  return dyCache;}
 function pageShifts(){
  if(shiftCache)return shiftCache;
  const P=profiles();if(!P.d||!P.v)return[];
  const out=[],seen=[];
  function push(g,zone){if(!isFinite(g))return;g=Math.round(g);
   if(seen.some(o=>Math.abs(o-g)<=2))return;seen.push(g);out.push({g:g,zone:zone});}
  const t=overlayDy();if(t)push(-t*P.v.k,'any');                 // 그림째 훑어 찾은 화면 전체 자리
  const al=window.qaAlign;
  if(al&&al.s)push((al.ty-(al.ctop||0)*al.s)*P.d.k,'any');   // 검수기가 잰 화면 전체 맞춤값(잘라낸 위쪽 띠만큼 되돌려서)
  const head=bestIn(0,Math.min(Math.max(8,Math.round(P.v.h/2)),P.d.h,P.v.h),-P.d.h,P.d.h);
  if(head&&head.sc>0.3)push(head.g,'top');                   // 위쪽 절반으로 잰 밀림
  const fh=Math.max(8,Math.round(P.v.h/3)),fr=Math.max(0,P.v.h-fh);
  const foot=bestIn(fr,Math.min(P.v.h-fr,P.d.h),-P.d.h,P.d.h);
  if(foot&&foot.sc>0.3)push(foot.g,'bottom');                // 아래쪽 1/3으로 잰 밀림
  const ed=inkEdges(P.d.p,P.d.h),ev=inkEdges(P.v.p,P.v.h);
  if(ed.b>=0&&ev.b>=0)push(ed.b-ev.b,'bottom');              // 바닥(마지막 잉크 줄)끼리 맞춘 밀림 — 글자가 옅어 무늬가 안 잡힐 때의 버팀목
  push(P.d.h-P.v.h,'bottom');                                // 두 그림의 아래끝끼리 맞춘 밀림(배경이 흰색이 아닐 때의 버팀목)
  if(ed.a>=0&&ev.a>=0)push(ed.a-ev.a,'top');                 // 머리(첫 잉크 줄)끼리 맞춘 밀림
  push(0,'any');
  shiftCache=out;return out;}
 function guessShift(devY,devH){   // 개발 그림의 그 줄이 시안에서 몇 줄(320폭 기준) 밀렸는지. 못 찾으면 null
  const P=profiles();if(!P.d||!P.v)return null;
  const mods=pageShifts();if(!mods.length)return null;
  const pad=Math.max(10,Math.round(P.v.h*0.04));
  let r1=Math.min(P.v.h,Math.round((devY+devH)*P.v.k)+pad),r0=Math.max(0,Math.round(devY*P.v.k)-pad);
  if(r1-r0<12){r1=Math.min(P.v.h,r0+12);r0=Math.max(0,r1-12);}   // 너무 얇은 창은 넓혀서 본다
  const n=r1-r0;if(n<8||n>P.d.h)return null;
  const R=Math.max(4,Math.round(P.d.h*0.02));   // 후보 언저리만 다듬는다
  let best=null;
  for(const m of mods){const b=bestIn(r0,n,m.g-R,m.g+R);if(b&&(!best||b.sc>best.sc))best=b;}
  if(best&&best.sc>0.5)return best.g;
  // 창이 밋밋해 고를 수 없으면 옮기지 않는다 — 그 자리(위/아래)에 맞는 화면 전체 값을 그대로 쓴다.
  const zone=(r0+r1)/2>P.v.h*2/3?'bottom':'top';
  const fall=mods.find(m=>m.zone===zone)||mods[0];
  return fall?fall.g:null;}
 const shiftMemo=new Map();
 function shiftFor(devY,devH){const k=Math.round(devY/8)+'x'+Math.round(devH/8);   // 마우스를 움직일 때마다 다시 재지 않게 기억해 둔다
  if(shiftMemo.has(k))return shiftMemo.get(k);const g=guessShift(devY,devH);shiftMemo.set(k,g);return g;}
 const SN=96,SM=64,boxMemo=new Map();
 function cropGray(im,x,y,w,h){return grayOf(g=>g.drawImage(im,x,y,w,h,0,0,SN,SM),SN,SM);}
 function designBoxFor(bx,by,bw,bh){   // 개발 그림의 이 자리가 시안에서는 어디인지 — 후보를 두고 그림째 견줘 고른다
  const mk=[bx,by,bw,bh].map(n=>Math.round(n/8)).join(',');if(boxMemo.has(mk))return boxMemo.get(mk);
  const P=profiles(),al=window.qaAlign,sx=d.naturalWidth/v.naturalWidth,t=overlayDy();
  const wide=t?(by-t)*sx:((al&&al.s)?(by-(al.ty-(al.ctop||0)*al.s))/al.s:null);   // 화면 전체로 본 자리
  const cand=[],add=y=>{if(isFinite(y)&&y>-bh*sx&&y<d.naturalHeight&&!cand.some(c=>Math.abs(c-y)<3))cand.push(y);};
  if(P.d&&P.v){const g=shiftFor(by,bh);if(g!==null&&g!==undefined)add((by*P.v.k+g)/P.d.k);
   pageShifts().forEach(m=>add((by*P.v.k+m.g)/P.d.k));}
  if(wide!==null)add(wide);add(by*sx);
  if(!cand.length)return null;
  let best=null;
  try{const dev=cropGray(v,bx,by,bw,bh);
   const at=y=>{const s=ncc2(cropGray(d,bx*sx,y,bw*sx,bh*sx),dev);if(!best||s>best.s)best={y:y,s:s};};
   cand.forEach(at);
   const mid=(wide!==null?wide:by*sx),R=Math.max(100,d.naturalHeight*0.12),step=Math.max(3,Math.round(bh*0.1));
   for(let y=mid-R;y<=mid+R;y+=step)at(y);   // 화면 전체 자리 언저리를 훑는다(맨 위·맨 아래처럼 잘린 자리는 후보가 빗나간다)
   for(const fine of [Math.max(1,Math.round(step/3)),1]){const c=best.y;for(let k=-3;k<=3;k++)if(k)at(c+k*fine);}   // 고른 자리를 두 번 다듬는다
  }catch(e){}
  const y=(best&&best.s>0.25)?best.y:(wide!==null?wide:cand[0]);   // 그림이 밋밋해 못 고르면 화면 전체 값으로
  const box={x:bx*sx,y:y,w:bw*sx,h:bh*sx};boxMemo.set(mk,box);return box;}
 function pageDy(){   // 겹쳐보기를 처음 열 때 시안을 얼마나 내려/올려 둘지(개발 그림 픽셀)
  const t=overlayDy();if(t)return t;
  const al=window.qaAlign;if(al&&al.s)return al.ty-(al.ctop||0)*al.s;
  return null;}
 // 시안 쪽도 **개발과 똑같은 넓이**를 잘라 온다 — 시안 요소 상자 크기를 그대로 쓰면 둘이 다른 배율로 보인다.
 // (개발 1px = 시안 scale px. 가운데만 시안 요소에 맞추고, 잘라 오는 넓이는 개발 쪽에서 받아온다.)
 function 같은배율(b,w,h,scale){const cw=w*scale,ch=h*scale;return{x:b.x+b.w/2-cw/2,y:b.y+b.h/2-ch/2,w:cw,h:ch};}
 function crop(box,target=dialog,dbox){if(!v.naturalWidth||!d.naturalWidth)return false;const x=Math.max(0,box.x),y=Math.max(0,box.y),w=Math.min(v.naturalWidth,box.x+box.w)-x,h=Math.min(v.naturalHeight,box.y+box.h)-y;if(w<3||h<3)return false;
 const scale=d.naturalWidth/v.naturalWidth;const factor=Math.min(1400/w,1400/h,Math.max(1,400/w)),outW=Math.max(1,Math.round(w*factor)),outH=Math.max(1,Math.round(h*factor));
 const db=dbox?같은배율(dbox,w,h,scale):null;   // 시안 쪽 자리를 알면 그 자리를 자른다(위아래로 밀린 화면도 제 짝끼리 보이게)
 window.qaLastCrop={dev:{x:x,y:y,w:w,h:h},design:db};   // 어느 자리를 잘라 왔는지 — 콘솔·검사판에서 확인용
 target.querySelectorAll('canvas').forEach((c,i)=>{c.width=outW;c.height=outH;const ctx=c.getContext('2d');ctx.fillStyle=색('--color-surface-default','#fff');ctx.fillRect(0,0,outW,outH);
  if(i)ctx.drawImage(v,x,y,w,h,0,0,outW,outH);
  else if(db)ctx.drawImage(d,db.x,db.y,db.w,db.h,0,0,outW,outH);
  else ctx.drawImage(d,(x-dx)*scale,(y-dy)*scale,w*scale,h*scale,0,0,outW,outH);});
 if(target===dialog&&!dialog.open)dialog.showModal();return true;}
 function showHover(e){const f=fit(),p=point(e);if(p.x<f.x||p.y<f.y||p.x>f.x+v.naturalWidth*f.s||p.y>f.y+v.naturalHeight*f.s){hover.hidden=true;return;}const w=Math.min(v.naturalWidth,92/f.s),h=Math.min(v.naturalHeight,63/f.s);const bx=Math.max(0,Math.min(v.naturalWidth-w,(p.x-f.x)/f.s-w/2)),by=Math.max(0,Math.min(v.naturalHeight-h,(p.y-f.y)/f.s-h/2));crop({x:bx,y:by,w,h},hover,designBoxFor(bx,by,w,h));hover.hidden=false;const r=hover.getBoundingClientRect();hover.style.left=Math.max(12,Math.min(innerWidth-r.width-12,e.clientX+20))+'px';hover.style.top=Math.max(12,e.clientY+r.height+24<innerHeight?e.clientY+20:e.clientY-r.height-20)+'px';}
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
  const ref=window.qaDesignRef,db=(window.qaDesignBox||{})[id];
  let dbox=null;
  if(db&&ref&&ref.w){const kd=d.naturalWidth/ref.w;dbox={x:(db[0]-20)*kd,y:(db[1]-20)*kd,w:(db[2]+40)*kd,h:(db[3]+40)*kd};}
  else dbox=designBoxFor(bx,by,bw,bh);   // 밀린 만큼 가늠해서, 안 되면 화면 전체 맞춤값으로
  if(!crop({x:bx,y:by,w:bw,h:bh},pop,dbox))return;
  const cs=pop.querySelectorAll('canvas'),note=pop.querySelector('.cv-pop-note');
  const 시안빔=blankCanvas(cs[0]),개발빔=blankCanvas(cs[1]);
  note.textContent=시안빔&&개발빔?'이 자리는 두 그림 모두 비어 있어요 — 핀 자리와 올린 그림이 어긋났을 수 있어요.'
   :개발빔?'개발 그림의 이 자리는 비어 있어요 — 핀 자리가 실제 요소와 어긋났을 수 있어요.'
   :시안빔?'시안의 이 자리는 비어 있어요 — 개발에만 있는 요소이거나, 자리를 못 맞췄을 수 있어요.':'';
  note.hidden=!note.textContent;
  placePop(card);
  return{dev:{x:bx,y:by,w:bw,h:bh},design:dbox};};   // 어느 자리를 잘라 왔는지 — 콘솔·검사판에서 확인용
 function reload(){profCache=null;shiftCache=null;dyCache=undefined;shiftMemo.clear();boxMemo.clear();autoDy=pageDy();if(!userSet)dy=autoDy||0;paint();}   // 그림이 바뀌면 줄무늬도 다시 잰다
 new ResizeObserver(paint).observe(host);d.addEventListener('load',reload);v.addEventListener('load',reload);
 if(d.complete&&v.complete)reload();setMode('side');
})();
'''
