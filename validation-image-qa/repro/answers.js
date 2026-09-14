const fs=require("fs");const p=process.argv[2];
const j=JSON.parse(fs.readFileSync(`/Users/designgroup_02/dev-screen-qa-color/validation-image-qa/repro/${p}_stay.json`,"utf8"));
const see=j.candidates.filter(c=>c.status!=="variable"&&c.status!=="excluded");
const words=["입문날짜","입문시간","출문날짜","출문시간","통근버스 운영 시스템","운영 관리","과속여부"];
let ok=0;words.forEach(w=>{const hit=see.filter(c=>((c.detail||"")+" "+(c.designValues||"")).includes(w));if(hit.length)ok++;
 console.log((hit.length?"O":"X"),w,hit.map(c=>"#"+c.no+"["+c.kind+"]").join(" "));});
console.log("정답 생존",ok+"/7");
