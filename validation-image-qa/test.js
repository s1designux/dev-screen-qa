// 추가 패키지 없이 설치된 Chrome으로 플러그인 UI의 순수 로컬 엔진을 검증한다.
const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const vm = require('vm');

// Figma 메인 코드의 선택 구분 규칙을 가벼운 가짜 문서로 확인한다.
const mainCode = fs.readFileSync(path.resolve(__dirname, '../plugin-image-qa/code.js'), 'utf8');
const figmaStub = { showUI() {}, ui: {}, currentPage: { selection: [] } };
const context = { figma: figmaStub, __html__: '' };
vm.runInNewContext(mainCode, context, { filename: 'plugin-image-qa/code.js' });
const imageNode = { type: 'RECTANGLE', absoluteBoundingBox: { x: 0, y: 0, width: 100, height: 200 }, fills: [{ type: 'IMAGE', visible: true }], exportAsync() {} };
const designWithImageBackground = { type: 'FRAME', absoluteBoundingBox: { x: 0, y: 0, width: 100, height: 200 }, fills: [{ type: 'IMAGE', visible: true }], children: [{}], exportAsync() {} };
if (!context.selectableCapture(imageNode) || context.selectableCapture(designWithImageBackground) || !context.selectableFrame(designWithImageBackground)) {
  console.error('Figma 디자인/개발화면 자동 구분 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ Figma 디자인/개발화면 자동 구분');

const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ui = 'file://' + path.resolve(__dirname, '../plugin-image-qa/ui.html') + '?selftest=1';
if (!fs.existsSync(chrome)) {
  console.error('Chrome을 찾지 못했습니다:', chrome);
  process.exit(1);
}
const html = cp.execFileSync(chrome, [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--virtual-time-budget=3000', '--dump-dom', ui
], { encoding: 'utf8', timeout: 30000 });
const title = (html.match(/<title>([^<]+)<\/title>/) || [])[1] || '';
const results = html.match(/<pre id="selftest">([\s\S]*?)<\/pre>/g) || [];
const last = results[results.length - 1] || '';
const text = last.replace(/^.*?<pre id="selftest">/, '').replace(/<\/pre>.*$/, '').replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');
if (title !== 'SELFTEST PASS') {
  console.error(text || html.slice(0, 1200));
  process.exit(1);
}
console.log(text.trim());
