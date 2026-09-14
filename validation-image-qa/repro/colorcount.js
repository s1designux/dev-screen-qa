const fs=require("fs"),p=process.argv[2];
const names=["board","vehicle","dash","door","stay","findid","login","table","codes","route"];
let tot=0,col=0;const rows=[];
for(const n of names){const f=`/Users/designgroup_02/dev-screen-qa-color/validation-image-qa/repro/${p}_${n}.json`;
 if(!fs.existsSync(f)){rows.push([n,"?","?"]);continue;}
 const j=JSON.parse(fs.readFileSync(f,"utf8"));
 const see=j.candidates.filter(c=>c.status!=="variable"&&c.status!=="excluded");
 const c=see.filter(x=>/색상/.test(x.label||""));tot+=see.length;col+=c.length;rows.push([n,see.length,c.length]);}
rows.forEach(r=>console.log(String(r[0]).padEnd(8),"볼것",String(r[1]).padStart(4),"색",String(r[2]).padStart(4)));
console.log("합계 볼것",tot,"색",col);
