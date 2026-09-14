// 시험 화면을 헤드리스 크롬으로 열어 값을 잰다 — 자는 capture-extension/collect-core.js 그대로(복사 없음).
//   node validation-registry/measure.js            → measure-ok.json · measure-off.json 을 다시 만든다
// Chrome 이 필요하다. 경로가 다르면 CHROME_PATH=/경로/크롬.
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const 자 = fs.readFileSync(path.resolve(__dirname, '../capture-extension/collect-core.js'), 'utf8');
const 화면들 = [['dev-ok.html', 'measure-ok.json'], ['dev-off.html', 'measure-off.json']];

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  for (const [html, out] of 화면들) {
    await page.goto('file://' + path.resolve(__dirname, html), { waitUntil: 'networkidle0' });
    await page.evaluate(자);
    const 잰것 = await page.evaluate(() => globalThis.__qaMeasure());
    잰것.meta.url = 'validation-registry/' + html;      // 절대 경로를 남기지 않는다
    fs.writeFileSync(path.resolve(__dirname, out), JSON.stringify(잰것, null, 2));
    console.log(out, '요소', 잰것.elements.length, '폭', 잰것.meta.artboardWidth, '높이', 잰것.meta.artboardHeight);
  }
  await browser.close();
})();
