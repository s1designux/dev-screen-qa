(function(){
 const p=document.getElementById('capture-picker');if(!p)return;
 const choices=[...p.querySelectorAll('input[name=capture]')];
 const preview=p.querySelector('#plan-capture-preview'), note=p.querySelector('.recommendation-status');
 let chosen=choices.find(x=>x.checked), automatic=null, userSelected=false;
 function show(input){if(input)preview.src=input.dataset.src;}
 p.addEventListener('change',e=>{if(e.target.name==='capture'){userSelected=true;show(e.target);}});
 p.addEventListener('close',()=>{const input=chosen||automatic;if(input){input.checked=true;show(input);}userSelected=false;});
 async function sample(src){
  const img=new Image();img.src=src;await img.decode();
  const c=document.createElement('canvas');c.width=96;c.height=160;
  const ctx=c.getContext('2d',{willReadFrequently:true});
  // Exclude device bars; normalize resolution, retain text and field edges.
  ctx.drawImage(img,0,img.height*.045,img.width,img.height*.91,0,0,96,160);
  return ctx.getImageData(0,0,96,160).data;
 }
 function distance(a,b){
  let total=0,weight=0;
  for(let i=0;i<a.length;i+=4){
   const ink=1-Math.min(a[i]+a[i+1]+a[i+2],b[i]+b[i+1]+b[i+2])/765;
   const w=.05+ink;total+=w*(Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2]))/765;weight+=w;
  }return total/weight;
 }
 (async()=>{
  if(!choices.length){note.textContent='등록된 개발 캡처가 없습니다. 디자인 시안과 같은 상태로 촬영해 주세요.';return;}
  try{
   const design=await sample(p.querySelector('.design-original').src);
   const scores=await Promise.all(choices.map(async input=>{try{return {input,score:distance(design,await sample(input.dataset.src))};}catch{return {input,score:Infinity};}}));
   scores.sort((a,b)=>a.score-b.score);
   const valid=scores.filter(x=>Number.isFinite(x.score));
   if(!valid.length)throw Error('no images');
   scores.forEach((x,i)=>{const label=x.input.closest('label');label.style.order=i;const badge=label.querySelector('.rank');if(badge)badge.textContent=Number.isFinite(x.score)?`${i+1}순위`:'이미지 확인 필요';});
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
