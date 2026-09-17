// 화면별 [후보 · 숨김 · 볼 것] 세기. 쓰기: node 열넷세기.js <앞> [견줄앞]
const fs=require('fs');
const 화면=['board','vehicle','dash','door','stay','findid','login','table','codes','route','home1','home2','home3','home4','appkbd'];
const [앞,전]=[process.argv[2],process.argv[3]];
function 재기(p,s){const f=`${p}_${s}.json`;if(!fs.existsSync(f))return null;
  const c=(JSON.parse(fs.readFileSync(f,'utf8')).candidates)||[];
  return c.length-c.filter(k=>k.status==='variable'||k.status==='excluded').length;}
let 합=0,합전=0;
for(const s of 화면){const a=재기(앞,s),b=전?재기(전,s):null;
  if(a==null){console.log(s.padEnd(8),'없음');continue;}
  합+=a; if(b!=null)합전+=b;
  const d=(b!=null)?(a-b===0?'   -':(a-b>0?'  +':'  ')+(a-b)):'';
  console.log(s.padEnd(8),(b!=null?String(b).padStart(5):''),String(a).padStart(5),d);}
console.log('합계'.padEnd(8),(전?String(합전).padStart(5):''),String(합).padStart(5),전?((합-합전>=0?'  +':'  ')+(합-합전)):'');
