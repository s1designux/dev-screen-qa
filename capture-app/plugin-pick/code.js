// Figma에서 드래그로 고른 화면을 '촬영 준비' 사이트로 보낸다.
// 읽기만 한다. 파일을 고치지 않는다.
//
// 2026-09-10 덧붙임: 고른 프레임에 이미 검수 화면이 있으면 단추가 '검수 시안 바꾸기'가 된다.
// 그때는 촬영 준비를 거치지 않고 검수 포털(내 PC, 8765)로 그림·요소·설정을 바로 보낸다. Figma 토큰이 필요 없다.

figma.showUI(__html__, { width: 340, height: 520 });

function 펼치기(노드들) {
  // 섹션을 골랐으면 그 안의 화면까지 펼친다.
  var 나온것 = [];
  노드들.forEach(function (n) {
    if (n.type === 'SECTION') {
      나온것 = 나온것.concat(펼치기(n.children));
    } else if (['FRAME', 'COMPONENT', 'COMPONENT_SET', 'INSTANCE', 'GROUP'].indexOf(n.type) >= 0) {
      나온것.push(n);
    }
  });
  return 나온것;
}

function 줄세우기(노드들) {
  // 캔버스에 놓인 대로 — 위 줄부터, 줄 안에서는 왼쪽부터.
  var 남은 = 노드들.slice().sort(function (a, b) {
    return a.absoluteBoundingBox.y - b.absoluteBoundingBox.y ||
           a.absoluteBoundingBox.x - b.absoluteBoundingBox.x;
  });
  var 결과 = [];
  while (남은.length) {
    var 기준 = 남은[0];
    var 띠 = Math.max(40, 기준.absoluteBoundingBox.height * 0.5);
    var 한줄 = 남은.filter(function (n) {
      return n.absoluteBoundingBox.y - 기준.absoluteBoundingBox.y <= 띠;
    });
    남은 = 남은.filter(function (n) { return 한줄.indexOf(n) < 0; });
    한줄.sort(function (a, b) { return a.absoluteBoundingBox.x - b.absoluteBoundingBox.x; });
    결과 = 결과.concat(한줄);
  }
  return 결과;
}

function 상자(n, 틀) {
  var b = n.absoluteBoundingBox;
  if (!b || !틀) return null;
  return {
    x: Math.round(((b.x - 틀.x) / 틀.width) * 1000) / 10,      // 화면 안 자리(%)
    y: Math.round(((b.y - 틀.y) / 틀.height) * 1000) / 10,
    w: Math.round((b.width / 틀.width) * 1000) / 10,
    h: Math.round((b.height / 틀.height) * 1000) / 10
  };
}

function 색글(paint) {
  if (!paint || paint.type !== 'SOLID' || paint.visible === false) return '';
  var c = paint.color;
  function 두자리(v) { var h = Math.round(v * 255).toString(16); return h.length < 2 ? '0' + h : h; }
  var 글 = '#' + (두자리(c.r) + 두자리(c.g) + 두자리(c.b)).toUpperCase();
  if (paint.opacity !== undefined && paint.opacity < 1) 글 += ' ' + Math.round(paint.opacity * 100) + '%';
  return 글;
}

function 첫색(칠) {
  if (!칠 || 칠 === figma.mixed || !칠.length) return '';
  for (var i = 0; i < 칠.length; i++) {
    var g = 색글(칠[i]);
    if (g) return g;
  }
  return '';
}

