// Figma에서 드래그로 고른 화면을 '촬영 준비' 사이트로 보낸다.
// 읽기만 한다. 파일을 고치지 않는다.

figma.showUI(__html__, { width: 340, height: 460 });

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

function 알리기() {
  var 고른것 = 줄세우기(펼치기(figma.currentPage.selection.slice()));
  figma.ui.postMessage({
    갈래: '고른것',
    페이지: figma.currentPage.name,
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
      속: 속알맹이(n)
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
