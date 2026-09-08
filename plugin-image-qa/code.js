// 개발화면 검수기 — Figma 문서 읽기와 캔버스 결과 표시.
// 이미지 비교는 ui.html의 로컬 Canvas 엔진이 맡고, 이 파일은 살아 있는 디자인값과
// 개발 캡처 위 번호·영역·기준값 쪽지를 만든다. 외부 통신과 자동 오류 확정은 없다.

figma.showUI(__html__, { width: 390, height: 720, themeColors: true });

var RESULT_MARK = "imageQaResult";
var CANDIDATE_MARK = "imageQaCandidate";
var OVERLAY_MARK = "imageQaOverlay";
var COMPARE_MARK = "imageQaCompare";
var REPORT_MARK = "imageQaReport";
var reportNodeByPair = {};
var compareNodeByPair = {};
var lastProgrammaticSelectionAt = 0;
var TRIM_KEY = "imageQaTopTrim";
var BOTTOM_TRIM_KEY = "imageQaBottomTrim"; // 사람이 정한 검수 범위(캡처 아래쪽 제외 px). 모바일 하단 내비게이션·홈 바를 빼는 데 쓴다.
var OVERLAY_FIX_KEY = "imageQaOverlayFix";
var POLICY_KEY = "imageQaPolicy"; // 디자인 프레임에 두는 작은 설정값: 화면 종류(공통/일반)와 사람이 정한 글자 가변 여부. 검수 결과가 아니라 설정이다. // 사람이 직접 끌어 맞춘 겹쳐보기 위치(캡처 노드 좌표계) // 사람이 정한 검수 범위(캡처 위쪽 제외 px). 캡처 노드에 남겨 다음 검수에도 쓴다.
var resultNodeByPair = {};
var candidateNodeById = {};
var overlayNodeByPair = {};

function round1(n) { return Math.round(n * 10) / 10; }
function to255(n) { return Math.round(n * 255); }
function colorString(paint) {
  if (!paint || paint.type !== "SOLID" || paint.visible === false) return null;
  var c = paint.color;
  var a = paint.opacity == null ? 1 : paint.opacity;
  if (a < 1) return "rgba(" + to255(c.r) + ", " + to255(c.g) + ", " + to255(c.b) + ", " + round1(a) + ")";
  return "#" + [c.r, c.g, c.b].map(function (v) {
    var s = to255(v).toString(16).toUpperCase(); return s.length < 2 ? "0" + s : s;
  }).join("");
}
function firstSolid(items) {
  if (!Array.isArray(items)) return null;
  for (var i = 0; i < items.length; i++) { var c = colorString(items[i]); if (c) return c; }
  return null;
}
function safeNumber(v) { return typeof v === "number" && isFinite(v) ? round1(v) : null; }
function safeFont(node) {
  try {
    if (node.fontName && node.fontName !== figma.mixed && node.fontName.family) {
      return { family: node.fontName.family, style: node.fontName.style || "" };
    }
  } catch (e) {}
  return { family: "혼합", style: "" };
}
function safeLineHeight(node) {
  try {
    var h = node.lineHeight;
    if (h === figma.mixed || !h) return null;
    if (h.unit === "AUTO") return "자동";
    if (h.unit === "PIXELS") return round1(h.value);
    if (h.unit === "PERCENT") return round1(h.value) + "%";
  } catch (e) {}
  return null;
}
function safeRadius(node) {
  try {
    if (typeof node.cornerRadius === "number") return round1(node.cornerRadius);
    if (typeof node.topLeftRadius === "number") return round1(node.topLeftRadius);
  } catch (e) {}
  return null;
}
function safeStrokeWidth(node) {
  try { if (typeof node.strokeWeight === "number") return round1(node.strokeWeight); } catch (e) {}
  try { if (typeof node.strokeTopWeight === "number") return round1(node.strokeTopWeight); } catch (e) {}
  return null;
}

