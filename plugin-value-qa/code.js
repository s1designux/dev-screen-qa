// ============================================================
//  값 검수 플러그인 - 메인 스레드 (Figma API 담당)
//  역할: 사용자가 고른 "정답 프레임" 안의 모든 '의미있는' 요소 값을
//        그 자리에서 라이브로 읽어 측정값으로 만들어 UI에 넘김.
//  이름표(레이어명) 없이도 됨 — UI에서 자동으로 짝을 맞춤.
//  외부 통신 없음. 사진(픽셀) 아님 — 실제 피그마 값·좌표를 읽음.
// ============================================================

figma.showUI(__html__, { width: 480, height: 760, themeColors: true });

var WEIGHT = { 'Thin':100,'Extra Light':200,'Light':300,'Regular':400,'Medium':500,'Semi Bold':600,'Bold':700,'Extra Bold':800,'Black':900 };

function r1(n) { return Math.round(n * 10) / 10; }
function to255(c) { return Math.round(c * 255); }

function fillRgb(node) {
  var fs = node.fills;
  if (!Array.isArray(fs)) return null;
  for (var i = 0; i < fs.length; i++) {
    var f = fs[i];
    if (f.visible !== false && f.type === 'SOLID') { var c = f.color; return 'rgb(' + to255(c.r) + ', ' + to255(c.g) + ', ' + to255(c.b) + ')'; }
  }
  return null;
}
function strokeRgb(node) {
  var ss = node.strokes;
  if (!Array.isArray(ss)) return null;
  for (var i = 0; i < ss.length; i++) {
    var s = ss[i];
    if (s.visible !== false && s.type === 'SOLID') { var c = s.color; return 'rgb(' + to255(c.r) + ', ' + to255(c.g) + ', ' + to255(c.b) + ')'; }
  }
  return null;
}
// 테두리 두께 안전하게 읽기 — VECTOR·ELLIPSE·LINE 등 일부 노드엔 개별-변 두께 속성이 없어 접근 시 throw됨.
function strokeW(node) {
  try { if (typeof node.strokeTopWeight === 'number') return node.strokeTopWeight; } catch (e) {}
  try { if (typeof node.strokeWeight === 'number') return node.strokeWeight; } catch (e) {}
  return 0;
}
function hasVisibleStroke(node) {
  return strokeRgb(node) != null && strokeW(node) > 0;
}
// 상자의 대표 글자(자식들 글자 합침) — 짝맞춤 힌트용
function aggText(node) {
  var t = '';
  (function w(x) { if (x.type === 'TEXT') { t += (x.characters || '') + ' '; } if ('children' in x) { for (var i = 0; i < x.children.length; i++) w(x.children[i]); } })(node);
  return t.replace(/\s+/g, ' ').trim().slice(0, 50);
}

// 스타일명 → 숫자 굵기 (공백제거·이탤릭제거·다양한 표기 흡수). 모르면 null(비교 스킵).
function weightFromStyle(sty) {
  if (!sty) return null;
  var s = String(sty).toLowerCase().replace(/\s+/g, '').replace('italic', '').replace('oblique', '');
  var M = { thin: 100, hairline: 100, extralight: 200, ultralight: 200, light: 300, regular: 400, normal: 400, book: 400, medium: 500, semibold: 600, demibold: 600, demi: 600, bold: 700, extrabold: 800, ultrabold: 800, heavy: 800, black: 900 };
  return M[s] != null ? M[s] : null;
}

