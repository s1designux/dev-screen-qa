// 표 화면 재현 세트 생성: codes_mock.html 을 헤드리스 Chrome 으로 찍어
// 사용: node make_table_case.js
const fs = require('fs'), path = require('path'), cp = require('child_process');
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const here = __dirname, page = 'file://' + path.join(here, 'codes_mock.html');
if (!fs.existsSync(chrome)) { console.error('Chrome을 찾지 못했습니다:', chrome); process.exit(1); }
const base = ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1', '--window-size=1200,760', '--virtual-time-budget=3000'];
function shot(v, out) {
  cp.execFileSync(chrome, base.concat(['--screenshot=' + path.join(here, out), page + '?v=' + v]), { stdio: 'ignore', timeout: 60000 });
  console.log('✓', out);
}
function elements(extra, out) {
  const html = cp.execFileSync(chrome, base.concat(['--dump-dom', page + '?v=design&elements=1' + extra]), { encoding: 'utf8', timeout: 60000 });
  const m = html.match(/<pre id="elements">([\s\S]*?)<\/pre>/);
  if (!m) { console.error('요소 목록을 만들지 못했습니다.'); process.exit(1); }
  const text = m[1].replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');
  fs.writeFileSync(path.join(here, out), text);
  console.log('✓', out, JSON.parse(text).rows.length + '개 요소');
}
shot('design', 'design_codes_1200x760.png');
shot('dev', 'dev_codes_1200x760.png');
elements('', 'elements_codes.json');