function textPropRef(node) {
  // 이 글자가 컴포넌트의 어느 글자 속성(label, placeholder, value…)에 묶여 있는지. 없으면 null.
  try {
    var refs = node.componentPropertyReferences;
    if (refs && refs.characters) return String(refs.characters).replace(/#.*$/, "");
  } catch (e) {}
  return null;
}
function readDesignElement(node, rootBox, depth, parentId, parentType, chain) {
  var bb = node.absoluteBoundingBox;
  if (!bb || bb.width < 1 || bb.height < 1) return null;
  var box = {
    x: round1(bb.x - rootBox.x), y: round1(bb.y - rootBox.y),
    w: round1(bb.width), h: round1(bb.height)
  };
  var base = { id: node.id, name: node.name || node.type, type: node.type, box: box, depth: depth, parentId: parentId || null, parentType: parentType || null };
  if (node.type === "TEXT") {
    var fn = safeFont(node);
    base.kind = "text";
    base.text = String(node.characters || "").slice(0, 120);
    base.chain = (chain || []).slice(0, 4); // 가까운 순서의 부모 이름·종류(역할 판단용: Input / Button / Table 행 …)
    base.propRef = textPropRef(node);
    base.values = {
      text: base.text,
      fontSize: safeNumber(node.fontSize),
      fontWeight: safeNumber(node.fontWeight),
      fontFamily: fn.family,
      fontStyle: fn.style,
      lineHeight: safeLineHeight(node),
      color: firstSolid(node.fills),
      textAlign: node.textAlignHorizontal || null
    };
    return base;
  }
  var fill = null, stroke = null, hasImage = false;
  try { fill = firstSolid(node.fills); } catch (e) {}
  try { hasImage = Array.isArray(node.fills) && node.fills.some(function (p) { return p && p.type === "IMAGE" && p.visible !== false; }); } catch (e1) {}
  try { stroke = firstSolid(node.strokes); } catch (e2) {}
  if (!fill && !stroke && !hasImage && !/^(FRAME|COMPONENT|INSTANCE|GROUP|SECTION|RECTANGLE|ELLIPSE)$/.test(node.type)) return null;
  base.kind = hasImage ? "image" : /^(VECTOR|BOOLEAN_OPERATION|STAR|POLYGON|LINE)$/.test(node.type) ? "icon" : "shape";
  base.text = "";
  base.values = {
    width: round1(bb.width), height: round1(bb.height),
    fill: fill, stroke: stroke, strokeWidth: safeStrokeWidth(node),
    radius: safeRadius(node), opacity: safeNumber(node.opacity)
  };
  return base;
}

function collectDesign(root) {
  var rb = root.absoluteBoundingBox;
  var items = [];
  function walk(n, depth, parentId, parentType, chain) {
    if (n.id !== root.id && n.visible !== false && n.absoluteBoundingBox) {
      var el = readDesignElement(n, rb, depth, parentId, parentType, chain);
      if (el) {
        var b = el.box;
        if (b.x < rb.width && b.y < rb.height && b.x + b.w > 0 && b.y + b.h > 0) items.push(el);
      }
    }
    var nextChain = n.id === root.id ? [] : [{ n: String(n.name || ""), t: n.type }].concat(chain || []).slice(0, 4);
    if ("children" in n) for (var i = 0; i < n.children.length; i++) walk(n.children[i], depth + 1, n.id, n.type, nextChain);
  }
  walk(root, 0, null, null, []);
  return items;
}

function readDesignPolicy(node) {
  // 디자인 프레임에 저장된 설정값(화면 종류·글자 가변 여부). 없거나 깨졌으면 null.
  try {
    var raw = node.getPluginData ? node.getPluginData(POLICY_KEY) : "";
    if (!raw) return null;
    var p = JSON.parse(raw);
    return p && typeof p === "object" ? p : null;
  } catch (e) { return null; }
}

function selectableFrame(n) {
  return !!(n && n.absoluteBoundingBox && "children" in n && /^(FRAME|COMPONENT|INSTANCE|SECTION|GROUP)$/.test(n.type));
}

function hasImageFill(node) {
  try {
    if (!node || !Array.isArray(node.fills)) return false;
    return node.fills.some(function (fill) { return fill && fill.type === "IMAGE" && fill.visible !== false; });
  } catch (e) { return false; }
}

function selectableCapture(node) {
  var hasChildren = !!(node && "children" in node && node.children.length);
  return !!(node && node.absoluteBoundingBox && typeof node.exportAsync === "function" && hasImageFill(node) && !hasChildren);
}

function selectionGeometry(selection) {
  var selected = selection || figma.currentPage.selection;
  var designs = [], captures = [];
  selected.forEach(function (node) {
    var bb = node.absoluteBoundingBox;
    if (!bb) return;
    var item = { id: node.id, x: round1(bb.x), y: round1(bb.y), width: round1(bb.width), height: round1(bb.height) };
    if (selectableCapture(node)) captures.push(item);
    else if (selectableFrame(node)) designs.push(item);
  });
  return { designs: designs, captures: captures };
}

function candidateIdFromNode(node) {
  // 번호 표시(그룹)나 그 안의 도형을 눌러도 어느 후보인지 찾아 올라간다.
  var n = node, guard = 0;
  while (n && guard++ < 40) {
    if (n.getPluginData && n.getPluginData(CANDIDATE_MARK)) return n.getPluginData(CANDIDATE_MARK);
    n = n.parent;
  }
  return null;
}
function pairIdFromNode(node) {
  // 검수 결과 프레임·나란히 보기 카드·레포트·겹쳐보기 중 무엇을 눌러도 어느 검수 화면인지 찾는다.
  var n = node, guard = 0, keys = [RESULT_MARK, COMPARE_MARK, REPORT_MARK, OVERLAY_MARK];
  while (n && guard++ < 40) {
    if (n.getPluginData) {
      for (var k = 0; k < keys.length; k++) { var v = n.getPluginData(keys[k]); if (v) return v; }
    }
    n = n.parent;
  }
  return null;
}
function postSelectionStatus() {
  var status = selectionGeometry();
  figma.ui.postMessage({ type: "selection-status", designs: status.designs, captures: status.captures });
  // 캔버스에서 번호를 직접 누른 경우 패널의 같은 번호로 옮겨 준다. (플러그인이 방금 고른 것은 되돌리지 않는다)
  if (Date.now() - lastProgrammaticSelectionAt < 500) return;
  var sel = figma.currentPage.selection;
  for (var i = 0; i < sel.length; i++) {
    var cid = candidateIdFromNode(sel[i]);
    if (cid) { figma.ui.postMessage({ type: "candidate-selected", candidateId: cid }); return; }
  }
  // 번호가 아니라 검수 화면(또는 그 화면의 카드·레포트)을 골랐으면 패널을 그 화면으로 옮긴다.
  for (var j = 0; j < sel.length; j++) {
    var pid = pairIdFromNode(sel[j]);
    if (pid) { figma.ui.postMessage({ type: "result-selected", pairId: pid }); return; }
  }
}

if (typeof figma.on === "function") figma.on("selectionchange", postSelectionStatus);

// 패널을 닫는 순간 캔버스 번호를 다시 또렷하게 되돌린다.
// (검수 중 다른 번호를 흐리게 해 둔 상태가 그대로 남아 문서로 읽기 어려운 문제)
function restoreCandidatesForReading() {
  allCandidateGroups().forEach(function (g) {
    if (g.getPluginData(CANDIDATE_STATUS_KEY) === "excluded") { g.remove(); return; } // 검수 제외는 캔버스에서 지운다
    g.opacity = readingOpacity(g.getPluginData(CANDIDATE_STATUS_KEY));
  });
}
if (typeof figma.on === "function") figma.on("close", restoreCandidatesForReading);

async function exportCaptureNode(node, index) {
  var bb = node.absoluteBoundingBox;
  var maxSide = Math.max(bb.width, bb.height);
  var scale = Math.min(1, 4096 / Math.max(1, maxSide));
  var bytes = await node.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: scale } });
  var topTrim = null, bottomTrim = null, overlayFix = null;
  try { var saved = node.getPluginData ? node.getPluginData(TRIM_KEY) : ""; if (saved !== "") { var n = Number(saved); if (isFinite(n)) topTrim = Math.max(0, Math.round(n * scale)); } } catch (e) {}
  try { var savedB = node.getPluginData ? node.getPluginData(BOTTOM_TRIM_KEY) : ""; if (savedB !== "") { var nb = Number(savedB); if (isFinite(nb)) bottomTrim = Math.max(0, Math.round(nb * scale)); } } catch (eb) {}
  try {
    var savedFix = node.getPluginData ? node.getPluginData(OVERLAY_FIX_KEY) : "";
    if (savedFix !== "") { var f = JSON.parse(savedFix); if (f && isFinite(f.dx) && isFinite(f.dy)) overlayFix = { dx: Math.round(f.dx * scale), dy: Math.round(f.dy * scale) }; }
  } catch (e2) {}
  return {
    id: "figma_" + node.id,
    nodeId: node.id,
    name: node.name || ("Figma 이미지 " + (index + 1)),
    source: "figma",
    x: round1(bb.x), y: round1(bb.y),
    width: round1(bb.width), height: round1(bb.height),
    bytes: Array.from(bytes),
    topTrim: topTrim,
    bottomTrim: bottomTrim,
    overlayFix: overlayFix
  };
}

async function exportSelectedCaptures(selection) {
  var selected = (selection || figma.currentPage.selection).filter(selectableCapture);
  var out = [];
  for (var i = 0; i < selected.length; i++) out.push(await exportCaptureNode(selected[i], i));
  return out;
}

async function exportSelectedDesigns() {
  var selected = figma.currentPage.selection.filter(function (node) {
    return selectableFrame(node) && !selectableCapture(node);
  });
  if (!selected.length) throw new Error("검수할 디자인 프레임을 하나 이상 선택해 주세요.");
  var out = [];
  for (var i = 0; i < selected.length; i++) {
    var root = selected[i];
    var bb = root.absoluteBoundingBox;
    var maxSide = Math.max(bb.width, bb.height);
    var scale = Math.min(1, 4096 / Math.max(1, maxSide)); // 디자인도 원본 해상도로 읽어 작은 아이콘·10px 글자까지 비교한다.
    var bytes = await root.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: scale } });
    out.push({
      id: root.id, name: root.name || ("디자인 " + (i + 1)), type: root.type,
      x: round1(bb.x), y: round1(bb.y),
      width: round1(bb.width), height: round1(bb.height),
      bytes: Array.from(bytes), elements: collectDesign(root), policy: readDesignPolicy(root)
    });
  }
  return out;
}

