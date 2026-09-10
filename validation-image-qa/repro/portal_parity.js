// 포털 엔진(/engine/ui.html 과 같은 파일)을 헤드리스 크롬에서 돌려 플러그인 재현(run.js) 결과와 같은지 잰다.
// 사용: ELEMENTS_JSON=… DESIGN_PNG=… DEV_PNG=… node portal_parity.js <기준 json(run.js 출력)> [출력 접두사]
const fs = require('fs'), path = require('path'), cp = require('child_process');
const here = __dirname, root = path.resolve(here, '../..');
const baselinePath = process.argv[2], outPrefix = process.argv[3] || 'portal';
if (!baselinePath) { console.error('사용: node portal_parity.js <기준 json> [접두사]'); process.exit(1); }
const el = JSON.parse(fs.readFileSync(path.join(here, process.env.ELEMENTS_JSON || 'elements.json'), 'utf8'));
const elements = el.rows.map(r => {
  const o = {}; el.cols.forEach((c, i) => o[c] = r[i]);
  const e = { id: o.id, name: o.name || o.id, type: o.type, kind: o.kind, depth: o.depth, parentId: o.parentId, parentType: null, box: { x: o.x, y: o.y, w: o.w, h: o.h }, text: o.text || '' };
  if (o.chain) e.chain = o.chain; if (o.propRef) e.propRef = o.propRef;
  if (o.kind === 'text') e.values = { text: o.text, fontSize: o.fontSize, fontWeight: o.fontWeight, fontFamily: 'Pretendard Variable', fontStyle: '', lineHeight: '130%', color: o.color, textAlign: 'LEFT' };
  else e.values = { width: o.w, height: o.h, fill: o.fill, stroke: o.stroke, strokeWidth: o.strokeWidth, radius: o.radius, opacity: 1 };
  return e;
});
const b64 = f => fs.readFileSync(path.join(here, f)).toString('base64');
const engine = cp.execFileSync('python3', ['-c', 'import sys;sys.path.insert(0,"' + path.join(root, 'mvp0') + '");import auto_inspect;sys.stdout.write(auto_inspect.engine_html())'], { encoding: 'utf8', maxBuffer: 1 << 26 });
const enginePath = path.join(here, outPrefix + '.engine.html'); fs.writeFileSync(enginePath, engine);
const materials = {
  type: 'portal-run', autoRunId: 'parity',
  design: { id: el.frame.id, name: el.frame.name || 'design', width: el.frame.width, height: el.frame.height, elements, policy: process.env.SCREEN_TYPE ? { screenType: process.env.SCREEN_TYPE } : null,
            pngUrl: 'data:image/png;base64,' + b64(process.env.DESIGN_PNG || 'design_1920x1080.png') },
  capture: { pngUrl: 'data:image/png;base64,' + b64(process.env.DEV_PNG || 'dev_1920x934.png') },
};
if (process.env.TOP_TRIM !== undefined) materials.capture.topTrim = Number(process.env.TOP_TRIM);
const driver = `<!doctype html><meta charset="utf-8"><pre id="reproOut"></pre><script>
var m=${JSON.stringify(materials)};
window.addEventListener("message",function(e){var d=e.data;if(!d||!d.type)return;
  if(d.type==="portal-ready"){document.getElementById("f").contentWindow.postMessage(m,"*");}
  else if(d.type==="portal-result"||d.type==="portal-error"){document.getElementById("reproOut").textContent=JSON.stringify(d);document.title="REPRO DONE";}
});
</script><iframe id="f" src="file://${enginePath}" style="width:1px;height:1px"></iframe>`;
const driverPath = path.join(here, outPrefix + '.driver.html'); fs.writeFileSync(driverPath, driver);
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const dom = cp.execFileSync(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu', '--allow-file-access-from-files', '--virtual-time-budget=120000', '--dump-dom', 'file://' + driverPath], { encoding: 'utf8', timeout: 240000, maxBuffer: 1 << 28 });
const mm = dom.match(/<pre id="reproOut">([\s\S]*?)<\/pre>/);
if (!mm || !mm[1].trim()) { console.error('결과 없음'); console.error(dom.slice(0, 1500)); process.exit(1); }
const out = JSON.parse(mm[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&'));
fs.writeFileSync(path.join(here, outPrefix + '.json'), JSON.stringify(out));
if (out.type === 'portal-error') { console.error('엔진 오류:', out.message); process.exit(1); }
const base = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
const key = c => [c.no, c.kind, c.status, c.label, JSON.stringify(c.rawBox), (c.designNodeIds || []).join(',')].join('|');
const A = base.candidates.map(key), B = out.candidates.map(key);
const onlyA = A.filter(k => !B.includes(k)), onlyB = B.filter(k => !A.includes(k));
console.log(`플러그인 재현 ${A.length}건 / 포털 엔진 ${B.length}건 · 정렬 ${JSON.stringify(base.model && {mode: base.model.mode, tx: base.model.tx, ty: base.model.ty})} vs ${JSON.stringify(out.alignment)}`);
if (onlyA.length || onlyB.length) { console.log('플러그인에만:', onlyA); console.log('포털에만:', onlyB); console.log('PARITY FAIL'); process.exit(2); }
console.log('PARITY OK (후보 목록 동일)');
