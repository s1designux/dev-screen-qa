// 자가검증 — 태그없는 자동짝맞춤 + 값 대조를 '실제 플러그인 ui.html'로 재현.
// 헤드리스 크롬으로 ui.html을 띄우고 정답(design-figma.json)+개발(measure-dev.json)을 주입해
// (1) 자동 짝맞춤이 의도된 짝을 맞추는지 (2) 심어둔 결함을 잡는지 (3) 헛경보가 없는지 검증한다.
// 실행: npm i  (puppeteer-core)  후  npm test   ※ Chrome 설치 필요(CHROME_PATH로 경로 지정 가능)
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const UI = 'file://' + path.resolve(__dirname, '../plugin-value-qa/ui.html');
const design = JSON.parse(fs.readFileSync(path.join(__dirname, 'design-figma.json'), 'utf8'));
const dev = JSON.parse(fs.readFileSync(path.join(__dirname, 'measure-dev.json'), 'utf8'));

// 의도된 짝 (이름표 없이 자동으로 맞춰야 하는 정답)
const GROUND_TRUTH = {
  'app/header': 'dev-1', 'header/logo': 'dev-2', 'header/search': 'dev-3', 'header/avatar': 'dev-4',
  'page/title': 'dev-5', 'stat/card-1': 'dev-7', 'stat/card-1/label': 'dev-8', 'stat/value-1': 'dev-9',
  'stat/card-2': 'dev-10', 'stat/card-2/label': 'dev-11', 'stat/value-2': 'dev-12',
  'stat/card-3': 'dev-13', 'stat/card-3/label': 'dev-14', 'stat/value-3': 'dev-15',
  'content/map': 'dev-16', 'content/list': 'dev-17', 'action/export-btn': 'dev-22'
};
// 심어둔 실제 결함이 있어야 하는 요소들
const EXPECTED_DEFECT_ELEMENTS = ['action/export-btn', 'page/title', 'header/avatar', 'stat/card-2', 'header/search', 'stat/value-3'];

const fails = [];
function check(name, cond) { if (!cond) fails.push(name); }

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') pageErrors.push(m.text()); });
  await page.goto(UI, { waitUntil: 'networkidle0' });

  const result = await page.evaluate((d, v) => {
    onmessage({ data: { pluginMessage: { type: 'design-read', data: d } } });
    dev = v; flags.dev = true; maybeMatch(); refreshSteps();
    var pairs = M.pairs.map(function (p) { return { fig: (M.fig[p.fi].name || M.fig[p.fi].text), dev: M.devEls[p.di].id }; });
    doCompare();
    var chips = {}; document.querySelectorAll('.chip').forEach(function (c) { chips[c.querySelector('.t').textContent] = +c.querySelector('.n').textContent; });
    var failNames = [].slice.call(document.querySelectorAll('.el.fail .el-head .name')).map(function (n) { return n.textContent; });
    return { pairs: pairs, chips: chips, failNames: failNames };
  }, design, dev);

  await browser.close();

  // 1) 로드 에러 없음
  check('페이지 에러 없음', pageErrors.length === 0);
  // 2) 자동 짝맞춤: 의도된 17개 짝을 모두 정확히
  const pairMap = {}; result.pairs.forEach(p => { pairMap[p.fig] = p.dev; });
  let matchOk = 0, matchTotal = 0;
  for (const fig in GROUND_TRUTH) { matchTotal++; if (pairMap[fig] === GROUND_TRUTH[fig]) matchOk++; }
  check('자동 짝맞춤 ' + matchOk + '/' + matchTotal, matchOk === matchTotal);
  // 3) 심어둔 결함 요소가 모두 '실제 문제'로 검출
  EXPECTED_DEFECT_ELEMENTS.forEach(function (name) {
    check('결함 검출: ' + name, result.failNames.indexOf(name) >= 0);
  });
  // 4) 헛경보 없음: 구조 차이는 1개(추가된 배너)만
  check('구조 차이 == 1 (헛경보 없음)', result.chips['구조 차이'] === 1);

  console.log('짝맞춤:', matchOk + '/' + matchTotal, '· 요약:', JSON.stringify(result.chips), '· 실제문제 요소:', result.failNames.join(', '));
  if (pageErrors.length) console.log('페이지 에러:', pageErrors.join(' | '));
  if (fails.length) { console.error('\n❌ 실패:', fails.join(' | ')); process.exit(1); }
  console.log('\n✅ 통과 — 태그없이 자동 짝맞춤 ' + matchOk + '/' + matchTotal + ', 심어둔 결함 ' + EXPECTED_DEFECT_ELEMENTS.length + '곳 검출, 구조차이 1(배너)만.');
})().catch(e => { console.error(e); process.exit(1); });