var reportFont = null;
async function ensureFont() {
  if (reportFont) return reportFont;
  var fonts = [
    { family: "Pretendard", style: "Regular" },
    { family: "Noto Sans KR", style: "Regular" },
    { family: "Apple SD Gothic Neo", style: "Regular" },
    { family: "Malgun Gothic", style: "Regular" },
    { family: "Inter", style: "Regular" }
  ];
  for (var i = 0; i < fonts.length; i++) {
    try { await figma.loadFontAsync(fonts[i]); reportFont = fonts[i]; return reportFont; } catch (e) {}
  }
  reportFont = { family: "Inter", style: "Regular" };
  return reportFont;
}
function paint(hex) {
  hex = hex.replace("#", "");
  return { r: parseInt(hex.slice(0, 2), 16) / 255, g: parseInt(hex.slice(2, 4), 16) / 255, b: parseInt(hex.slice(4, 6), 16) / 255 };
}
function statusColor(status) {
  if (status === "confirmed") return paint("DC2626");
  if (status === "excluded") return paint("6B7280");
  if (status === "variable") return paint("5B7DB1"); // 가변 글자(내용은 검사하지 않음)
  return paint("DC2626"); // 따로 제외하지 않은 후보는 오류확정
}
function statusOpacity(status) { return status === "excluded" ? 0.25 : status === "variable" ? 0.4 : 1; }
// 플러그인 패널을 닫았을 때는 캔버스를 그냥 문서처럼 읽는다.
// 검수 중 흐림(고른 번호만 진하게)은 걷어내고, 가변 글자만 살짝 옅게 남겨 구분한다.
// (검수 제외한 번호는 문서에 남길 필요가 없어 캔버스에서 지운다.)
function readingOpacity(status) { return status === "variable" ? 0.8 : 1; }
var CANDIDATE_STATUS_KEY = "imageQaCandidateStatus";
function makeText(font, value, size, color) {
  var t = figma.createText();
  t.fontName = font; t.characters = value; t.fontSize = size;
  t.fills = [{ type: "SOLID", color: color }];
  return t;
}
async function removeGenerated(pairId, designId) {
  await removeCompareCard(pairId);
  var rep0 = reportNodeByPair[pairId];
  if (rep0) { var repNode = await figma.getNodeByIdAsync(rep0); if (repNode) repNode.remove(); delete reportNodeByPair[pairId]; }
  var id = resultNodeByPair[pairId];
  if (id) {
    var old = await figma.getNodeByIdAsync(id);
    if (old) old.remove();
    delete resultNodeByPair[pairId];
  }
  // 세션이 바뀌어도 같은 디자인의 이전 결과 프레임이 남아 겹치지 않게 정리한다.
  figma.currentPage.findAll(function (n) {
    if (!n.getPluginData || !n.getPluginData(RESULT_MARK)) return false;
    return n.getPluginData(RESULT_MARK) === pairId || (!!designId && n.getPluginData("designId") === designId);
  }).forEach(function (n) { n.remove(); });
}

function findFreeSpot(rb, w, h) {
  var margin = 120;
  var x = rb.x + rb.width + margin, y = rb.y;
  var others = figma.currentPage.children;
  var moved = true, guard = 0;
  while (moved && guard++ < 60) {
    moved = false;
    for (var i = 0; i < others.length; i++) {
      var bb = others[i].absoluteBoundingBox;
      if (!bb) continue;
      var overlap = x < bb.x + bb.width && bb.x < x + w && y < bb.y + bb.height && bb.y < y + h;
      if (overlap) { x = bb.x + bb.width + margin; moved = true; }
    }
  }
  return { x: x, y: y };
}

