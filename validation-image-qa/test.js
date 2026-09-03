// 추가 패키지 없이 설치된 Chrome으로 플러그인 UI의 순수 로컬 엔진을 검증한다.
const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const vm = require('vm');

// Figma 메인 코드의 선택 구분 규칙을 가벼운 가짜 문서로 확인한다.
const mainCode = fs.readFileSync(path.resolve(__dirname, '../plugin-image-qa/code.js'), 'utf8');
const figmaStub = { showUI() {}, ui: { postMessage() {} }, currentPage: { selection: [] }, on() {} };
const context = { figma: figmaStub, __html__: '' };
vm.runInNewContext(mainCode, context, { filename: 'plugin-image-qa/code.js' });
const imageNode = { type: 'RECTANGLE', absoluteBoundingBox: { x: 0, y: 0, width: 100, height: 200 }, fills: [{ type: 'IMAGE', visible: true }], exportAsync() {} };
const designWithImageBackground = { type: 'FRAME', absoluteBoundingBox: { x: 0, y: 0, width: 100, height: 200 }, fills: [{ type: 'IMAGE', visible: true }], children: [{}], exportAsync() {} };
if (!context.selectableCapture(imageNode) || context.selectableCapture(designWithImageBackground) || !context.selectableFrame(designWithImageBackground)) {
  console.error('Figma 디자인/개발화면 자동 구분 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ Figma 디자인/개발화면 자동 구분');
const selectedGeometry = context.selectionGeometry([designWithImageBackground, imageNode]);
if (selectedGeometry.designs.length !== 1 || selectedGeometry.captures.length !== 1) {
  console.error('Figma 드래그 선택 상태 구분 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ Figma 드래그 선택 상태 구분');
const rootFrame = { id: 'root', type: 'FRAME', absoluteBoundingBox: { x: 0, y: 0, width: 200, height: 200 }, children: [
  { id: 'card-a', name: '카드 A', type: 'FRAME', visible: true, absoluteBoundingBox: { x: 20, y: 20, width: 160, height: 50 }, fills: [], strokes: [], children: [] },
  { id: 'card-b', name: '카드 B', type: 'FRAME', visible: true, absoluteBoundingBox: { x: 20, y: 100, width: 160, height: 50 }, fills: [], strokes: [], children: [] }
] };
const collected = context.collectDesign(rootFrame);
if (collected.length !== 2 || collected[0].depth !== 1 || collected[0].parentId !== 'root') {
  console.error('컴포넌트 간격 비교용 부모·깊이 수집 규칙이 깨졌습니다.');
  process.exit(1);
}
if (!mainCode.includes('c.kind === "spacing"') || !mainCode.includes('간격 기준 컴포넌트') || !mainCode.includes('간격 측정선')) {
  console.error('컴포넌트 간격 후보의 캔버스 표시 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 컴포넌트 간격 기준 수집과 측정선 표시');

const uiSource = fs.readFileSync(path.resolve(__dirname, '../plugin-image-qa/ui.html'), 'utf8');
const manifest = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../plugin-image-qa/manifest.json'), 'utf8'));
if (manifest.name !== '개발화면 검수기' || !uiSource.includes('class="header-title">개발화면 검수기 1.0Ver') || !uiSource.includes('class="update-time">업데이트 ') || /header\{[^}]*border-bottom/.test(uiSource)) {
  console.error('첫 화면의 검수기 이름 또는 우측 업데이트 표시 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 첫 화면 좌측 검수기 이름과 우측 업데이트 표시');
if (!uiSource.includes('class="scope-trigger"') || !uiSource.includes('id="scopeTooltip" role="tooltip"') || !uiSource.includes('.scope-popover:hover .scope-tooltip,.scope-popover:focus-within .scope-tooltip') || (uiSource.match(/class="scope-item"/g) || []).length !== 5 || uiSource.includes('표시된 결과는 오류가 아닌') || !['요소 추가·누락','위치, 정렬, 크기, 컴포넌트 간격','색상, 형태, 테두리, 구분선','아이콘, 이미지, 잘림','폰트 모양, 글자 영역 크기, 줄바꿈, 말줄임'].every((text) => uiSource.includes(text))) {
  console.error('첫 화면의 검수 가능 범위 호버 안내가 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 첫 화면 검수 가능 범위 호버 안내');
if (uiSource.includes('class="steps"') || uiSource.includes('id="readDesigns"') || !uiSource.includes('나열한 모든 화면을 드래그해 선택한 뒤')) {
  console.error('첫 화면의 간단한 2단계 안내 또는 단일 검수 시작 흐름이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 첫 화면 프로세스 숨김과 2단계 안내');
if (!uiSource.includes('.guide-row.next-step{margin-top:12px}') || !uiSource.includes('class="guide-row next-step"')) {
  console.error('2번 안내 위 여백 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 2번 안내 위 여백 확대');
if (!uiSource.includes('class="pair-example"') || !uiSource.includes('class="example-position">좌</span>') || !uiSource.includes('class="example-position">우</span>') || uiSource.includes('class="example-arrow"') || uiSource.includes('아직 선택하지 않았어요.')) {
  console.error('첫 화면의 좌우 배치 참고 일러스트 또는 초기 상태 문구 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 화살표 없는 좌우 배치 참고 일러스트와 빈 초기 상태');
if (!uiSource.includes('id="startCompare" disabled') || !uiSource.includes('pendingCompare||!selectionReady')) {
  console.error('올바른 화면 선택 전 검수 시작 비활성화 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 화면 선택 전 검수 시작 비활성화');
if (!uiSource.includes('function fitPrepareView()') || !uiSource.includes('if(name==="prepare")fitPrepareView();') || !uiSource.includes('body.prep-compact .pair-example{display:none}') || !uiSource.includes('window.addEventListener("resize",fitPrepareView)')) {
  console.error('준비 화면이 패널 높이에 맞게 줄어드는 규칙(스크롤 없애기)이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 준비 화면 패널 높이에 맞춰 접기(스크롤 없음)');
const prepareStatusAt = uiSource.indexOf('class="prepare-status"');
const startCompareAt = uiSource.indexOf('id="startCompare"');
if (prepareStatusAt < 0 || startCompareAt < prepareStatusAt || !uiSource.includes('#prepareView{height:100%;min-height:0;display:flex;flex-direction:column}') || !/\.prepare-status\{flex:1;min-height:72px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:12px 4px;overflow-y:auto/.test(uiSource) || !uiSource.includes('#startCompare{flex:none;margin-top:auto}')) {
  console.error('첫 화면의 중앙 상태 안내 또는 최하단 검수 시작 버튼 배치가 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 같은 행 비교 안내 중앙 정렬과 검수 시작 최하단 배치');
if (uiSource.includes('id="reviewSummary"') || uiSource.includes('class="chip"') || uiSource.includes('정렬 <b>') || uiSource.includes('countStatus(')) {
  console.error('검토 화면 상단의 불필요한 요약 칩이 남아 있습니다.');
  process.exit(1);
}
console.log('✓ 검토 화면 상단 요약 칩 제거');
if (!uiSource.includes('#reviewView{height:100%;min-height:0;display:flex;flex-direction:column}') || !uiSource.includes('#numberLists{flex:1;min-height:104px;overflow-y:auto;overscroll-behavior:contain') || uiSource.indexOf('id="toggleOverlay"') > uiSource.indexOf('id="numberLists"') || !uiSource.includes('class="overlay-control" id="toggleOverlay" aria-pressed="false"') || !uiSource.includes('.overlay-control{margin:0 0 10px;border-color:#D9D9D9;background:#FFFFFF;color:#353535;font-weight:500}') || !uiSource.includes('.overlay-control.on{border-color:#1D6CEB;background:#FFFFFF;color:#1D6CEB;font-weight:700}') || !uiSource.includes('toggleOverlay.textContent=visible?"겹쳐보기 끄기":"겹쳐보기"') || !uiSource.includes('class="candidate-hit"') || !uiSource.includes('class="row-action confirm') || !uiSource.includes('data-status="excluded">제외')) {
  console.error('검토 목록의 겹쳐보기 위치·행 클릭·빠른 판정 버튼 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 겹쳐보기 고정과 후보 목록 독립 스크롤·빠른 판정');
if (uiSource.includes('id="selectedCard"') || uiSource.includes('id="selectedTitle"') || uiSource.includes('id="selectedDesc"') || uiSource.includes('id="clearSelect"') || !uiSource.includes('function selectCandidate(id){selectedCandidateId=id;post({type:"focus-candidate"')) {
  console.error('후보 목록 클릭 시 선택 팝업 제거 또는 캔버스 포인팅 유지 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 후보 목록 클릭 팝업 제거와 캔버스 포인팅 유지');
if (!uiSource.includes('id="rangeCard"') || !uiSource.includes('id="rangeAdjust"') || !uiSource.includes('id="rangeApply"') || !uiSource.includes('id="rangeNone"') || !uiSource.includes('function decideFrameBands(') || !uiSource.includes('function trimmedCapture(') || !uiSource.includes('function comparePair(') || uiSource.indexOf('id="rangeCard"') > uiSource.indexOf('id="toggleOverlay"')) {
  console.error('검수 범위(틀 띠 제외·캡처 위쪽 조정) 카드 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 검수 범위 카드와 틀 띠 제외 흐름');
if (uiSource.includes('class="compare-strip') || uiSource.includes('function renderCompareStrip(') || uiSource.includes('compare-panes') || uiSource.includes('resize-ui')) {
  console.error('패널 안 나란히 보기가 남아 있습니다(캔버스 표시만 있어야 합니다).');
  process.exit(1);
}
console.log('✓ 패널 안 나란히 보기 제거');
if (!uiSource.includes('id="rangeToggle"') || !uiSource.includes('id="rangeBody"') || !uiSource.includes('function setRangeOpen(') || !uiSource.includes('.range-card.open .range-body{display:block}') || !uiSource.includes("main{flex:1;min-height:0;padding:8px 20px 16px;overflow:auto}") || uiSource.includes('height:calc(100vh - 64px)')) {
  console.error('검수 범위 접기·상단 여백 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 검수 범위 접기와 상단 여백');
if (!uiSource.includes('function overlayPlacement(') || !uiSource.includes('function overlayDesignBytes(') || !uiSource.includes('y:trim*K') || uiSource.includes('y:-sF.ty/sF.s*cap.displayScale*k')) {
  console.error('겹쳐보기 자리(잘라낸 띠 되돌리기·틀 띠 잘라 얹기) 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 겹쳐보기 자리 보정');
if (uiSource.includes('id="overlayFixCard"') || uiSource.includes('id="grabOverlay"') || uiSource.includes('id="saveOverlayPos"')) {
  console.error('겹쳐보기 맞추기 상자가 패널에 남아 있습니다(캔버스에서 끌어 저장만 있어야 합니다).');
  process.exit(1);
}
if (!uiSource.includes('function overlayFixFromPos(') || !uiSource.includes('function overlayMovedOnCanvas(') || !mainCode.includes('OVERLAY_FIX_KEY') || !mainCode.includes('function watchOverlayMoves(') || !mainCode.includes('"nodechange"') || !mainCode.includes('type: "overlay-moved"') || !mainCode.includes('reportOverlayPos(msg.pairId, existing)')) {
  console.error('겹쳐보기 위치를 끌어서 저장하는 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 겹쳐보기 위치 끌어서 저장');
if (!uiSource.includes('id="buildReport"') || !uiSource.includes('function buildReportPayload(') || !uiSource.includes('class="bottom-row"') || !mainCode.includes('async function buildReport(') || !mainCode.includes('REPORT_MARK') || !mainCode.includes('"build-report"') || !mainCode.includes('검수 레포트 · ')) {
  console.error('검수 레포트 작성(캔버스 메모장) 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 검수 레포트 작성 버튼과 캔버스 메모장');
if (!uiSource.includes('id="compareWhereBtn"') || !uiSource.includes('var compareOn=true') || !uiSource.includes('function renderCompareOnCanvas(') || !uiSource.includes('type:"render-compare"') || !uiSource.includes('compareOn?"켬":"끔"')) {
  console.error('나란히 보기 캔버스 표시와 켜기·끄기 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 나란히 보기 캔버스 표시와 켜기·끄기');
if (!mainCode.includes('function buildCompareCard(') || !mainCode.includes('COMPARE_MARK') || !mainCode.includes('"render-compare"') || !mainCode.includes('"clear-compare"') || !mainCode.includes('나란히 보기 · 번호 ')) {
  console.error('캔버스 나란히 보기 카드 생성 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 캔버스 나란히 보기 카드 생성');
if (!mainCode.includes('var topSide = (cbb.y + cbb.height + margin + card.height)') || !mainCode.includes('card.x = cbb.x + cbb.width / 2 - cardW / 2;') || !/link\.resize\(3, Math\.max\(1, Math\.abs\(pinEdgeY - cardEdgeY\)\)\)/.test(mainCode) || !mainCode.includes('focusNodes([card], 1.04);')) {
  console.error('나란히 보기 카드를 번호 위·아래에 붙이고 크게 보여 주는 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 나란히 보기 카드 번호 위·아래 배치와 확대');
if (!mainCode.includes('card.strokes = [{ type: "SOLID", color: paint("8A94A6") }]; card.strokeWeight = 2;') || !/card\.effects = \[\s*\{ type: "DROP_SHADOW"/.test(mainCode)) {
  console.error('나란히 보기 카드의 진한 테두리·그림자 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 나란히 보기 카드 테두리·그림자');
if (!mainCode.includes('function candidateIdFromNode(') || !mainCode.includes('"candidate-selected"') || !mainCode.includes('lastProgrammaticSelectionAt') || !mainCode.includes('link.name = "연결선"') || !uiSource.includes('function focusCandidateFromCanvas(')) {
  console.error('캔버스 번호 선택 → 패널 연동 또는 핀 옆 카드 배치 규칙이 깨졌습니다.');
  process.exit(1);
}
const pinChild = { getPluginData: () => '', parent: { getPluginData: (k) => (k === 'imageQaCandidate' ? 'cand-9' : ''), parent: null } };
if (context.candidateIdFromNode(pinChild) !== 'cand-9' || context.candidateIdFromNode({ getPluginData: () => '', parent: null }) !== null) {
  console.error('번호 표시에서 후보 id를 찾는 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 캔버스 번호 선택 → 패널 포커싱과 핀 옆 카드 배치');
if (!mainCode.includes('function pairIdFromNode(') || !mainCode.includes('"result-selected"') || !uiSource.includes('function focusResultFromCanvas(')) {
  console.error('캔버스에서 검수 화면을 고르면 패널이 따라가는 규칙이 깨졌습니다.');
  process.exit(1);
}
const boardNode = { getPluginData: (k) => (k === 'imageQaResult' ? 'pair-2' : ''), parent: null };
const insideCard = { getPluginData: () => '', parent: { getPluginData: (k) => (k === 'imageQaCompare' ? 'pair-3' : ''), parent: null } };
if (context.pairIdFromNode(boardNode) !== 'pair-2' || context.pairIdFromNode(insideCard) !== 'pair-3' || context.pairIdFromNode({ getPluginData: () => '', parent: null }) !== null) {
  console.error('선택한 노드에서 검수 화면을 찾는 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 캔버스 검수 화면 선택 → 패널 화면 전환');
if (!mainCode.includes('TRIM_KEY') || !mainCode.includes('set-capture-trim') || !mainCode.includes('비교 제외 띠') || !mainCode.includes('검수 범위')) {
  console.error('검수 범위 저장·캔버스 표시·패널 크기 규칙이 깨졌습니다.');
  process.exit(1);
}
console.log('✓ 검수 범위 저장(캡처 노드)과 캔버스 제외 띠 표시');

let exported;
imageNode.name = '개발 캡처';
imageNode.exportAsync = async () => new Uint8Array([1, 2, 3]);
context.exportCaptureNode(imageNode, 0).then((value) => { exported = value; });
setImmediate(() => {
  if (!exported || exported.x !== 0 || exported.y !== 0 || exported.width !== 100 || exported.height !== 200) {
    console.error('Figma 캔버스 행 위치 전달 규칙이 깨졌습니다.');
    process.exit(1);
  }
});

const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ui = 'file://' + path.resolve(__dirname, '../plugin-image-qa/ui.html') + '?selftest=1';
if (!fs.existsSync(chrome)) {
  console.error('Chrome을 찾지 못했습니다:', chrome);
  process.exit(1);
}
const html = cp.execFileSync(chrome, [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--virtual-time-budget=8000', '--dump-dom', ui
], { encoding: 'utf8', timeout: 60000 });
const title = (html.match(/<title>([^<]+)<\/title>/) || [])[1] || '';
const results = html.match(/<pre id="selftest">([\s\S]*?)<\/pre>/g) || [];
const last = results[results.length - 1] || '';
const text = last.replace(/^.*?<pre id="selftest">/, '').replace(/<\/pre>.*$/, '').replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');
if (title !== 'SELFTEST PASS') {
  console.error(text || html.slice(0, 1200));
  process.exit(1);
}
console.log(text.trim());