function readElement(node, rootBox) {
  var bb = node.absoluteBoundingBox;
  if (!bb) return null;
  var isText = node.type === 'TEXT';
  var box = { x: r1(bb.x - rootBox.x), y: r1(bb.y - rootBox.y), w: r1(bb.width), h: r1(bb.height) };
  var style, text;
  if (isText) {
    var fam = (node.fontName && node.fontName.family) ? node.fontName.family : 'Inter';
    var sty = (node.fontName && node.fontName.style) ? node.fontName.style : 'Regular';
    var align = (node.textAlignHorizontal || 'LEFT').toLowerCase();
    text = (node.characters || '').slice(0, 50);
    // 굵기: Figma 숫자값 우선(가장 정확) → 스타일명 정규화 매핑 → 그래도 모르면 null(비교 스킵)
    var fw = (typeof node.fontWeight === 'number') ? node.fontWeight : weightFromStyle(sty);
    style = {
      color: fillRgb(node) || 'rgb(0, 0, 0)', backgroundColor: 'rgba(0, 0, 0, 0)',
      fontSize: r1(node.fontSize), fontWeight: fw, fontFamily: fam, lineHeight: 0,
      borderRadius: 0, borderWidth: 0, borderColor: 'rgb(0, 0, 0)',
      paddingTop: 0, paddingRight: 0, paddingBottom: 0, paddingLeft: 0,
      textAlign: align === 'left' ? 'start' : (align === 'right' ? 'end' : align),
      opacity: r1(node.opacity != null ? node.opacity : 1)
    };
  } else {
    // 모서리: 원=한 변 절반(완전둥금 표시), 나머지=cornerRadius(혼합이면 topLeft). 원/알약 정합은 비교 단계에서 '둥금' 범주로 판정.
    var radius;
    if (node.type === 'ELLIPSE') { radius = Math.min(bb.width, bb.height) / 2; }
    else { radius = (typeof node.cornerRadius === 'number') ? node.cornerRadius : (typeof node.topLeftRadius === 'number' ? node.topLeftRadius : 0); }
    var topStroke = (node.strokes && node.strokes.length) ? strokeW(node) : 0;
    text = aggText(node);
    style = {
      color: 'rgb(31, 41, 55)', backgroundColor: fillRgb(node) || 'rgba(0, 0, 0, 0)',
      fontSize: 16, fontWeight: 400, fontFamily: '', lineHeight: 0,
      borderRadius: r1(radius), borderWidth: r1(topStroke), borderColor: strokeRgb(node) || 'rgb(31, 41, 55)',
      paddingTop: r1(node.paddingTop || 0), paddingRight: r1(node.paddingRight || 0),
      paddingBottom: r1(node.paddingBottom || 0), paddingLeft: r1(node.paddingLeft || 0),
      textAlign: 'start', opacity: r1(node.opacity != null ? node.opacity : 1)
    };
  }
  return {
    id: node.id, name: node.name, role: node.type, isText: isText, text: text,
    box: box, style: style, contentZone: node.name.indexOf('content/') === 0
  };
}

function readDesign(root) {
  var rootBox = root.absoluteBoundingBox;
  var W = rootBox.width, H = rootBox.height;
  var raw = [];
  var VEC = /^(VECTOR|BOOLEAN_OPERATION|LINE|STAR|POLYGON)$/;
  function walk(node) {
    if (node.id !== root.id && node.visible !== false && node.absoluteBoundingBox) {
      var bb = node.absoluteBoundingBox;
      // 아이콘 조각(작은 벡터/불리언 등)은 제외 — 개발화면은 아이콘을 이미지 1개로 그려서 값 비교 자체가 불가한 노이즈
      var iconFrag = VEC.test(node.type) && Math.max(bb.width, bb.height) < 32;
      var meaningful = !iconFrag && ((node.type === 'TEXT') || (fillRgb(node) != null) || hasVisibleStroke(node));
      if (meaningful) {
        var el = readElement(node, rootBox);
        // 화면(프레임) 밖에 있는 요소는 제외 (예: 저 아래 붙은 중복 푸터)
        if (el) {
          var b = el.box;
          var offFrame = (b.y >= H) || (b.y + b.h <= 0) || (b.x >= W) || (b.x + b.w <= 0);
          if (!offFrame) raw.push(el);
        }
      }
    }
    if ('children' in node) { for (var i = 0; i < node.children.length; i++) walk(node.children[i]); }
  }
  walk(root);
  // 거의 같은 자리·같은 종류의 겹친 레이어는 하나만 (컴포넌트 래퍼+배경 중복 제거)
  function nearSame(a, b) {
    return a.isText === b.isText && Math.abs(a.box.x - b.box.x) <= 1 && Math.abs(a.box.y - b.box.y) <= 1 && Math.abs(a.box.w - b.box.w) <= 1 && Math.abs(a.box.h - b.box.h) <= 1;
  }
  var out = [];
  raw.forEach(function (el) { for (var i = 0; i < out.length; i++) { if (nearSame(out[i], el)) return; } out.push(el); });
  return {
    meta: { label: 'design', source: 'figma', rootId: root.id, frameName: root.name, artboardWidth: r1(W), artboardHeight: r1(H), toolVersion: '2.1' },
    elements: out
  };
}