// ── 번호표(번호 + 검수내용) 자리 정하기 ─────────────────────────────────────
// 원칙: 화면 안(한눈에 보이게)에 두되, 글자·버튼 같은 "내용이 있는 곳"과
//       다른 번호표를 피해서 놓는다. ink는 UI가 캡처를 훑어 만든
//       "내용이 있는 칸" 지도(1=내용 있음). 없으면 겹침만 피한다.
// 순수 계산부라 검증 스크립트에서 그대로 돌려 볼 수 있다.
// ── 화면 맞추기(피그마 패널을 피해서) ────────────────────────────────────────
// 피그마 왼쪽(레이어)·오른쪽(속성) 패널과 이 플러그인 창은 캔버스를 덮는다.
// 그래서 가운데 "안 가려지는 영역"에 맞춰 배율과 위치를 정한다.
var PANEL_LEFT = 250, PANEL_RIGHT = 250, PLUGIN_W = 390, TOOLBAR_TOP = 44, EDGE = 24;
function unionBox(nodes) {
  var box = null;
  nodes.forEach(function (n) {
    var b = n && n.absoluteBoundingBox; if (!b) return;
    if (!box) box = { x: b.x, y: b.y, w: b.width, h: b.height };
    else {
      var x1 = Math.min(box.x, b.x), y1 = Math.min(box.y, b.y);
      var x2 = Math.max(box.x + box.w, b.x + b.width), y2 = Math.max(box.y + box.h, b.y + b.height);
      box = { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
    }
  });
  return box;
}
// room: 대상이 안 가려지는 영역의 몇 배 여유를 두고 들어갈지(1=꽉, 3=주변까지 넓게)
function fitIntoSafeArea(box, room, minZoom, maxZoom) {
  if (!box || !box.w || !box.h) return false;
  var vb = figma.viewport.bounds, z = figma.viewport.zoom;
  var screenW = vb.width * z, screenH = vb.height * z;
  // 이 플러그인 창은 보통 오른쪽 속성 패널 위에 겹쳐 뜬다. 그래서 둘을 더하지 않고 더 넓은 쪽만 뺀다.
  var left = PANEL_LEFT + EDGE, right = Math.max(PANEL_RIGHT, PLUGIN_W + EDGE) + EDGE;
  // 창이 좁아 패널이 대부분을 덮으면, 최소한 화면 가로의 34%는 쓸 수 있게 물러난다.
  var free = screenW - left - right, want = screenW * 0.34;
  if (free < want) {
    var back = (want - free) / 2;
    left = Math.max(0, left - back); right = Math.max(0, right - back);
  }
  var safeW = Math.max(80, screenW - left - right);
  var safeH = Math.max(80, screenH - TOOLBAR_TOP - EDGE * 2);
  var r = room || 1.15;
  var zoom = Math.min(safeW / (box.w * r), safeH / (box.h * r));
  zoom = Math.min(maxZoom || 2.5, Math.max(minZoom || 0.02, zoom));
  figma.viewport.zoom = zoom;
  // 안 가려지는 영역의 한가운데에 대상이 오도록 화면을 옆으로 민다.
  var dx = (left - right) / 2, dy = (TOOLBAR_TOP - EDGE) / 2;
  figma.viewport.center = { x: box.x + box.w / 2 - dx / zoom, y: box.y + box.h / 2 - dy / zoom };
  return true;
}
function focusNodes(nodes, room, minZoom, maxZoom) {
  if (!fitIntoSafeArea(unionBox(nodes), room, minZoom, maxZoom)) figma.viewport.scrollAndZoomIntoView(nodes);
}

function planChipPlacement(boxes, chipSizes, devW, devH, ink, sx) {
  var useInk = (ink && ink.rows && ink.rows.length) ? ink : null;
  var inkCell = useInk ? Math.max(1, useInk.cell * sx) : 0;
  function inkCost(px, py, pw, ph) {
    if (!useInk) return 0;
    var c0 = Math.floor(px / inkCell), c1 = Math.ceil((px + pw) / inkCell);
    var r0 = Math.floor(py / inkCell), r1 = Math.ceil((py + ph) / inkCell);
    var total = 0, filled = 0;
    for (var r = r0; r < r1; r++) {
      var row = useInk.rows[r];
      for (var cc = c0; cc < c1; cc++) {
        total++;
        if (row && row.charAt(cc) === "1") filled++;
      }
    }
    return total ? filled / total : 0;
  }
  function overlapArea(a, b) {
    var ow = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
    var oh = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    return ow > 0 && oh > 0 ? ow * oh : 0;
  }
  function rectGap(a, b) {
    var dx = Math.max(0, Math.max(a.x - (b.x + b.w), b.x - (a.x + a.w)));
    var dy = Math.max(0, Math.max(a.y - (b.y + b.h), b.y - (a.y + a.h)));
    return Math.sqrt(dx * dx + dy * dy);
  }
  var GAP = 6, placed = [], out = [];
  boxes.map(function (b, idx) { return { idx: idx, y: b.y, x: b.x }; })
    .sort(function (a, b) { return (a.y - b.y) || (a.x - b.x); })
    .forEach(function (o) {
      var b = boxes[o.idx], cw = chipSizes[o.idx].w, ch = chipSizes[o.idx].h;
      var opts = [], steps = [0, 20, -20, 42, -42, 66, -66, 96, -96];
      steps.forEach(function (d) {
        opts.push({ x: b.x + b.w + GAP, y: b.y + d });            // 오른쪽
        opts.push({ x: b.x - GAP - cw, y: b.y + d });             // 왼쪽
        opts.push({ x: b.x + d, y: b.y - GAP - ch });             // 위
        opts.push({ x: b.x + d, y: b.y + b.h + GAP });            // 아래
        opts.push({ x: b.x + b.w - cw - d, y: b.y - GAP - ch });  // 위(오른쪽 맞춤)
        opts.push({ x: b.x + b.w - cw - d, y: b.y + b.h + GAP }); // 아래(오른쪽 맞춤)
      });
      var tries = opts.map(function (p) {
        return {
          x: Math.min(Math.max(0, p.x), Math.max(0, devW - cw)),
          y: Math.min(Math.max(0, p.y), Math.max(0, devH - ch)), out: false
        };
      });
      // 마지막 수단: 화면 바로 옆(내용은 안 가리지만 눈이 조금 멀어진다)
      tries.push({ x: devW + GAP, y: Math.max(0, b.y), out: true });
      tries.push({ x: -GAP - cw, y: Math.max(0, b.y), out: true });

      var best = null;
      tries.forEach(function (p) {
        var chip = { x: p.x, y: p.y, w: cw, h: ch }, area = cw * ch;
        var cost = inkCost(p.x, p.y, cw, ch) * 100 + (p.out ? 46 : 0);
        for (var k = 0; k < placed.length; k++) cost += overlapArea(chip, placed[k]) / area * 400;
        for (var m = 0; m < boxes.length; m++) cost += overlapArea(chip, boxes[m]) / area * 70;
        cost += rectGap(chip, b) / 26;
        if (!best || cost < best.cost) best = { x: p.x, y: p.y, w: cw, h: ch, cost: cost };
      });
      out[o.idx] = best;
      placed.push({ x: best.x, y: best.y, w: best.w, h: best.h });
    });
  return out;
}

async function buildCanvasResult(msg) {
  var root = await figma.getNodeByIdAsync(msg.designId);
  if (!root || !root.absoluteBoundingBox) throw new Error("연결된 디자인 프레임을 찾지 못했어요.");
  await removeGenerated(msg.pairId, msg.designId);
  var font = await ensureFont();
  var rb = root.absoluteBoundingBox;
  var image = figma.createImage(new Uint8Array(msg.captureBytes));
  var imageSize = await image.getSizeAsync();
  var devW = Math.max(240, root.width);
  var devH = devW * imageSize.height / imageSize.width;

  var spot = findFreeSpot(rb, devW, devH);
  var board = figma.createFrame();
  board.name = "개발화면 검수 · " + (msg.designName || root.name);
  board.x = spot.x; board.y = spot.y;
  board.resize(devW, devH);
  board.fills = [{ type: "IMAGE", imageHash: image.hash, scaleMode: "FILL" }];
  board.clipsContent = false;
  board.setPluginData(RESULT_MARK, msg.pairId);
  board.setPluginData("designId", msg.designId);
  figma.currentPage.appendChild(board);

  var sx = devW / imageSize.width, sy = devH / imageSize.height;
  var excludedTop = Math.max(0, Number(msg.excludedTop) || 0) * sy;
  var excludedBottom = Math.max(0, Number(msg.excludedBottom) || 0) * sy;
  if (excludedTop > 0 || excludedBottom > 0) {
    // 비교에서 뺀 위·아래 띠는 흐리게 덮고, 실제 검수 범위는 점선으로 표시한다.
    if (excludedTop > 0) {
      var dim = figma.createRectangle(); board.appendChild(dim); dim.name = "비교 제외 띠(브라우저 틀)";
      dim.x = 0; dim.y = 0; dim.resize(devW, Math.max(1, excludedTop));
      dim.fills = [{ type: "SOLID", color: paint("6B7280"), opacity: 0.55 }]; dim.strokes = [];
      var dimText = makeText(font, "비교 제외 · 브라우저 틀(검수 범위)", 11, { r: 1, g: 1, b: 1 }); board.appendChild(dimText);
      dimText.x = 8; dimText.y = Math.max(2, excludedTop / 2 - dimText.height / 2);
    }
    if (excludedBottom > 0) {
      var dimB = figma.createRectangle(); board.appendChild(dimB); dimB.name = "비교 제외 띠(하단 내비게이션)";
      dimB.x = 0; dimB.y = Math.max(0, devH - excludedBottom); dimB.resize(devW, Math.max(1, excludedBottom));
      dimB.fills = [{ type: "SOLID", color: paint("6B7280"), opacity: 0.55 }]; dimB.strokes = [];
      var dimTextB = makeText(font, "비교 제외 · 하단 내비게이션(검수 범위)", 11, { r: 1, g: 1, b: 1 }); board.appendChild(dimTextB);
      dimTextB.x = 8; dimTextB.y = Math.max(2, devH - excludedBottom / 2 - dimTextB.height / 2);
    }
    var rangeRect = figma.createRectangle(); board.appendChild(rangeRect); rangeRect.name = "검수 범위";
    rangeRect.x = 0; rangeRect.y = excludedTop; rangeRect.resize(devW, Math.max(1, devH - excludedTop - excludedBottom));
    rangeRect.fills = []; rangeRect.strokes = [{ type: "SOLID", color: paint("1D6CEB") }]; rangeRect.strokeWeight = 1.5; rangeRect.dashPattern = [8, 6];
  }
  var nodeMap = {};

  // 번호표 자리(내용·다른 번호표를 피한 위치)를 먼저 계산한다.
  var boxes = [], tagWidths = [], chipSizes = [];
  for (var bi = 0; bi < msg.candidates.length; bi++) {
    var cb = msg.candidates[bi].rawBox;
    boxes.push({
      x: Math.max(0, cb.x * sx), y: Math.max(0, cb.y * sy),
      w: Math.max(8, cb.w * sx), h: Math.max(8, cb.h * sy)
    });
    var tw = 0, th = 0;
    if (msg.candidates[bi].label) {
      var probe = makeText(font, msg.candidates[bi].label, 10, { r: 1, g: 1, b: 1 });
      tw = probe.width + 12; th = probe.height + 6; probe.remove(); // 크기만 재고 버린다
    }
    tagWidths.push({ w: tw, h: th });
    chipSizes.push({ w: 26 + (tw ? 6 + tw : 0), h: Math.max(26, th) });
  }
  var BADGE = 26;
  var chipAt = planChipPlacement(boxes, chipSizes, devW, devH, msg.ink, sx);
  function rectGap(a, b) {
    var dx = Math.max(0, Math.max(a.x - (b.x + b.w), b.x - (a.x + a.w)));
    var dy = Math.max(0, Math.max(a.y - (b.y + b.h), b.y - (a.y + a.h)));
    return Math.sqrt(dx * dx + dy * dy);
  }

  for (var i = 0; i < msg.candidates.length; i++) {
    var c = msg.candidates[i];
    var col = statusColor(c.status);
    var x = boxes[i].x, y = boxes[i].y, w = boxes[i].w, h = boxes[i].h;
    var rect = figma.createRectangle(); board.appendChild(rect); rect.name = "후보 영역 " + c.no;
    rect.x = x; rect.y = y; rect.resize(w, h);
    rect.fills = [{ type: "SOLID", color: col, opacity: c.kind === "spacing" ? 0.16 : 0.08 }];
    rect.strokes = [{ type: "SOLID", color: col }]; rect.strokeWeight = c.kind === "spacing" ? 1 : 2; rect.cornerRadius = 4;
    var spacingNodes = [];
    if (c.kind === "spacing") {
      (c.rawAnchorBoxes || []).forEach(function (ab, ai) {
        var anchor = figma.createRectangle(); board.appendChild(anchor); anchor.name = "간격 기준 컴포넌트 " + (ai + 1);
        anchor.x = Math.max(0, ab.x * sx); anchor.y = Math.max(0, ab.y * sy);
        anchor.resize(Math.max(8, Math.min(devW - anchor.x, ab.w * sx)), Math.max(8, Math.min(devH - anchor.y, ab.h * sy)));
        anchor.fills = []; anchor.strokes = [{ type: "SOLID", color: col, opacity: 0.55 }]; anchor.strokeWeight = 1; anchor.cornerRadius = 4;
        spacingNodes.push(anchor);
      });
      function measureRect(name, mx, my, mw, mh) {
        var mark = figma.createRectangle(); board.appendChild(mark); mark.name = name;
        mark.x = mx; mark.y = my; mark.resize(Math.max(1, mw), Math.max(1, mh));
        mark.fills = [{ type: "SOLID", color: col, opacity: 0.9 }]; mark.strokes = [];
        spacingNodes.push(mark);
      }
      if (c.axis === "vertical") {
        var centerX = x + w / 2;
        measureRect("간격 측정선", centerX - 0.75, y, 1.5, h);
        measureRect("간격 측정 위", centerX - 6, y, 12, 1.5);
        measureRect("간격 측정 아래", centerX - 6, y + h - 1.5, 12, 1.5);
      } else {
        var centerY = y + h / 2;
        measureRect("간격 측정선", x, centerY - 0.75, w, 1.5);
        measureRect("간격 측정 왼쪽", x, centerY - 6, 1.5, 12);
        measureRect("간격 측정 오른쪽", x + w - 1.5, centerY - 6, 1.5, 12);
      }
    }

    // 빈 곳에 놓인 번호표. 영역에서 떨어져 있으면 얇은 ㄱ자 안내선으로 잇는다.
    var chip = chipAt[i], leadNodes = [];
    var leadRect = function (lx, ly, lw, lh) {
      var l = figma.createRectangle(); board.appendChild(l); l.name = "안내선 " + c.no;
      l.x = lx; l.y = ly; l.resize(Math.max(1, lw), Math.max(1, lh));
      l.fills = [{ type: "SOLID", color: col, opacity: 0.55 }]; l.strokes = [];
      leadNodes.push(l);
    };
    if (rectGap(chip, { x: x, y: y, w: w, h: h }) > 10) {
      var ccx = chip.x + chip.w / 2, ccy = chip.y + chip.h / 2, bcy = y + h / 2;
      var joinX = Math.min(Math.max(ccx, x), x + w); // 세로선이 만나는 영역 위의 지점
      leadRect(ccx - 0.75, Math.min(ccy, bcy), 1.5, Math.abs(ccy - bcy));
      leadRect(Math.min(ccx, joinX), bcy - 0.75, Math.abs(joinX - ccx), 1.5);
    }

    var badge = figma.createEllipse(); board.appendChild(badge); badge.resize(BADGE, BADGE);
    badge.x = chip.x; badge.y = chip.y + (chip.h - BADGE) / 2;
    badge.fills = [{ type: "SOLID", color: col }];
    badge.strokes = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }]; badge.strokeWeight = 1.5;
    var num = makeText(font, String(c.no), 13, { r: 1, g: 1, b: 1 }); board.appendChild(num);
    num.resize(BADGE, BADGE); num.textAlignHorizontal = "CENTER"; num.textAlignVertical = "CENTER";
    num.x = badge.x; num.y = badge.y;
    var nodes = [rect].concat(spacingNodes, leadNodes, [badge, num]);

    if (c.label) {
      var tagText = makeText(font, c.label, 10, { r: 1, g: 1, b: 1 });
      var tagBg = figma.createRectangle(); board.appendChild(tagBg); tagBg.name = "분류 " + c.no;
      var tagW = tagWidths[i].w, tagH = tagWidths[i].h;
      tagBg.x = chip.x + BADGE + 6; tagBg.y = chip.y + (chip.h - tagH) / 2;
      tagBg.resize(tagW, tagH);
      tagBg.fills = [{ type: "SOLID", color: col }]; tagBg.cornerRadius = 4;
      tagBg.strokes = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }]; tagBg.strokeWeight = 1;
      board.appendChild(tagText);
      tagText.x = tagBg.x + 6; tagText.y = tagBg.y + 3;
      nodes.push(tagBg, tagText);
    }
    var group = figma.group(nodes, board); group.name = "검수 번호 " + c.no;
    group.opacity = statusOpacity(c.status);
    group.setPluginData(CANDIDATE_MARK, c.id);
    group.setPluginData(CANDIDATE_STATUS_KEY, c.status || "");
    group.setPluginData("designNodeIds", JSON.stringify(c.designNodeIds || []));
    candidateNodeById[c.id] = group.id; nodeMap[c.id] = group.id;
  }
  resultNodeByPair[msg.pairId] = board.id;
  lastProgrammaticSelectionAt = Date.now(); figma.currentPage.selection = [board];
  focusNodes([root, board], 1.1);
  return { boardId: board.id, candidateNodes: nodeMap, imageWidth: imageSize.width, imageHeight: imageSize.height };
}

