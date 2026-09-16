// 체류시간 정답 생존 확인. 사용: node answers_check.js <결과 json>
const fs=require('fs');const o=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const A=JSON.parse(fs.readFileSync('answers_stay.json','utf8'));
const el=JSON.parse(fs.readFileSync('elements_stay_full.json','utf8'));const rows=el.rows.map(r=>{const x={};el.cols.forEach((c,i)=>x[c]=r[i]);return x;});
let alive=0;for(const a of A.answers){const ids=rows.filter(r=>r.kind==='text'&&String(r.text||'').trim()===a.design).map(r=>r.id);
  const hits=o.candidates.filter(c=>(c.designNodeIds||[]).some(id=>ids.includes(id)));
  const vis=hits.filter(c=>c.status!=='variable'&&c.status!=='excluded');
  const ok=vis.length>0;if(ok)alive++;
  console.log((ok?'✓':'✗'),`#${a.no}`,a.design,'→',vis.map(c=>`#${c.no} ${c.label}`).join(' / ')||(hits.length?`(접힘: ${hits.map(c=>c.status+':'+c.policy).join(',')})`:'(후보 없음)'));}
console.log(`정답 생존 ${alive}/${A.answers.length}`);