// 개발화면 이미지를 정답 프레임 오른쪽에 나란히 놓기
async function placeDevImage(anchorId, bytes, label) {
  var anchor = await figma.getNodeByIdAsync(anchorId);
  if (!anchor || !anchor.absoluteBoundingBox) throw new Error('정답 프레임을 찾을 수 없어요. 먼저 "정답 값 읽기"를 해주세요.');
  var image = figma.createImage(new Uint8Array(bytes));
  var size = await image.getSizeAsync();
  var frameW = anchor.width;
  var frameH = Math.max(1, Math.round(frameW * (size.height / size.width)));
  var f = figma.createFrame();
  f.name = '🖥 개발화면' + (label ? ' · ' + label : '');
  f.resize(frameW, frameH);
  f.fills = [{ type: 'IMAGE', imageHash: image.hash, scaleMode: 'FILL' }];
  f.x = anchor.x + anchor.width + 160;
  f.y = anchor.y;
  if (anchor.parent) anchor.parent.appendChild(f); else figma.currentPage.appendChild(f);
  // 라벨 — 폰트를 '먼저 로드'한 뒤 fontName 설정(안 그러면 set_fontName: unloaded font 에러). 한글 되는 폰트 폴백 사용.
  try {
    var capFont = await ensureReportFont();
    var cap = figma.createText();
    cap.fontName = capFont;
    cap.characters = '🖥 개발화면 (캡처)'; cap.fontSize = 28;
    cap.x = f.x; cap.y = f.y - 44;
    if (anchor.parent) anchor.parent.appendChild(cap); else figma.currentPage.appendChild(cap);
  } catch (e) { /* 캡션 실패는 무시(배치는 성공) */ }
  figma.currentPage.selection = [f];
  figma.viewport.scrollAndZoomIntoView([anchor, f]);
  return { id: f.id, w: frameW, h: frameH };
}

// ---- Figma 검수결과서: 정답 위 불일치에 빨간 핀 + 번호, 옆에 이슈 목록 ----
var reportFont = null;
async function ensureReportFont() {
  if (reportFont) return reportFont;
  var cands = [{ family: 'Pretendard', style: 'Regular' }, { family: 'Noto Sans KR', style: 'Regular' }, { family: 'Apple SD Gothic Neo', style: 'Regular' }, { family: 'Malgun Gothic', style: 'Regular' }, { family: 'Inter', style: 'Regular' }];
  for (var i = 0; i < cands.length; i++) { try { await figma.loadFontAsync(cands[i]); reportFont = cands[i]; return reportFont; } catch (e) {} }
  reportFont = { family: 'Inter', style: 'Regular' }; return reportFont;
}
async function buildFigmaReport(rootId, issues) {
  var root = await figma.getNodeByIdAsync(rootId);
  if (!root || !root.absoluteBoundingBox) throw new Error('정답 프레임을 찾을 수 없어요. 먼저 정답을 읽고 대조해 주세요.');
  var font = await ensureReportFont();
  var rb = root.absoluteBoundingBox;
  var RED = { r: 0.86, g: 0.15, b: 0.15 };
  var pins = [];
  for (var i = 0; i < issues.length; i++) {
    var iss = issues[i];
    var node = iss.id ? await figma.getNodeByIdAsync(iss.id) : null;
    if (!node || !node.absoluteBoundingBox) continue;
    var bb = node.absoluteBoundingBox;
    var box = figma.createRectangle();
    box.x = bb.x; box.y = bb.y; box.resize(Math.max(6, bb.width), Math.max(6, bb.height));
    box.fills = [{ type: 'SOLID', color: RED, opacity: 0.06 }];
    box.strokes = [{ type: 'SOLID', color: RED }]; box.strokeWeight = 2; box.cornerRadius = 4;
    box.name = '검수 ' + iss.no;
    figma.currentPage.appendChild(box); pins.push(box);
    var badge = figma.createEllipse();
    badge.resize(24, 24); badge.x = bb.x - 10; badge.y = bb.y - 10;
    badge.fills = [{ type: 'SOLID', color: RED }];
    figma.currentPage.appendChild(badge); pins.push(badge);
    var t = figma.createText(); t.fontName = font; t.characters = String(iss.no); t.fontSize = 13;
    t.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 } }];
    t.resize(24, 24); t.textAlignHorizontal = 'CENTER'; t.textAlignVertical = 'CENTER'; t.x = bb.x - 10; t.y = bb.y - 10;
    figma.currentPage.appendChild(t); pins.push(t);
  }
  var pinGroup = pins.length ? figma.group(pins, figma.currentPage) : null;
  if (pinGroup) pinGroup.name = '🔴 검수 핀 (' + issues.length + ')';

  var list = figma.createFrame();
  list.name = '📋 개발화면 검수결과';
  list.layoutMode = 'VERTICAL'; list.itemSpacing = 10;
  list.paddingTop = 24; list.paddingBottom = 24; list.paddingLeft = 24; list.paddingRight = 24;
  list.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 } }];
  list.strokes = [{ type: 'SOLID', color: { r: 0.9, g: 0.9, b: 0.92 } }]; list.strokeWeight = 1; list.cornerRadius = 10;
  figma.currentPage.appendChild(list);
  list.resize(560, 100);
  list.primaryAxisSizingMode = 'AUTO'; list.counterAxisSizingMode = 'FIXED';
  list.x = rb.x + rb.width + 160; list.y = rb.y;

  var title = figma.createText(); title.fontName = font; title.characters = '개발화면 검수결과 · ' + issues.length + '건';
  title.fontSize = 20; title.fills = [{ type: 'SOLID', color: { r: 0.1, g: 0.11, b: 0.13 } }];
  list.appendChild(title); title.layoutSizingHorizontal = 'FILL';
  for (var j = 0; j < issues.length; j++) {
    var row = figma.createText(); row.fontName = font;
    var s = issues[j].no + '.  ' + issues[j].name + (issues[j].summary ? ('   —   ' + issues[j].summary) : '');
    row.characters = s; row.fontSize = 14; row.fills = [{ type: 'SOLID', color: { r: 0.23, g: 0.25, b: 0.28 } }];
    list.appendChild(row); row.layoutSizingHorizontal = 'FILL';
  }
  if (!issues.length) {
    var none = figma.createText(); none.fontName = font; none.characters = '고쳐야 할 것이 없습니다 🎉'; none.fontSize = 14;
    none.fills = [{ type: 'SOLID', color: { r: 0.09, g: 0.64, b: 0.29 } }];
    list.appendChild(none); none.layoutSizingHorizontal = 'FILL';
  }
  var out = [list.id]; if (pinGroup) out.push(pinGroup.id);
  figma.currentPage.selection = pinGroup ? [pinGroup] : [list];
  figma.viewport.scrollAndZoomIntoView([root, list]);
  return { created: out, count: issues.length };
}