function allCandidateGroups() {
  return figma.currentPage.findAll(function (n) { return !!(n.getPluginData && n.getPluginData(CANDIDATE_MARK)); });
}
async function focusCandidate(candidateId) {
  var node = candidateNodeById[candidateId] ? await figma.getNodeByIdAsync(candidateNodeById[candidateId]) : null;
  if (!node) {
    var hits = allCandidateGroups().filter(function (n) { return n.getPluginData(CANDIDATE_MARK) === candidateId; });
    node = hits[0] || null;
  }
  if (!node) throw new Error("캔버스의 번호를 찾지 못했어요. 결과를 다시 만들어 주세요.");
  var groups = allCandidateGroups();
  groups.forEach(function (g) { g.opacity = g.id === node.id ? 1 : 0.16; });
  var ids = [];
  try { ids = JSON.parse(node.getPluginData("designNodeIds") || "[]"); } catch (e) {}
  var selection = [node];
  for (var i = 0; i < ids.length; i++) {
    var live = await figma.getNodeByIdAsync(ids[i]);
    if (live && live.type !== "DOCUMENT" && live.type !== "PAGE") selection.push(live);
  }
  lastProgrammaticSelectionAt = Date.now(); figma.currentPage.selection = selection;
  figma.ui.postMessage({ type: "design-values-live", candidateId: candidateId, items: await readLiveDesignValues(ids) });
  // 번호 영역이 화면 중앙에 오도록 맞춘다. (멀리 있는 디자인 레이어까지 한 화면에 넣지 않는다.)
  var bb = node.absoluteBoundingBox;
  if (bb) {
    // 번호 둘레까지 보되 너무 멀어지지 않게 2.2배 여유. 좌·우 패널에 가리지 않는 가운데로 온다.
    fitIntoSafeArea({ x: bb.x, y: bb.y, w: bb.width, h: bb.height }, 2.2, 0.5, 3);
  } else {
    focusNodes([node], 1.2);
  }
}
async function readLiveDesignValues(ids) {
  // 번호가 가리키는 디자인 레이어를 '지금' Figma에서 다시 읽는다. 검수 시작 때 찍어 둔 값과 달라졌으면 패널이 그 사실을 보여 준다.
  // 값을 읽기만 한다 — 오류를 확정하거나 개발 값을 추측하지 않는다.
  var out = [];
  for (var i = 0; i < (ids || []).length; i++) {
    var id = ids[i], node = null;
    try { node = await figma.getNodeByIdAsync(id); } catch (e) { node = null; }
    if (!node || node.removed || node.type === "DOCUMENT" || node.type === "PAGE" || !node.absoluteBoundingBox) { out.push({ id: id, gone: true }); continue; }
    var bb = node.absoluteBoundingBox, el = readDesignElement(node, { x: bb.x, y: bb.y }, 0, null, null, []);
    if (!el) { out.push({ id: id, name: node.name || node.type, kind: "shape", text: "", values: {} }); continue; }
    out.push({ id: id, name: el.name, kind: el.kind, text: el.text || "", values: el.values });
  }
  return out;
}
function clearCandidateFocus() {
  allCandidateGroups().forEach(function (g) { g.opacity = 1; });
}
async function updateCandidateStatus(candidateId, status) {
  var node = candidateNodeById[candidateId] ? await figma.getNodeByIdAsync(candidateNodeById[candidateId]) : null;
  if (!node) return;
  node.opacity = statusOpacity(status);
  node.setPluginData(CANDIDATE_STATUS_KEY, status || "");
  var col = statusColor(status);
  if ("children" in node) {
    node.children.forEach(function (n) {
      if (n.type === "RECTANGLE" && n.name.indexOf("후보 영역") === 0) {
        n.strokes = [{ type: "SOLID", color: col }]; n.fills = [{ type: "SOLID", color: col, opacity: 0.08 }];
      }
      if (n.type === "RECTANGLE" && n.name.indexOf("간격 기준 컴포넌트") === 0) {
        n.strokes = [{ type: "SOLID", color: col, opacity: 0.55 }]; n.fills = [];
      }
      if (n.type === "RECTANGLE" && n.name.indexOf("간격 측정") === 0) n.fills = [{ type: "SOLID", color: col, opacity: 0.9 }];
      if (n.type === "ELLIPSE") n.fills = [{ type: "SOLID", color: col }];
    });
  }
}