function 값읽기(n) {
  // 시안의 '지금 값' — 검수 때 원본값으로 쓴다.
  var v = {};
  var 배경 = 첫색(n.fills);
  if (배경) v[n.type === 'TEXT' ? '글자색' : '배경색'] = 배경;
  var 테두리 = 첫색(n.strokes);
  if (테두리) {
    v['테두리색'] = 테두리;
    if (typeof n.strokeWeight === 'number') v['테두리굵기'] = n.strokeWeight;
  }
  if (typeof n.cornerRadius === 'number' && n.cornerRadius) v['모서리'] = n.cornerRadius;
  if (n.absoluteBoundingBox) {
    v['폭'] = Math.round(n.absoluteBoundingBox.width);
    v['높이'] = Math.round(n.absoluteBoundingBox.height);
  }
  if (n.type === 'TEXT') {
    if (n.fontName && n.fontName !== figma.mixed) {
      v['글꼴'] = n.fontName.family;
      v['굵기'] = n.fontName.style;
    }
    if (typeof n.fontSize === 'number') v['글자크기'] = n.fontSize;
    if (n.lineHeight && n.lineHeight !== figma.mixed && n.lineHeight.unit !== 'AUTO') {
      v['줄간격'] = n.lineHeight.value + (n.lineHeight.unit === 'PERCENT' ? '%' : '');
    }
    if (n.textAlignHorizontal) v['가로정렬'] = n.textAlignHorizontal;
  }
  if (typeof n.opacity === 'number' && n.opacity < 1) v['투명도'] = Math.round(n.opacity * 100) + '%';
  return v;
}

function 속알맹이(뿌리) {
  // 화면 안에 무엇이 있는지 — 글자와 아이콘 이름·자리. 동작 초안을 짓는 데 쓴다.
  var 틀 = 뿌리.absoluteBoundingBox;
  var 모은것 = [];
  function 훑기(n, 깊이) {
    if (모은것.length > 300 || 깊이 > 6) return;
    var 자리 = 상자(n, 틀);
    var 아이콘같음 = /eye|visib|보기|숨김|icon|^ic[_-]|toggle/i.test(n.name || '');
    if (자리 && (n.type === 'TEXT' || 깊이 <= 4 || 아이콘같음)) {
      모은것.push({
        이름: n.name, 종류: n.type,
        글자: n.type === 'TEXT' ? String(n.characters || '').trim() : '',
        자리: 자리,
        값: 값읽기(n)
      });
    }
    if ('children' in n) n.children.forEach(function (c) { 훑기(c, 깊이 + 1); });
  }
  if ('children' in 뿌리) 뿌리.children.forEach(function (c) { 훑기(c, 1); });
  return 모은것;
}

