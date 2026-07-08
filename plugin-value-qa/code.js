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
function hasVisibleStroke(node) {
  return strokeRgb(node) != null && ((node.strokeWeight || 0) > 0 || (node.strokeBottomWeight || 0) > 0 || (node.strokeTopWeight || 0) > 0);
}
// 상자의 대표 글자(자식들 글자 합침) — 짝맞춤 힌트용
function aggText(node) {
  var t = '';
  (function w(x) { if (x.type === 'TEXT') { t += (x.characters || '') + ' '; } if ('children' in x) { for (var i = 0; i < x.children.length; i++) w(x.children[i]); } })(node);
  return t.replace(/\s+/g, ' ').trim().slice(0, 50);
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
    style = {
      color: fillRgb(node) || 'rgb(0, 0, 0)', backgroundColor: 'rgba(0, 0, 0, 0)',
      fontSize: r1(node.fontSize), fontWeight: WEIGHT[sty] || 400, fontFamily: fam, lineHeight: 0,
      borderRadius: 0, borderWidth: 0, borderColor: 'rgb(0, 0, 0)',
      paddingTop: 0, paddingRight: 0, paddingBottom: 0, paddingLeft: 0,
      textAlign: align === 'left' ? 'start' : (align === 'right' ? 'end' : align),
      opacity: r1(node.opacity != null ? node.opacity : 1)
    };
  } else {
    var radius = (node.type === 'ELLIPSE') ? 999 : (typeof node.cornerRadius === 'number' ? node.cornerRadius : 0);
    var topStroke = 0;
    if (node.strokes && node.strokes.length) { topStroke = (node.strokeTopWeight != null) ? node.strokeTopWeight : (node.strokeWeight || 0); }
    text = aggText(node);
    style = {
      color: 'rgb(31, 41, 55)', backgroundColor: fillRgb(node) || 'rgba(0, 0, 0, 0)',
      fontSize: 16, fontWeight: 400, fontFamily: 'Inter', lineHeight: 0,
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
  var out = [];
  function walk(node) {
    if (node.id !== root.id && node.visible !== false && node.absoluteBoundingBox) {
      var meaningful = (node.type === 'TEXT') || (fillRgb(node) != null) || hasVisibleStroke(node);
      if (meaningful) { var el = readElement(node, rootBox); if (el) out.push(el); }
    }
    if ('children' in node) { for (var i = 0; i < node.children.length; i++) walk(node.children[i]); }
  }
  walk(root);
  return {
    meta: { label: 'design', source: 'figma', rootId: root.id, frameName: root.name, artboardWidth: r1(rootBox.width), artboardHeight: r1(rootBox.height), toolVersion: '2.0' },
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
  // 라벨
  var cap = figma.createText();
  cap.fontName = { family: 'Inter', style: 'Regular' };
  try { await figma.loadFontAsync({ family: 'Inter', style: 'Regular' }); cap.characters = '🖥 개발화면 (캡처)'; cap.fontSize = 28; cap.x = f.x; cap.y = f.y - 44; if (anchor.parent) anchor.parent.appendChild(cap); } catch (e) { cap.remove(); }
  figma.currentPage.selection = [f];
  figma.viewport.scrollAndZoomIntoView([anchor, f]);
  return { id: f.id, w: frameW, h: frameH };
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