async function removeCompareCard(pairId) {
  var id = compareNodeByPair[pairId];
  if (id) { var old = await figma.getNodeByIdAsync(id); if (old) old.remove(); delete compareNodeByPair[pairId]; }
  figma.currentPage.findAll(function (n) {
    return !!(n.getPluginData && n.getPluginData(COMPARE_MARK)) && (!pairId || n.getPluginData(COMPARE_MARK) === pairId);
  }).forEach(function (n) { n.remove(); });
}

// 나란히 보기 카드: 디자인 조각과 개발 조각을 캔버스에 크게 나란히 놓는다. 플러그인 패널은 좁게 둔다.
async function buildCompareCard(msg) {
  var boardId = resultNodeByPair[msg.pairId];
  var board = boardId ? await figma.getNodeByIdAsync(boardId) : null;
  if (!board || !board.absoluteBoundingBox) return;
  await removeCompareCard(msg.pairId);
  var font = await ensureFont();
  var pad = 28, gap = 20, paneW = 520;
  var aspect = Math.max(0.08, Math.min(3, Number(msg.aspect) || 0.5));
  var paneH = Math.max(120, Math.min(760, Math.round(paneW * aspect)));
  var cardW = pad * 2 + paneW * 2 + gap;
  var card = figma.createFrame();
  card.name = "나란히 보기 · 번호 " + msg.no;
  card.resize(cardW, 400);
  card.fills = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
  // 캔버스 배경과 확실히 구분되게: 진한 테두리 + 그림자
  card.strokes = [{ type: "SOLID", color: paint("8A94A6") }]; card.strokeWeight = 2; card.cornerRadius = 12;
  card.effects = [
    { type: "DROP_SHADOW", color: { r: 0.09, g: 0.12, b: 0.18, a: 0.22 }, offset: { x: 0, y: 10 }, radius: 28, spread: 0, visible: true, blendMode: "NORMAL" },
    { type: "DROP_SHADOW", color: { r: 0.09, g: 0.12, b: 0.18, a: 0.14 }, offset: { x: 0, y: 2 }, radius: 6, spread: 0, visible: true, blendMode: "NORMAL" }
  ];
  card.clipsContent = false;
  card.setPluginData(COMPARE_MARK, msg.pairId);
  figma.currentPage.appendChild(card);

  var y = pad;
  var title = makeText(font, "번호 " + msg.no + " · " + (msg.label || "차이 후보"), 20, paint("222222"));
  card.appendChild(title); title.x = pad; title.y = y; title.resize(cardW - pad * 2, title.height); y += title.height + 18;

  var labels = ["디자인 원본", "개발 캡처"], bytes = [msg.designBytes, msg.devBytes];
  for (var i = 0; i < 2; i++) {
    var lx = pad + i * (paneW + gap);
    var lab = makeText(font, labels[i], 13, paint("888888"));
    card.appendChild(lab); lab.x = lx; lab.y = y;
    var img = figma.createImage(new Uint8Array(bytes[i]));
    var rect = figma.createRectangle(); card.appendChild(rect); rect.name = labels[i];
    rect.x = lx; rect.y = y + lab.height + 6; rect.resize(paneW, paneH);
    rect.fills = [{ type: "IMAGE", imageHash: img.hash, scaleMode: "FIT" }];
    rect.strokes = [{ type: "SOLID", color: paint("EEEEEE") }]; rect.strokeWeight = 1; rect.cornerRadius = 6;
  }
  y += 19 + 6 + paneH + 18;

  var notes = [];
  if (msg.detail) notes.push({ text: msg.detail, size: 14, color: "353535" });
  if (msg.designValues) notes.push({ text: "디자인 원본값: " + msg.designValues, size: 12, color: "888888" });
  if (msg.designNote) notes.push({ text: msg.designNote, size: 12, color: "B45309" }); // 검수 뒤 디자인이 바뀐 경우
  for (var n = 0; n < notes.length; n++) {
    var t = makeText(font, notes[n].text, notes[n].size, paint(notes[n].color));
    card.appendChild(t); t.x = pad; t.y = y;
    t.textAutoResize = "HEIGHT"; t.resize(cardW - pad * 2, t.height);
    y += t.height + 8;
  }
  card.resize(cardW, y + pad - 8);

  // 검수 화면 위의 그 번호 바로 옆에 둔다(연결선으로 어느 번호의 카드인지 표시).
  var bb = board.absoluteBoundingBox;
  var candId = candidateNodeById[msg.candidateId];
  var cand = candId ? await figma.getNodeByIdAsync(candId) : null;
  var cbb = cand && cand.absoluteBoundingBox;
  var margin = 32;
  if (cbb) {
    // 번호 바로 아래에 둔다. 번호가 화면 아래쪽에 가까우면 위에 둔다. (좌우가 아니라 위·아래)
    var topSide = (cbb.y + cbb.height + margin + card.height) > (bb.y + bb.height + card.height * 0.5);
    card.y = topSide ? (cbb.y - margin - card.height) : (cbb.y + cbb.height + margin);
    card.x = cbb.x + cbb.width / 2 - cardW / 2;
    // 어느 번호의 카드인지 선으로 잇는다.
    var pinEdgeY = topSide ? (cbb.y - card.y) : (cbb.y + cbb.height - card.y), cardEdgeY = topSide ? card.height : 0;
    var linkX = (cbb.x + cbb.width / 2) - card.x - 1.5;
    var link = figma.createRectangle(); card.appendChild(link); link.name = "연결선";
    link.x = linkX; link.y = Math.min(pinEdgeY, cardEdgeY);
    link.resize(3, Math.max(1, Math.abs(pinEdgeY - cardEdgeY)));
    link.fills = [{ type: "SOLID", color: paint("1D6CEB"), opacity: 0.55 }]; link.strokes = [];
    var dot = figma.createEllipse(); card.appendChild(dot); dot.name = "연결점";
    dot.x = linkX - 3.5; dot.y = pinEdgeY - 5; dot.resize(10, 10);
    dot.fills = [{ type: "SOLID", color: paint("1D6CEB") }];
  } else { card.x = bb.x + bb.width / 2 - cardW / 2; card.y = bb.y + bb.height + margin; }
  compareNodeByPair[msg.pairId] = card.id;

  // 카드를 크게 본다(번호는 카드 바로 위·아래에 붙어 있어 연결선으로 찾을 수 있다).
  focusNodes([card], 1.04);
  return card;
}

