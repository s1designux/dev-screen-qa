// 선택된 탭 규칙(#16) 앞뒤 대조 그림. 디자인과 개발화면에서 탭 줄을 같은 크기로 잘라 위아래로 놓는다.
// 사용: node tab_report.js <출력html>
const fs=require('fs');
const b64=p=>'data:image/png;base64,'+fs.readFileSync(p).toString('base64');
// [제목, 설명, 디자인png, 개발png, 자를 폭, 디자인 y, 개발 y, 높이, 왼쪽 자름]
const cases=[
  ['노선관리 — 선택된 탭','디자인은 「노선관리」, 개발화면은 띄어쓰기가 들어간 「노선 관리」로 보입니다. 예전에는 “요소가 없어졌다”로 올라와 무슨 차이인지 알 수 없었습니다.',
   'design_route_1920x1080.png','dev_route_1920x1080.png',760,132,146,46,140],
  ['체류시간 — 선택된 탭 바탕','탭이 옆으로 밀려 있을 뿐 바탕색은 같습니다. 예전에는 “색이 다르다”고 잘못 올라왔습니다.',
   'design_stay_1920x1080.png','dev_stay_1920x1081.png',760,134,143,44,140],
];
const panel=(t,d,dp,vp,w,dy,vy,h,lx)=>`<section>
<h2>${t}</h2><p>${d}</p>
<div class=pair>
  <figure><figcaption>디자인</figcaption><div class=win style="width:${w}px;height:${h}px"><img src="${b64(dp)}" style="margin:${-dy}px 0 0 ${-lx}px"></div></figure>
  <figure><figcaption>개발화면</figcaption><div class=win style="width:${w}px;height:${h}px"><img src="${b64(vp)}" style="margin:${-vy}px 0 0 ${-lx}px"></div></figure>
</div></section>`;
fs.writeFileSync(process.argv[2],`<!doctype html><meta charset=utf-8><title>선택된 탭 대조</title>
<style>body{font:15px/1.7 system-ui,-apple-system,sans-serif;margin:28px;background:#fff;color:#111}
h1{font-size:20px;margin:0 0 6px}h2{font-size:16px;margin:26px 0 4px}
p{color:#555;margin:0 0 12px;max-width:760px}
figure{margin:0}figcaption{font-weight:700;font-size:13px;color:#333;margin:0 0 4px}
.pair{display:flex;flex-direction:column;gap:10px}
.win{overflow:hidden;border:1px solid #d8d8d8;border-radius:4px;background:#fff}
.win img{display:block}</style>
<h1>선택된 탭 — 자리는 묻지 않고 글자만 대조</h1>
<p>탭 줄은 열린 탭 수에 따라 가로로 움직입니다. 그래서 선택된 탭은 탭 줄 안에서 찾아 <b>글자만</b> 견줍니다.</p>
${cases.map(c=>panel(...c)).join('')}`);
console.log('wrote',process.argv[2]);
