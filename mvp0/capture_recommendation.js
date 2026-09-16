(function(){
 const p=document.getElementById('capture-picker');if(!p)return;
 // 예전 촬영(접어 둔 것)은 순위를 매기지 않는다 — 고르는 것은 마지막 촬영 사진이다.
 const choices=[...p.querySelectorAll('input[name=capture]')].filter(x=>!x.closest('label').classList.contains('cap-old'));
 const preview=p.querySelector('#plan-capture-preview'), note=p.querySelector('.recommendation-status');
 let chosen=choices.find(x=>x.checked), automatic=null, userSelected=false;
 function show(input){if(input)preview.src=input.dataset.src;}
 p.addEventListener('change',e=>{if(e.target.name==='capture'){userSelected=true;show(e.target);}});
 p.addEventListener('close',()=>{const input=chosen||automatic;if(input){input.checked=true;show(input);}userSelected=false;});
 // 이미지 한 장을 '잉크 지도'로 줄인다: 기기 막대를 뺀 뒤 흑백 64x128로 눌러 담고, 평균 밝기를 빼 둔다.
 // 평균을 빼면 전체가 밝고 어두운 차이가 아니라 '무엇이 어디에 그려져 있나'만 남는다.
 const W=64,H=128;
 async function sample(src){
  const img=new Image();img.src=src;await img.decode();
  const c=document.createElement('canvas');c.width=W;c.height=H;
  const ctx=c.getContext('2d',{willReadFrequently:true});
  ctx.fillStyle='#fff';ctx.fillRect(0,0,W,H);
  ctx.drawImage(img,0,img.height*.045,img.width,img.height*.91,0,0,W,H);
  const d=ctx.getImageData(0,0,W,H).data, v=new Float32Array(W*H);
  for(let i=0,j=0;i<d.length;i+=4,j++)v[j]=1-(d[i]*.299+d[i+1]*.587+d[i+2]*.114)/255;
  let m=0;for(const x of v)m+=x;m/=v.length;
  for(let j=0;j<v.length;j++)v[j]-=m;
  return v;
 }
 function overlap(a,b,shift){
  let s=0,na=0,nb=0;
  for(let y=0;y<H;y++){const yb=y+shift;if(yb<0||yb>=H)continue;
   for(let x=0;x<W;x++){const u=a[y*W+x],w=b[yb*W+x];s+=u*w;na+=u*u;nb+=w*w;}}
  return na&&nb?s/Math.sqrt(na*nb):-1;
 }
 // 시안과 촬영본은 위아래로 조금씩 밀려 있다 — 제일 잘 겹치는 자리를 찾아 그 값으로 견준다.
 function distance(a,b){let best=-1;for(let sh=-10;sh<=10;sh+=2){const v=overlap(a,b,sh);if(v>best)best=v;}return 1-best;}
 (async()=>{
  if(!choices.length){note.textContent='등록된 개발 캡처가 없습니다. 디자인 시안과 같은 상태로 촬영해 주세요.';return;}
  try{
   const design=await sample(p.querySelector('.design-original').src);
   const scores=await Promise.all(choices.map(async input=>{try{return {input,score:distance(design,await sample(input.dataset.src))};}catch{return {input,score:Infinity};}}));
   scores.sort((a,b)=>a.score-b.score);
   const valid=scores.filter(x=>Number.isFinite(x.score));
   if(!valid.length)throw Error('no images');
   // 지금 비교 중인 사진은 늘 맨 위에 두고 순위를 매기지 않는다.
   let rank=0;
   scores.forEach(x=>{
    const label=x.input.closest('label'), badge=label.querySelector('.rank');
    if(x.input===chosen){label.style.order=-1;if(badge)badge.textContent='비교 중';return;}
    label.style.order=++rank;
    if(badge)badge.textContent=Number.isFinite(x.score)?`${rank}순위`:'이미지 확인 필요';
   });
   automatic=valid[0].input;
   if(!chosen&&!userSelected){automatic.checked=true;show(automatic);}
   note.textContent='형태·색상 차이가 적은 순서입니다. 글자·입력 상태가 같은지는 확인해 주세요.';
   const pane=document.querySelector('.cols .pane:nth-child(2) .canvas');
   if(!chosen&&pane&&!pane.querySelector('img.capimg')){
    const img=document.createElement('img');img.className='capimg';img.alt='자동 추천 개발 캡처 · 미확인';img.src=automatic.dataset.src;
    pane.querySelector('.ph')?.remove();pane.prepend(img);
    const tag=document.createElement('p');tag.className='capture-suggestion';tag.textContent='추천 후보 · '+automatic.dataset.name+' · 아직 연결하지 않았습니다';pane.parentElement.insertBefore(tag,pane);
   }
  }catch{note.textContent='자동 추천을 계산하지 못했습니다. 아래 캡처를 직접 선택해 주세요.';}
 })();
})();