// 검수 레포트: 검수 화면 옆에 번호와 검수 내용을 적은 메모장을 만든다.
async function buildReport(msg) {
  var boardId = resultNodeByPair[msg.pairId];
  var board = boardId ? await figma.getNodeByIdAsync(boardId) : null;
  if (!board || !board.absoluteBoundingBox) throw new Error("검수 결과 프레임을 찾지 못했어요. 자동 비교를 다시 실행해 주세요.");
  var oldId = reportNodeByPair[msg.pairId];
  if (oldId) { var oldNode = await figma.getNodeByIdAsync(oldId); if (oldNode) oldNode.remove(); delete reportNodeByPair[msg.pairId]; }
  figma.currentPage.findAll(function (n) { return !!(n.getPluginData && n.getPluginData(REPORT_MARK) === msg.pairId); }).forEach(function (n) { n.remove(); });

  var font = await ensureFont();
  var pad = 32, cardW = 720, textW = cardW - pad * 2, bodyX = pad + 36;
  var memo = figma.createFrame();
  memo.name = "검수 레포트 · " + (msg.screenName || "검수 화면");
  memo.resize(cardW, 600);
  memo.fills = [{ type: "SOLID", color: paint("FFFDF5") }]; // 메모장 느낌의 미색
  memo.strokes = [{ type: "SOLID", color: paint("E6DFC8") }]; memo.strokeWeight = 1; memo.cornerRadius = 10;
  memo.setPluginData(REPORT_MARK, msg.pairId);
  figma.currentPage.appendChild(memo);

  function line(text, size, color, x, y, w) {
    var t = makeText(font, text, size, paint(color));
    memo.appendChild(t); t.x = x; t.y = y;
    t.textAutoResize = "HEIGHT"; t.resize(w, t.height);
    return t;
  }
  var y = pad;
  var title = line("검수 레포트 · " + (msg.screenName || "검수 화면"), 22, "222222", pad, y, textW); y += title.height + 10;
  var meta = line((msg.date || "") + "   " + (msg.summary || ""), 12, "888888", pad, y, textW); y += meta.height + 6;
  var rangeLine = line(msg.rangeText || "", 12, "888888", pad, y, textW); y += rangeLine.height + 18;
  var rule = figma.createRectangle(); memo.appendChild(rule); rule.x = pad; rule.y = y; rule.resize(textW, 1);
  rule.fills = [{ type: "SOLID", color: paint("E6DFC8") }]; rule.strokes = []; y += 18;

  var rows = msg.rows || [];
  if (!rows.length) { line("자동 비교에서 눈에 띄는 차이 후보를 찾지 못했어요.", 14, "353535", pad, y, textW); y += 30; }
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i], col = statusColor(row.status);
    var badge = figma.createEllipse(); memo.appendChild(badge); badge.name = "번호 " + row.no;
    badge.x = pad; badge.y = y; badge.resize(26, 26);
    badge.fills = [{ type: "SOLID", color: col }];
    var num = makeText(font, String(row.no), 13, { r: 1, g: 1, b: 1 }); memo.appendChild(num);
    num.resize(26, 26); num.textAlignHorizontal = "CENTER"; num.textAlignVertical = "CENTER"; num.x = pad; num.y = y;
    var stateText = makeText(font, row.statusText || "", 11, col); memo.appendChild(stateText);
    stateText.x = cardW - pad - 90; stateText.y = y + 4; stateText.resize(90, stateText.height); stateText.textAlignHorizontal = "RIGHT";
    var rowY = y;
    var reason = line(row.reason || "", 14, "222222", bodyX, rowY + 3, cardW - bodyX - pad - 96); rowY += reason.height + 9;
    if (row.detail) { var det = line(row.detail, 12, "555555", bodyX, rowY, cardW - bodyX - pad); rowY += det.height + 6; }
    if (row.designValues) { var dv = line("디자인 원본값: " + row.designValues, 11, "999999", bodyX, rowY, cardW - bodyX - pad); rowY += dv.height + 6; }
    y = Math.max(rowY, y + 26) + 12;
    if (i < rows.length - 1) {
      var sep = figma.createRectangle(); memo.appendChild(sep); sep.x = bodyX; sep.y = y; sep.resize(cardW - bodyX - pad, 1);
      sep.fills = [{ type: "SOLID", color: paint("F0EADA") }]; sep.strokes = []; y += 13;
    }
  }
  var foot = line("자동 비교 결과는 후보이며, 오류 확정은 사람이 고른 번호에만 적용됩니다.", 11, "AAAAAA", pad, y + 6, textW);
  memo.resize(cardW, foot.y + foot.height + pad);

  var bb = board.absoluteBoundingBox;
  // 번호·검수내용이 놓인 오른쪽 여백까지 피해서 레포트를 둔다.
  var boardRight = bb.x + bb.width;
  (board.children || []).forEach(function (ch) { var cb = ch.absoluteBoundingBox; if (cb) boardRight = Math.max(boardRight, cb.x + cb.width); });
  memo.x = boardRight + 120; memo.y = bb.y;
  reportNodeByPair[msg.pairId] = memo.id;
  lastProgrammaticSelectionAt = Date.now(); figma.currentPage.selection = [memo];
  focusNodes([memo], 1.1);
  figma.notify("검수 레포트를 검수 화면 옆에 만들었어요.");
  return memo;
}

async function clearCandidates(pairId) {
  // 겹쳐보기 자리를 옮기면 이전 번호 표시를 지운다(겹쳐놓은 디자인·개발 캡처는 그대로 둔다).
  var boardId = resultNodeByPair[pairId];
  var board = boardId ? await figma.getNodeByIdAsync(boardId) : null;
  if (!board || !board.findAll) return;
  var marks = board.findAll(function (n) { return !!(n.getPluginData && n.getPluginData(CANDIDATE_MARK)); });
  marks.forEach(function (n) {
    var cid = n.getPluginData(CANDIDATE_MARK);
    if (candidateNodeById[cid]) delete candidateNodeById[cid];
    n.remove();
  });
  if (marks.length) figma.notify("겹쳐보기 자리를 옮겨 이전 번호를 지웠어요. 패널에서 ‘재검수 진행’을 눌러 주세요.");
}

function reportOverlayPos(pairId, node) {
  if (node && typeof node.x === "number") figma.ui.postMessage({ type: "overlay-moved", pairId: pairId, x: node.x, y: node.y });
}
var overlayMoveTimer = null;
function watchOverlayMoves() {
  // 겹쳐놓은 디자인을 캔버스에서 끌면 그 자리를 그대로 저장한다(따로 누를 것 없음).
  if (!figma.currentPage || typeof figma.currentPage.on !== "function") return;
  try {
    figma.currentPage.on("nodechange", function (ev) {
      var hit = null;
      (ev.nodeChanges || []).forEach(function (ch) {
        if (!ch || ch.type !== "PROPERTY_CHANGE") return;
        var props = ch.properties || [];
        if (props.indexOf("x") < 0 && props.indexOf("y") < 0 && props.indexOf("relativeTransform") < 0) return;
        var id = ch.node && ch.node.id;
        Object.keys(overlayNodeByPair).forEach(function (pid) { if (overlayNodeByPair[pid] === id) hit = { pid: pid, node: ch.node }; });
      });
      if (!hit) return;
      if (overlayMoveTimer) clearTimeout(overlayMoveTimer);
      overlayMoveTimer = setTimeout(function () { // 끄는 동안 여러 번 오므로 마지막 자리만 저장
        overlayMoveTimer = null;
        if (!hit.node.removed) reportOverlayPos(hit.pid, hit.node);
      }, 350);
    });
  } catch (e) {}
}
watchOverlayMoves();

