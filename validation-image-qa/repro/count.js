// 결과 세기·비교. 사용: node count.js <접두사> [기준 접두사]
const fs=require('fs');const S=['board','vehicle','dash','door','stay','findid','login','table','codes','route'];
const [P,B]=process.argv.slice(2);
function load(p,s){try{return JSON.parse(fs.readFileSync(`${p}_${s}.json`,'utf8'));}catch(e){return null;}}
const see=o=>o.candidates.filter(c=>c.status!=='variable'&&c.status!=='excluded');
const key=c=>[c.kind,c.label,(c.designNodeIds||[]).join(','),c.designBox.x,c.designBox.y].join('|');
let tot=0,btot=0;
console.log('화면'.padEnd(8),'볼것','위치','제외','띠','새로/사라짐','띠 목록');
for(const s of S){const o=load(P,s);if(!o){console.log(s.padEnd(8),'(없음)');continue;}
  const v=see(o),pos=v.filter(c=>/위치/.test(c.label)).length,ex=o.candidates.filter(c=>c.status==='excluded').length;
  const bands=(o.range&&o.range.bands||[]).map(b=>`${b.edge==='top'?'위':'아래'}:${b.name}(${Math.round(b.box.h)}px,${b.reason})`).join(' · ');
  let diff='';if(B){const bo=load(B,s);if(bo){const bk=new Set(see(bo).map(key)),vk=new Set(v.map(key));const nw=[...vk].filter(k=>!bk.has(k)).length,gone=[...bk].filter(k=>!vk.has(k)).length;diff=`+${nw}/-${gone}`;btot+=see(bo).length;}}
  tot+=v.length;console.log(s.padEnd(8),String(v.length).padStart(3),String(pos).padStart(3),String(ex).padStart(3),String((o.range&&o.range.bands||[]).length).padStart(2),diff.padEnd(10),bands);}
console.log('합계'.padEnd(8),tot,B?`(기준 ${btot})`:'');
