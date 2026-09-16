// 플러그인 UI 엔진을 실제 이미지로 헤드리스 크롬에서 돌려 후보 목록과 오버레이 PNG를 만든다.
// 사용: node run.js [uiHtmlPath] [outPrefix]
const fs = require('fs'), path = require('path'), cp = require('child_process');
const here = __dirname;
const uiPath = process.argv[2] || path.resolve(here, '../../engine/ui.html');
const outPrefix = process.argv[3] || 'out';
const ui = fs.readFileSync(fs.existsSync(uiPath) ? uiPath : '/Users/designgroup_02/dev-screen-qa/engine/ui.html', 'utf8');
const el = JSON.parse(fs.readFileSync(path.join(here, process.env.ELEMENTS_JSON || 'elements.json'), 'utf8'));
// 포털 자료를 그대로 쓰는 길 — elements 파일에 native 배열이 있으면 그대로 쓴다(값을 다시 짜맞추지 않는다).
const elements = el.native ? el.native : el.rows.map(r => {
  const o = {}; el.cols.forEach((c, i) => o[c] = r[i]);
  const e = { id: o.id, name: o.name || o.id, type: o.type, kind: o.kind, depth: o.depth, parentId: o.parentId, parentType: null, box: { x: o.x, y: o.y, w: o.w, h: o.h }, text: o.text || '' };
  if (o.chain) e.chain = o.chain; if (o.propRef) e.propRef = o.propRef; // 역할 판단용(있을 때만)
  if (o.kind === 'text') e.values = { text: o.text, fontSize: o.fontSize, fontWeight: o.fontWeight, fontFamily: 'Pretendard Variable', fontStyle: '', lineHeight: '130%', color: o.color, textAlign: 'LEFT' };
  else e.values = { width: o.w, height: o.h, fill: o.fill, stroke: o.stroke, strokeWidth: o.strokeWidth, radius: o.radius, opacity: 1 };
  return e;
});
const designB64 = fs.readFileSync(path.join(here, process.env.DESIGN_PNG || 'design_1920x1080.png')).toString('base64');
const devB64 = fs.readFileSync(path.join(here, process.env.DEV_PNG || 'dev_1920x934.png')).toString('base64');

let patched = ui;
if (process.env.DIFF_MAX) patched = patched.replace('var max=360,q=Math.min(max/designImg.width', 'var max=' + process.env.DIFF_MAX + ',q=Math.min(max/designImg.width');
// buildDiff internals
patched = patched.replace('cands.forEach(function(c,i){c.no=i+1;c.id=pairId+"_c"+(i+1);});\n  return cands;',
  'window.__dbg={w:w,h:h,q:q,bandH:bandH,bandDy:Array.from(bandDy),bandVotes:bandVotes,lowerShift:lowerShift,componentShifts:Object.keys(componentShifts).map(function(k){var v=componentShifts[k];return{id:k,dx:v.dx,dy:v.dy,score:v.score,zero:v.zero,box:v.element.box};}),gapMatches:gapMatches.map(function(g){return{a:g.a.element.id,b:g.b.element.id,axis:g.axis,designGap:g.designGap,deltaLogical:g.deltaLogical};}),boxes:boxes};cands.forEach(function(c,i){c.no=i+1;c.id=pairId+"_c"+(i+1);});\n  return cands;');
// textDiff internals
patched = patched.replace('var best=textEdgeMismatch(dE,cE,W,H,textBox,bestDx,localDy+bestDy),moved=Math.abs(bestDx)>=3||Math.abs(bestDy)>=3;',
  'var best=textEdgeMismatch(dE,cE,W,H,textBox,bestDx,localDy+bestDy),moved=Math.abs(bestDx)>=3||Math.abs(bestDy)>=3;(window.__textDbg=window.__textDbg||[]).push({id:e.id,text:e.text,box:textBox,points:points.length,localDy:localDy,zeroMatch:+zeroMatch.toFixed(3),bestMatch:+bestMatch.toFixed(3),bestDx:bestDx,bestDy:bestDy,mismatch:+best.toFixed(3),flagged:(moved||best>.28)&&best<1});');