async function toggleOverlay(msg) {
  var existingId = overlayNodeByPair[msg.pairId];
  var existing = existingId ? await figma.getNodeByIdAsync(existingId) : null;
  if (existing) {
    reportOverlayPos(msg.pairId, existing); // 끄기 전에 옮겨 둔 자리를 저장한다
    existing.remove(); delete overlayNodeByPair[msg.pairId];
    return { visible: false };
  }
  // 검수 결과 프레임(개발 캡처) 위에 디자인 이미지를 반투명으로 얹는다. 디자인 프레임으로 이동하지 않는다.
  var boardId = resultNodeByPair[msg.pairId];
  var board = boardId ? await figma.getNodeByIdAsync(boardId) : null;
  if (!board) throw new Error("검수 결과 프레임을 찾지 못했어요. 자동 비교를 다시 실행해 주세요.");
  var image = figma.createImage(new Uint8Array(msg.designBytes));
  var over = figma.createRectangle(); over.name = "겹쳐보기(디자인)";
  board.insertChild(0, over); // 번호·영역 표시 아래에 깔리게 맨 밑에 넣는다.
  over.x = msg.box.x; over.y = msg.box.y;
  over.resize(Math.max(1, msg.box.w), Math.max(1, msg.box.h));
  over.fills = [{ type: "IMAGE", imageHash: image.hash, scaleMode: "FILL" }];
  over.opacity = 0.5; over.setPluginData(OVERLAY_MARK, msg.pairId);
  overlayNodeByPair[msg.pairId] = over.id;
  // 바로 끌어서 자리를 맞출 수 있게 겹쳐놓은 디자인을 선택해 둔다. 옮긴 자리는 자동으로 저장된다.
  lastProgrammaticSelectionAt = Date.now(); figma.currentPage.selection = [over];
  focusNodes([board], 1.1);
  figma.notify("겹쳐놓은 디자인을 끌어서 자리를 맞출 수 있어요. 옮긴 자리는 저장됩니다.");
  return { visible: true };
}

figma.ui.onmessage = async function (msg) {
  try {
    if (msg.type === "request-selection-status") {
      postSelectionStatus();
    } else if (msg.type === "read-selected-designs") {
      var designs = await exportSelectedDesigns();
      figma.ui.postMessage({ type: "designs-read", designs: designs });
    } else if (msg.type === "read-selected-assets") {
      var selection = figma.currentPage.selection;
      var selectedDesigns = selection.filter(function (node) { return selectableFrame(node) && !selectableCapture(node); });
      var selectedCaptures = selection.filter(selectableCapture);
      if (!selectedDesigns.length && !selectedCaptures.length) {
        throw new Error("디자인 프레임이나 이미지가 들어간 개발화면을 선택해 주세요.");
      }
      var assetDesigns = [];
      if (selectedDesigns.length) {
        for (var i = 0; i < selectedDesigns.length; i++) {
          var root = selectedDesigns[i];
          var bb = root.absoluteBoundingBox;
          var maxSide = Math.max(bb.width, bb.height);
          var scale = Math.min(1, 4096 / Math.max(1, maxSide)); // 디자인도 원본 해상도로 읽어 작은 아이콘·10px 글자까지 비교한다.
          var bytes = await root.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: scale } });
          assetDesigns.push({
            id: root.id, name: root.name || ("디자인 " + (i + 1)), type: root.type,
            x: round1(bb.x), y: round1(bb.y),
            width: round1(bb.width), height: round1(bb.height),
            bytes: Array.from(bytes), elements: collectDesign(root), policy: readDesignPolicy(root)
          });
        }
      }
      var assetCaptures = await exportSelectedCaptures(selectedCaptures);
      figma.ui.postMessage({ type: "assets-read", designs: assetDesigns, captures: assetCaptures });
    } else if (msg.type === "read-selected-captures") {
      var captures = await exportSelectedCaptures();
      if (!captures.length) throw new Error("이미지가 채워진 개발화면 레이어를 하나 이상 선택해 주세요.");
      figma.ui.postMessage({ type: "captures-read", captures: captures });
    } else if (msg.type === "render-results") {
      var result = await buildCanvasResult(msg);
      figma.ui.postMessage({ type: "results-rendered", pairId: msg.pairId, result: result });
    } else if (msg.type === "focus-candidate") {
      await focusCandidate(msg.candidateId);
    } else if (msg.type === "read-design-values") {
      figma.ui.postMessage({ type: "design-values-live", candidateId: msg.candidateId, items: await readLiveDesignValues(msg.ids || []) });
    } else if (msg.type === "clear-focus") {
      clearCandidateFocus();
    } else if (msg.type === "clear-candidates") {
      await clearCandidates(msg.pairId);
    } else if (msg.type === "candidate-status") {
      await updateCandidateStatus(msg.candidateId, msg.status);
    } else if (msg.type === "toggle-overlay") {
      var overlay = await toggleOverlay(msg);
      figma.ui.postMessage({ type: "overlay-changed", pairId: msg.pairId, visible: overlay.visible });
    } else if (msg.type === "build-report") {
      await buildReport(msg);
    } else if (msg.type === "set-capture-overlay-fix") {
      var fixNode = msg.nodeId ? await figma.getNodeByIdAsync(msg.nodeId) : null;
      if (fixNode && fixNode.setPluginData) {
        var fbb = fixNode.absoluteBoundingBox, fsc = fbb ? Math.min(1, 4096 / Math.max(1, Math.max(fbb.width, fbb.height))) : 1;
        if (!msg.fix) fixNode.setPluginData(OVERLAY_FIX_KEY, "");
        else fixNode.setPluginData(OVERLAY_FIX_KEY, JSON.stringify({ dx: Math.round(msg.fix.dx / fsc), dy: Math.round(msg.fix.dy / fsc) })); // 노드 좌표계로 저장
      }
    } else if (msg.type === "render-compare") {
      await buildCompareCard(msg);
    } else if (msg.type === "clear-compare") {
      await removeCompareCard(msg.pairId);
    } else if (msg.type === "set-capture-trim") {
      var capNode = msg.nodeId ? await figma.getNodeByIdAsync(msg.nodeId) : null;
      if (capNode && capNode.setPluginData) {
        var bbT = capNode.absoluteBoundingBox, sc = bbT ? Math.min(1, 4096 / Math.max(1, Math.max(bbT.width, bbT.height))) : 1;
        capNode.setPluginData(TRIM_KEY, String(Math.max(0, Math.round((Number(msg.topTrim) || 0) / sc)))); // 노드 좌표계(export 배율 되돌림)로 저장
        capNode.setPluginData(BOTTOM_TRIM_KEY, String(Math.max(0, Math.round((Number(msg.bottomTrim) || 0) / sc))));
      }
    } else if (msg.type === "set-design-policy") {
      // 화면 종류(공통/일반)와 사람이 정한 글자 가변 여부를 디자인 프레임에 작은 설정값으로 저장한다.
      var policyNode = msg.designId ? await figma.getNodeByIdAsync(msg.designId) : null;
      if (policyNode && policyNode.setPluginData) policyNode.setPluginData(POLICY_KEY, msg.policy ? JSON.stringify(msg.policy) : "");
    } else if (msg.type === "notify") {
      figma.notify(msg.message);
    }
  } catch (err) {
    figma.ui.postMessage({ type: "plugin-error", message: String(err && err.message ? err.message : err) });
  }
};
