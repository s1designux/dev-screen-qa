// 단일 원본(collect.js) → 북마클릿 생성 + setup.html 생성 + ui.html 주입
const fs = require('fs');
const path = require('path');
const DIR = '/Users/designgroup_02/dev-screen-qa/plugin-value-qa';

// collect.js 를 북마클릿으로 변환 (주석 제거 → 1줄화 → javascript: 래핑). collect.js가 유일 원본이라 표류 없음.
const collect = fs.readFileSync(path.join(DIR,'collect.js'),'utf8');
const bm = 'javascript:' + collect.replace(/\/\*[\s\S]*?\*\//g,'').replace(/^\s*\/\/.*$/gm,'').replace(/\s+/g,' ').trim();
fs.writeFileSync(path.join(DIR,'collect-bookmarklet.txt'), bm);

function htmlAttr(s){ return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;'); }

const setup = `<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>화면 측정 북마크 설정</title>
<style>
 body{font-family:-apple-system,"Segoe UI","Malgun Gothic",system-ui,sans-serif;background:#F9FAFB;color:#1F2937;max-width:640px;margin:0 auto;padding:40px 24px;line-height:1.6;}
 h1{font-size:22px;margin-bottom:6px;} .sub{color:#6B7280;margin-bottom:28px;}
 .bar{background:#EFF6FF;border:1px dashed #93C5FD;border-radius:12px;padding:28px;text-align:center;margin:20px 0;}
 .bm{display:inline-block;background:#2563EB;color:#fff;font-weight:700;font-size:16px;padding:12px 22px;border-radius:10px;text-decoration:none;cursor:grab;}
 ol{padding-left:20px;} li{margin:8px 0;} .step-n{font-weight:700;color:#2563EB;}
 kbd{background:#F3F4F6;border:1px solid #E5E7EB;border-radius:5px;padding:1px 6px;font-size:13px;}
 .note{font-size:13px;color:#6B7280;background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:14px 16px;margin-top:20px;}
</style></head><body>
 <h1>📐 화면 측정 북마크 설정</h1>
 <div class="sub">아래 파란 버튼을 <b>북마크바로 드래그</b>하면 끝이에요. 딱 한 번만 하면 됩니다.</div>
 <div class="bar">
   <a class="bm" href="${htmlAttr(bm)}">📐 화면 측정</a>
   <div style="margin-top:14px;color:#6B7280;font-size:13px">↑ 이 버튼을 위쪽 <b>북마크바로 끌어다 놓기</b></div>
 </div>
 <ol>
   <li><span class="step-n">1.</span> 북마크바가 안 보이면 <kbd>⌘</kbd>+<kbd>⇧</kbd>+<kbd>B</kbd> 로 켜기</li>
   <li><span class="step-n">2.</span> 위 <b>📐 화면 측정</b> 버튼을 북마크바로 드래그</li>
   <li><span class="step-n">3.</span> 끝! 이제 검사할 화면에서 그 북마크를 클릭하면 측정 파일이 다운로드돼요</li>
 </ol>
 <div class="note">⚠️ 회사 사이트가 보안정책으로 이 북마크를 막으면, <b>collect.js</b> 내용을 개발자도구 콘솔에 붙여넣는 방식으로 대신하면 됩니다(같은 결과).</div>
</body></html>`;
fs.writeFileSync(path.join(DIR,'setup.html'), setup);

// ui.html 에 북마클릿 주입 — 구분 마커 사이를 교체(idempotent). 선언을 못 찾으면 에러(가드).
let ui = fs.readFileSync(path.join(DIR,'ui.html'),'utf8');
const re = /var BOOKMARKLET = (?:\/\*BM_START\*\/[\s\S]*?\/\*BM_END\*\/|"(?:[^"\\]|\\.)*");/;
if (!re.test(ui)) throw new Error('ui.html에서 `var BOOKMARKLET = ...;` 선언을 못 찾았어요. 주입 실패(가드).');
ui = ui.replace(re, 'var BOOKMARKLET = /*BM_START*/' + JSON.stringify(bm) + '/*BM_END*/;');
fs.writeFileSync(path.join(DIR,'ui.html'), ui);

console.log('생성: collect-bookmarklet.txt(' + bm.length + '자) · setup.html · ui.html 주입 완료');