patched = patched.replace('cands.notices=notices;','cands.notices=notices;window.__ctx=ctx;window.__unitDbg=results.map(function(r){return{pb:r.pb,dx:r.best.dx,dy:r.best.dy,id:r.u.el.id,kind:r.u.kind,text:r.u.el.text,sec:r.sec.el?r.sec.el.id:"root",base:r.base,best:r.best,capRatio:+r.capRatio.toFixed(2),mismatch:+r.mismatch.toFixed(2),moved:r.moved,missing:r.missing,pts:r.pts.length,ncc:r.ncc,exact:r.exact,ts:r.textStats,segInfo:r.segInfo};});');
patched = patched.replace('return boxes.map(function(b){var pad=3','window.__areaBoxes=boxes;window.__areaGrid={cols:cols,rows:rows,q:q};return boxes.map(function(b){var pad=3');
patched = patched.replace('return{segments:segs.length,goodRatio:good/segs.length,','return{segNccs:segs.map(function(g){return [Math.round(g.seg.x),+g.free.toFixed(2),g.offset,+g.ncc.toFixed(2)];}),segments:segs.length,goodRatio:good/segs.length,');
patched = patched.replace('  if(!votes.length)return null;\n  // 세로·가로 둘 다','  window.__anchorVotes=votes.slice();window.__anchorList=anchors.map(function(e){return{id:e.id,text:e.text,box:e.box};});\n  if(!votes.length)return null;\n  // 세로·가로 둘 다');
patched = patched.replace('  var tol=Math.max(3,Math.round(4*lg)),best=null;','  (window.__secVotes=window.__secVotes||[]).push({name:section.el?section.el.name:"root",votes:votes.slice()});\n  var tol=Math.max(3,Math.round(4*lg)),best=null;');
// ANCHOR_MODE=spread: 기준 요소를 화면 전체에서 고루·많이 찾는 실험판(현재 엔진은 맨 위에서 5개만 고른다).
if (process.env.ANCHOR_MODE === 'spread') {
  const cols = Number(process.env.ANCHOR_COLS || 6), rows = Number(process.env.ANCHOR_ROWS || 6);
  const spread = `function pickAnchors(design,excludeBoxes){
  var ex=excludeBoxes||[];
  var cands=(design.elements||[]).filter(function(e){var b=e.box;
    if(ex.some(function(x){return boxContains(x,b);}))return false;
    return b.w>=24&&b.h>=10&&b.w<=design.width*.8&&b.h<=140;});
  // ① 화면에 여러 번 나오는 모양·글자는 기준으로 쓰지 않는다(반복 메뉴·표 데이터에 엉뚱하게 붙는다)
  function key(e){return e.kind==="text"?("t:"+String(e.text||"")):("s:"+Math.round(e.box.w)+"x"+Math.round(e.box.h)+":"+(e.values&&e.values.fill||""));}
  var freq={};cands.forEach(function(e){var k=key(e);freq[k]=(freq[k]||0)+1;});
  cands=cands.filter(function(e){return freq[key(e)]===1;});
  // ② 짧은 글자는 어디에나 맞으므로 뺀다
  cands=cands.filter(function(e){return e.kind!=="text"||String(e.text||"").replace(/\\s/g,"").length>=4;});
  // ③ 화면을 격자로 나눠 칸마다 가장 큰 것을 하나씩 — 위쪽에 몰리지 않게
  var C=${cols},R=${rows},cell={};
  cands.forEach(function(e){
    var cx=Math.min(C-1,Math.floor((e.box.x+e.box.w/2)/design.width*C));
    var cy=Math.min(R-1,Math.floor((e.box.y+e.box.h/2)/design.height*R));
    var k=cx+","+cy,cur=cell[k],a=e.box.w*e.box.h;
    if(!cur||a>cur.box.w*cur.box.h)cell[k]=e;
  });
  return Object.keys(cell).map(function(k){return cell[k];});
}`;
  const start = patched.indexOf('function pickAnchors(design,excludeBoxes){');
  const end = patched.indexOf('\nfunction matchAnchorPatch(', start);
  if (start < 0 || end < 0) { console.error('pickAnchors not found'); process.exit(1); }
  patched = patched.slice(0, start) + spread + patched.slice(end);
}
// FORCE_TX/FORCE_TY: 정렬을 고정한다(자동 판정의 '천장'을 재는 계측용. 실제 운영 방안 아님).
// 빈 값은 '안 준 것'으로 본다 — 셸에서 FORCE_TY="" 로 넘기면 예전엔 ty=0 고정이 켜져
// 화면 전체가 정렬 없이 비교되고 있었다(엔진의 정렬을 전혀 재지 못했다).
if (process.env.FORCE_TY !== undefined && process.env.FORCE_TY !== '') {
  patched = patched.replace('function comparePair(p,d,cap,img){',
    'function comparePair(p,d,cap,img){\n  var __origAlign=alignFor;alignFor=function(){return {mode:"forced",s:1,tx:' +
    Number(process.env.FORCE_TX || 0) + ',ty:' + Number(process.env.FORCE_TY) + ',score:1,anchors:99};};');
}
const marker = 'if(location.search.indexOf("selftest=1")>=0)runSelfTest();else post({type:"request-selection-status"});';
if (!ui.includes(marker)) { console.error('marker not found'); process.exit(1); }
const harness = `
window.__repro=true;
async function __load(b64){return new Promise(function(res,rej){var im=new Image();im.onload=function(){res(im);};im.onerror=rej;im.src="data:image/png;base64,"+b64;});}
async function __run(){
  var full=await __load(${JSON.stringify(designB64)});
  var scale=Math.min(1,${process.env.DESIGN_MAX||1200}/Math.max(full.width,full.height));
  var dc=canvasFor(Math.round(full.width*scale),Math.round(full.height*scale));dc.getContext("2d").drawImage(full,0,0,dc.width,dc.height);
  var cap=await __load(${JSON.stringify(devB64)});
  var design={id:${JSON.stringify(el.frame.id)},name:${JSON.stringify(el.frame.name||"design")},width:${el.frame.width},height:${el.frame.height},elements:${JSON.stringify(elements)},policy:${process.env.SCREEN_TYPE?JSON.stringify({screenType:process.env.SCREEN_TYPE}):"null"}}; // SCREEN_TYPE=common|data 로 화면 종류를 정할 수 있다(없으면 프레임 이름으로 추정)
  var capture={img:cap,width:cap.width,height:cap.height};
  var t0=performance.now();
  if(${JSON.stringify(process.env.TOP_TRIM||'')}!=="")capture.topTrim=Number(${JSON.stringify(process.env.TOP_TRIM||'0')});
  if(${JSON.stringify(process.env.BOTTOM_TRIM||'')}!=="")capture.bottomTrim=Number(${JSON.stringify(process.env.BOTTOM_TRIM||'0')}); // 검수 범위 › 아래쪽 제외(플러그인의 사람 설정과 같은 자리)
  var pairResult=comparePair({id:"p"},design,capture,dc); // 플러그인과 같은 흐름(틀 띠 판정 → 캡처 위쪽 자르기 → 2차 비교)
  var model=pairResult.alignment,t1=performance.now();
  var cands=pairResult.candidates,trimUsed=pairResult.range.captureTop||0;
  var t2=performance.now();
  function __rawNCC(box,dx,dy){var c=window.__ctx,W=c.W,H=c.H,dd=c.dd.data,cd=c.cd.data,n=0,sa=0,sb=0,saa=0,sbb=0,sab=0;for(var y=Math.floor(box.y);y<box.y+box.h;y++)for(var x=Math.floor(box.x);x<box.x+box.w;x++){var cx=x+dx,cy=y+dy;if(x<0||y<0||x>=W||y>=H||cx<0||cy<0||cx>=W||cy>=H)continue;var i=(y*W+x)*4,j=(cy*W+cx)*4,a=dd[i]*.299+dd[i+1]*.587+dd[i+2]*.114,b=cd[j]*.299+cd[j+1]*.587+cd[j+2]*.114;n++;sa+=a;sb+=b;saa+=a*a;sbb+=b*b;sab+=a*b;}var ma=sa/n,mb=sb/n,va=saa/n-ma*ma,vb=sbb/n-mb*mb;if(va<1||vb<1)return 1;return (sab/n-ma*mb)/Math.sqrt(va*vb);}
  window.__unitDbg.forEach(function(u){if(u.kind!=="text"||!u.segInfo)return;var pb=u.pb,segW=Math.max(24,Math.round(pb.h*2)),step=Math.max(8,Math.round(segW/2)),out=[];for(var x=pb.x;x+segW<=pb.x+pb.w+step;x+=step){var seg={x:x,y:pb.y,w:Math.min(segW,pb.x+pb.w-x),h:pb.h};if(seg.w<segW*.6)break;var md=Math.max(3,Math.round(pb.w*.1)),best=-2,bestE=1;for(var o=-md;o<=md;o++){for(var oy=-1;oy<=1;oy++){var v=__rawNCC(seg,u.dx+o,u.dy+oy);if(v>best)best=v;}}for(var o2=-md;o2<=md;o2++){var e=__exactMin(seg,u.dx+o2,u.dy);if(e<bestE)bestE=e;}out.push([Math.round(x),+best.toFixed(2),+bestE.toFixed(2)]);}u.rawSegs=out;});

  function __blur(data,W,H,x,y){var r=0,n=0;for(var yy=-1;yy<=1;yy++)for(var xx=-1;xx<=1;xx++){var px=x+xx,py=y+yy;if(px<0||py<0||px>=W||py>=H)continue;var i=(py*W+px)*4;r+=data[i]*.299+data[i+1]*.587+data[i+2]*.114;n++;}return r/n;}
  function __blurNCC(box,dx,dy){var c=window.__ctx,W=c.W,H=c.H,dd=c.dd.data,cd=c.cd.data,n=0,sa=0,sb=0,saa=0,sbb=0,sab=0;for(var y=Math.floor(box.y);y<box.y+box.h;y++)for(var x=Math.floor(box.x);x<box.x+box.w;x++){var cx=x+dx,cy=y+dy;if(x<0||y<0||x>=W||y>=H||cx<0||cy<0||cx>=W||cy>=H)continue;var a=__blur(dd,W,H,x,y),b=__blur(cd,W,H,cx,cy);n++;sa+=a;sb+=b;saa+=a*a;sbb+=b*b;sab+=a*b;}var ma=sa/n,mb=sb/n,va=saa/n-ma*ma,vb=sbb/n-mb*mb;if(va<1||vb<1)return 1;return (sab/n-ma*mb)/Math.sqrt(va*vb);}
  function __exactMin(box,dx,dy){var c=window.__ctx,W=c.W,H=c.H,best=1;for(var oy=-1;oy<=1;oy++)for(var ox=-1;ox<=1;ox++){var miss=0,uni=0;for(var y=Math.floor(box.y);y<box.y+box.h;y++)for(var x=Math.floor(box.x);x<box.x+box.w;x++){var cx=x+dx+ox,cy=y+dy+oy;if(x<0||y<0||x>=W||y>=H||cx<0||cy<0||cx>=W||cy>=H)continue;var a=c.dE[y*W+x]>30,b=c.cE[cy*W+cx]>30;if(a||b){uni++;if(a!==b)miss++;}}var m=uni?miss/uni:1;if(m<best)best=m;}return best;}
  window.__unitDbg.forEach(function(u){if(u.kind!=="text")return;var c=window.__ctx,pb=u.pb,segW=Math.max(24,Math.round(pb.h*2)),step=Math.max(8,Math.round(segW/2)),segs=[];for(var x=pb.x;x+segW<=pb.x+pb.w+step;x+=step){var seg={x:x,y:pb.y,w:Math.min(segW,pb.x+pb.w-x),h:pb.h};if(seg.w<segW*.6)break;var bestN=-2,bestO=0,md=Math.max(3,Math.round(pb.w*.1));for(var o=-md;o<=md;o+=2){var nn=grayPatchNCC(c.dd.data,c.cd.data,c.W,c.H,seg,u.dx+o,u.dy);if(nn>bestN){bestN=nn;bestO=o;}}segs.push([Math.round(x),+grayPatchNCC(c.dd.data,c.cd.data,c.W,c.H,seg,u.dx,u.dy).toFixed(2),+bestN.toFixed(2),bestO]);}u.segs=segs;u.bncc=+__blurNCC(u.pb,u.dx,u.dy).toFixed(2);u.exact=+__exactMin(u.pb,u.dx,u.dy).toFixed(2);});

  var lite=cands.map(function(c){return{no:c.no,status:c.status,policy:c.policy?c.policy.source+":"+(c.policy.variable?"가변":"고정"):null,kind:c.kind||"area",label:c.label,detail:c.detail,confidence:c.confidence,rawBox:{x:Math.round(c.rawBox.x),y:Math.round(c.rawBox.y),w:Math.round(c.rawBox.w),h:Math.round(c.rawBox.h)},designBox:{x:Math.round(c.designBox.x),y:Math.round(c.designBox.y),w:Math.round(c.designBox.w),h:Math.round(c.designBox.h)},designNodeIds:c.designNodeIds,designValues:c.designValues};});
  var ov=canvasFor(cap.width,cap.height),ox=ov.getContext("2d");ox.drawImage(cap,0,0);
  cands.forEach(function(c){var col=c.kind==="spacing"?"#CA8A04":"#EA580C";ox.strokeStyle=col;ox.lineWidth=3;ox.strokeRect(c.rawBox.x,c.rawBox.y,c.rawBox.w,c.rawBox.h);ox.fillStyle=col;ox.beginPath();ox.arc(c.rawBox.x-6,c.rawBox.y-6,14,0,7);ox.fill();ox.fillStyle="#fff";ox.font="bold 15px sans-serif";ox.textAlign="center";ox.textBaseline="middle";ox.fillText(String(c.no),c.rawBox.x-6,c.rawBox.y-6);});
  // 정렬된 디자인을 개발 이미지 좌표계로 반투명 겹침
  var ovl=canvasFor(cap.width,cap.height),lx=ovl.getContext("2d");lx.drawImage(cap,0,0);if(trimUsed){lx.fillStyle="rgba(107,114,128,.55)";lx.fillRect(0,0,cap.width,trimUsed);}lx.globalAlpha=.45;
  // 구간별로 따로 맞춘 화면은 구간마다 제 자리에 얹는다(한 번에 얹으면 실제 비교와 다른 그림이 나온다)
  (model.bands&&model.bands.length?model.bands:[{y0:0,y1:dc.height,ty:model.ty}]).forEach(function(z){
    lx.save();lx.beginPath();lx.rect(0,(z.y0-model.ty)/model.s+trimUsed,cap.width,(z.y1-z.y0)/model.s);lx.clip();
    lx.setTransform(1/model.s,0,0,1/model.s,-model.tx/model.s,-z.ty/model.s+trimUsed);lx.drawImage(dc,0,0);lx.restore();});
  lx.setTransform(1,0,0,1,0,0);
  var out={model:{mode:model.mode,s:model.s,tx:model.tx,ty:model.ty,score:model.score,anchors:model.anchors,bands:model.bands||null,logicalScale:dc.width/design.width},timing:{alignMs:Math.round(t1-t0),diffMs:Math.round(t2-t1)},designImg:{w:dc.width,h:dc.height},capture:{w:cap.width,h:cap.height},candidates:lite,notices:cands.notices,range:pairResult.range,sections:cands.sections,units:window.__unitDbg,secVotes:window.__secVotes,anchorVotes:window.__anchorVotes,anchorList:window.__anchorList,areaBoxes:window.__areaBoxes,areaGrid:window.__areaGrid,dbg:window.__dbg,textDbg:window.__textDbg};
  document.body.innerHTML='<pre id="reproOut">'+JSON.stringify(out).replace(/</g,"&lt;")+'</pre><img id="reproOverlay" src="'+ov.toDataURL("image/png")+'"><img id="reproAlign" src="'+ovl.toDataURL("image/png")+'">';
  document.title="REPRO DONE";
}
__run().catch(function(e){document.body.innerHTML='<pre id="reproOut">ERROR '+String(e&&e.stack||e).replace(/</g,"&lt;")+'</pre>';document.title="REPRO ERROR";});
`;
const html = patched.replace(marker, process.env.CASE_FILE ? fs.readFileSync(process.env.CASE_FILE,'utf8') : harness);
const harnessPath = path.join(here, outPrefix + '.harness.html');
fs.writeFileSync(harnessPath, html);
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const dom = cp.execFileSync(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu', '--virtual-time-budget=90000', '--dump-dom', 'file://' + harnessPath], { encoding: 'utf8', timeout: 180000, maxBuffer: 1 << 28 });
const m = dom.match(/<pre id="reproOut">([\s\S]*?)<\/pre>/);
if (!m) { console.error(dom.slice(0, 2000)); process.exit(1); }
const text = m[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
fs.writeFileSync(path.join(here, outPrefix + '.json'), text);
['reproOverlay', 'reproAlign'].forEach((id, i) => {
  const im = dom.match(new RegExp('<img id="' + id + '" src="data:image/png;base64,([^"]+)"'));
  if (im) fs.writeFileSync(path.join(here, outPrefix + (i ? '.align.png' : '.overlay.png')), Buffer.from(im[1], 'base64'));
});
if (text.startsWith('ERROR')) { console.error(text); process.exit(1); }
if (process.env.CASE_FILE) { console.log(text); process.exit(0); }
const out = JSON.parse(text);
console.log('model', JSON.stringify(out.model), 'timing', JSON.stringify(out.timing));
console.log('notices',out.notices);console.log('range',JSON.stringify(out.range));console.log('sections',JSON.stringify(out.sections));
out.candidates.forEach(c => console.log(`#${c.no} [${c.kind}]${c.status==='variable'?' (가변 글자 묶음)':''}${c.policy?' {'+c.policy+'}':''} ${c.label} ${c.detail?'— '+c.detail:''} conf=${c.confidence || '-'} raw=${JSON.stringify(c.rawBox)} design=${JSON.stringify(c.designBox)} nodes=${(c.designNodeIds || []).join(',')}`));