function postSelection() {
  var sel = figma.currentPage.selection;
  if (!sel || sel.length === 0) { figma.ui.postMessage({ type: 'selection', node: null }); return; }
  var n = sel[0];
  var ok = ('children' in n) && !!n.absoluteBoundingBox;
  figma.ui.postMessage({ type: 'selection', node: { id: n.id, name: n.name, type: n.type, selectable: ok } });
}
figma.on('selectionchange', postSelection);

figma.ui.onmessage = async function (msg) {
  try {
    if (msg.type === 'init') { postSelection(); }
    else if (msg.type === 'read-design') {
      var sel = figma.currentPage.selection;
      if (!sel || sel.length === 0) { figma.ui.postMessage({ type: 'design-read', error: '피그마에서 정답이 될 프레임(화면)을 먼저 선택해 주세요.' }); return; }
      var root = sel[0];
      if (!('children' in root) || !root.absoluteBoundingBox) { figma.ui.postMessage({ type: 'design-read', error: '이 항목은 프레임이 아니에요. 화면 전체 프레임을 골라주세요.' }); return; }
      var data = readDesign(root);
      if (data.elements.length === 0) { figma.ui.postMessage({ type: 'design-read', error: '읽을 요소가 없어요. 색·글자·테두리가 있는 요소가 있는 프레임인지 확인해 주세요.' }); return; }
      figma.ui.postMessage({ type: 'design-read', data: data });
    }
    else if (msg.type === 'place-dev-image') {
      try {
        var res = await placeDevImage(msg.anchorId, msg.bytes, msg.label);
        figma.ui.postMessage({ type: 'dev-image-placed', ok: true, info: res });
      } catch (e) {
        figma.ui.postMessage({ type: 'dev-image-placed', ok: false, error: String(e && e.message ? e.message : e) });
      }
    }
    else if (msg.type === 'build-figma-report') {
      try {
        var rep = await buildFigmaReport(msg.rootId, msg.issues || []);
        figma.ui.postMessage({ type: 'figma-report-built', ok: true, info: rep });
      } catch (e) {
        figma.ui.postMessage({ type: 'figma-report-built', ok: false, error: String(e && e.message ? e.message : e) });
      }
    }
    else if (msg.type === 'go-to-node') {
      var node = await figma.getNodeByIdAsync(msg.nodeId);
      if (node) { figma.currentPage.selection = [node]; figma.viewport.scrollAndZoomIntoView([node]); }
    }
    else if (msg.type === 'resize') { figma.ui.resize(Math.max(400, msg.width | 0), Math.max(480, msg.height | 0)); }
    else if (msg.type === 'notify') { figma.notify(msg.message); }
  } catch (err) {
    figma.ui.postMessage({ type: 'design-read', error: String(err && err.message ? err.message : err) });
  }
};