// ── 검수 포털용 요소 목록 ───────────────────────────────────────────────
// 검수기(dev-screen-qa/plugin-image-qa/code.js)의 collectDesign()과 같은 모양을 만든다.
// 포털의 자동 검수가 이 목록으로 정렬·차이 찾기를 하므로, 저쪽 규칙을 바꾸면 여기도 같이 고친다.
function 소수1(n) { return Math.round(n * 10) / 10; }
function 이오오(n) { return Math.round(n * 255); }
function 검수색(paint) {
  if (!paint || paint.type !== 'SOLID' || paint.visible === false) return null;
  var c = paint.color, a = paint.opacity == null ? 1 : paint.opacity;
  if (a < 1) return 'rgba(' + 이오오(c.r) + ', ' + 이오오(c.g) + ', ' + 이오오(c.b) + ', ' + 소수1(a) + ')';
  return '#' + [c.r, c.g, c.b].map(function (v) { var s = 이오오(v).toString(16).toUpperCase(); return s.length < 2 ? '0' + s : s; }).join('');
}
function 검수첫색(items) {
  if (!Array.isArray(items)) return null;
  for (var i = 0; i < items.length; i++) { var c = 검수색(items[i]); if (c) return c; }
  return null;
}
function 안전수(v) { return typeof v === 'number' && isFinite(v) ? 소수1(v) : null; }
function 안전글꼴(node) {
  try { if (node.fontName && node.fontName !== figma.mixed && node.fontName.family) return { family: node.fontName.family, style: node.fontName.style || '' }; } catch (e) {}
  return { family: '혼합', style: '' };
}
function 안전줄높이(node) {
  try {
    var h = node.lineHeight;
    if (h === figma.mixed || !h) return null;
    if (h.unit === 'AUTO') return '자동';
    if (h.unit === 'PIXELS') return 소수1(h.value);
    if (h.unit === 'PERCENT') return 소수1(h.value) + '%';
  } catch (e) {}
  return null;
}
function 안전둥글기(node) {
  try {
    if (typeof node.cornerRadius === 'number') return 소수1(node.cornerRadius);
    if (typeof node.topLeftRadius === 'number') return 소수1(node.topLeftRadius);
  } catch (e) {}
  return null;
}
function 안전테두리(node) {
  try { if (typeof node.strokeWeight === 'number') return 소수1(node.strokeWeight); } catch (e) {}
  try { if (typeof node.strokeTopWeight === 'number') return 소수1(node.strokeTopWeight); } catch (e) {}
  return null;
}
function 글자속성이름(node) {
  try { var refs = node.componentPropertyReferences; if (refs && refs.characters) return String(refs.characters).replace(/#.*$/, ''); } catch (e) {}
  return null;
}
function 검수요소하나(node, rootBox, depth, parentId, parentType, chain) {
  var bb = node.absoluteBoundingBox;
  if (!bb || bb.width < 1 || bb.height < 1) return null;
  var box = { x: 소수1(bb.x - rootBox.x), y: 소수1(bb.y - rootBox.y), w: 소수1(bb.width), h: 소수1(bb.height) };
  var base = { id: node.id, name: node.name || node.type, type: node.type, box: box, depth: depth, parentId: parentId || null, parentType: parentType || null };
  if (node.type === 'TEXT') {
    var fn = 안전글꼴(node);
    base.kind = 'text';
    base.text = String(node.characters || '').slice(0, 120);
    base.chain = (chain || []).slice(0, 4);
    base.propRef = 글자속성이름(node);
    base.values = { text: base.text, fontSize: 안전수(node.fontSize), fontWeight: 안전수(node.fontWeight), fontFamily: fn.family, fontStyle: fn.style,
                    lineHeight: 안전줄높이(node), color: 검수첫색(node.fills), textAlign: node.textAlignHorizontal || null };
    return base;
  }
  var fill = null, stroke = null, hasImage = false;
  try { fill = 검수첫색(node.fills); } catch (e) {}
  try { hasImage = Array.isArray(node.fills) && node.fills.some(function (p) { return p && p.type === 'IMAGE' && p.visible !== false; }); } catch (e1) {}
  try { stroke = 검수첫색(node.strokes); } catch (e2) {}
  if (!fill && !stroke && !hasImage && !/^(FRAME|COMPONENT|INSTANCE|GROUP|SECTION|RECTANGLE|ELLIPSE)$/.test(node.type)) return null;
  base.kind = hasImage ? 'image' : /^(VECTOR|BOOLEAN_OPERATION|STAR|POLYGON|LINE)$/.test(node.type) ? 'icon' : 'shape';
  base.text = '';
  base.values = { width: 소수1(bb.width), height: 소수1(bb.height), fill: fill, stroke: stroke, strokeWidth: 안전테두리(node), radius: 안전둥글기(node), opacity: 안전수(node.opacity) };
  return base;
}
function 검수요소(root) {
  var rb = root.absoluteBoundingBox, items = [];
  function walk(n, depth, parentId, parentType, chain) {
    if (n.id !== root.id && n.visible !== false && n.absoluteBoundingBox) {
      var el = 검수요소하나(n, rb, depth, parentId, parentType, chain);
      if (el) {
        var b = el.box;
        if (b.x < rb.width && b.y < rb.height && b.x + b.w > 0 && b.y + b.h > 0) items.push(el);
      }
    }
    var nextChain = n.id === root.id ? [] : [{ n: String(n.name || ''), t: n.type }].concat(chain || []).slice(0, 4);
    if ('children' in n) for (var i = 0; i < n.children.length; i++) walk(n.children[i], depth + 1, n.id, n.type, nextChain);
  }
  walk(root, 0, null, null, []);
  return items;
}
function 검수설정(node) {
  // 검수기에서 사람이 정한 설정(화면 종류·글자 가변 여부). 공유 칸(devScreenQa) 먼저, 없으면 예전 개인 칸.
  var raw = '';
  try { if (node.getSharedPluginData) raw = node.getSharedPluginData('devScreenQa', 'imageQaPolicy') || ''; } catch (e) {}
  if (!raw) { try { raw = node.getPluginData ? node.getPluginData('imageQaPolicy') || '' : ''; } catch (e2) {} }
  if (!raw) return null;
  try { var p = JSON.parse(raw); return p && typeof p === 'object' ? p : null; } catch (e3) { return null; }
}

function 파일열쇠() { try { return figma.fileKey || ''; } catch (e) { return ''; } }

function 알리기() {
  var 고른것 = 줄세우기(펼치기(figma.currentPage.selection.slice()));
  figma.ui.postMessage({
    갈래: '고른것',
    페이지: figma.currentPage.name,
    파일열쇠: 파일열쇠(),
    파일이름: figma.root.name,
    화면들: 고른것.map(function (n) {
      var b = n.absoluteBoundingBox;
      return { id: n.id, 이름: n.name, 폭: Math.round(b.width), 높이: Math.round(b.height),
               x: Math.round(b.x), y: Math.round(b.y) };
    })
  });
}

figma.on('selectionchange', 알리기);
알리기();

figma.ui.onmessage = async function (msg) {
  if (msg.갈래 === '사이트열기') {
    figma.openExternal('http://localhost:8767');
    return;
  }
  if (msg.갈래 === '검수열기') {
    if (msg.주소) figma.openExternal(msg.주소);
    return;
  }
  if (msg.갈래 === '검수시안보내기') {
    // 대상: [{id, page}] — 검수 화면이 있는 프레임만. 촬영 준비를 거치지 않는다.
    var 대상 = msg.대상 || [];
    for (var k = 0; k < 대상.length; k++) {
      var node = await figma.getNodeByIdAsync(대상[k].id);
      if (!node || !node.absoluteBoundingBox) { figma.ui.postMessage({ 갈래: '검수부치기', 실패: '프레임을 찾지 못했어요.', page: 대상[k].page }); continue; }
      var bb = node.absoluteBoundingBox;
      figma.ui.postMessage({ 갈래: '진행', 지금: k + 1, 전부: 대상.length });
      var 배율 = Math.min(1, 4096 / Math.max(1, Math.max(bb.width, bb.height)));   // 검수기와 같은 배율(원본 해상도)
      var 그림 = await node.exportAsync({ format: 'PNG', constraint: { type: 'SCALE', value: 배율 } });
      figma.ui.postMessage({
        갈래: '검수부치기', page: 대상[k].page, 마지막: k === 대상.length - 1,
        프레임: { id: node.id, name: node.name, width: 소수1(bb.width), height: 소수1(bb.height), png: Array.from(그림),
                elements: 검수요소(node), policy: 검수설정(node) }
      });
    }
    return;
  }
  if (msg.갈래 !== '보내기') return;
  var 고른것 = 줄세우기(펼치기(figma.currentPage.selection.slice()));
  if (!고른것.length) {
    figma.ui.postMessage({ 갈래: '알림', 글: '먼저 캔버스에서 화면을 골라 주세요.' });
    return;
  }
  var 보낼것 = [];
  for (var i = 0; i < 고른것.length; i++) {
    var n = 고른것[i];
    var b = n.absoluteBoundingBox;
    figma.ui.postMessage({ 갈래: '진행', 지금: i + 1, 전부: 고른것.length });
    var 배율 = b.width > 2200 ? 0.5 : 1;      // 너무 큰 화면은 반으로 (파일 크기)
    var 그림 = await n.exportAsync({ format: 'PNG', constraint: { type: 'SCALE', value: 배율 } });
    보낼것.push({
      id: n.id, 이름: n.name, 폭: Math.round(b.width), 높이: Math.round(b.height),
      x: Math.round(b.x), y: Math.round(b.y), 그림: Array.from(그림),
      속: 속알맹이(n),
      // 검수 포털의 자동 검수용(검수기와 같은 모양의 요소 목록·사람이 정한 설정). 촬영 준비 → 검수 접수 때 포털에 함께 들어간다.
      검수요소: 검수요소(n), 검수설정: 검수설정(n), 틀: { 폭: 소수1(b.width), 높이: 소수1(b.height) }
    });
  }
  figma.ui.postMessage({
    갈래: '부치기',
    꾸러미: {
      파일이름: figma.root.name,
      파일열쇠: figma.fileKey || '',
      페이지이름: figma.currentPage.name,
      화면들: 보낼것
    }
  });
};
