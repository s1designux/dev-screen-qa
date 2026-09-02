// 개발화면 검수기 — Figma 문서 읽기와 캔버스 결과 표시.
// 이미지 비교는 ui.html의 로컬 Canvas 엔진이 맡고, 이 파일은 살아 있는 디자인값과
// 개발 캡처 위 번호·영역·기준값 쪽지를 만든다. 외부 통신과 자동 오류 확정은 없다.

figma.showUI(__html__, { width: 390, height: 720, themeColors: true });

var RESULT_MARK = "imageQaResult";
var CANDIDATE_MARK = "imageQaCandidate";
var OVERLAY_MARK = "imageQaOverlay";
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

function readDesignElement(node, rootBox, depth, parentId, parentType) {
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
  function walk(n, depth, parentId, parentType) {
    if (n.id !== root.id && n.visible !== false && n.absoluteBoundingBox) {
      var el = readDesignElement(n, rb, depth, parentId, parentType);
      if (el) {
        var b = el.box;
        if (b.x < rb.width && b.y < rb.height && b.x + b.w > 0 && b.y + b.h > 0) items.push(el);
      }
    }
    if ("children" in n) for (var i = 0; i < n.children.length; i++) walk(n.children[i], depth + 1, n.id, n.type);
  }
  walk(root, 0, null, null);
  return items;
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

function postSelectionStatus() {
  var status = selectionGeometry();
  figma.ui.postMessage({ type: "selection-status", designs: status.designs, captures: status.captures });
}

if (typeof figma.on === "function") figma.on("selectionchange", postSelectionStatus);

async function exportCaptureNode(node, index) {
  var bb = node.absoluteBoundingBox;
  var maxSide = Math.max(bb.width, bb.height);
  var scale = Math.min(1, 4096 / Math.max(1, maxSide));
  var bytes = await node.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: scale } });
  return {
    id: "figma_" + node.id,
    nodeId: node.id,
    name: node.name || ("Figma 이미지 " + (index + 1)),
    source: "figma",
    x: round1(bb.x), y: round1(bb.y),
    width: round1(bb.width), height: round1(bb.height),
    bytes: Array.from(bytes)
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
      bytes: Array.from(bytes), elements: collectDesign(root)
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
  if (status === "hold") return paint("CA8A04");
  return paint("EA580C");
}
function statusOpacity(status) { return status === "excluded" ? 0.25 : 1; }
function makeText(font, value, size, color) {
  var t = figma.createText();
  t.fontName = font; t.characters = value; t.fontSize = size;
  t.fills = [{ type: "SOLID", color: color }];
  return t;
}
async function removeGenerated(pairId, designId) {
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
  var nodeMap = {};
  for (var i = 0; i < msg.candidates.length; i++) {
    var c = msg.candidates[i];
    var col = statusColor(c.status);
    var x = Math.max(0, c.rawBox.x * sx), y = Math.max(0, c.rawBox.y * sy);
    var w = Math.max(8, c.rawBox.w * sx), h = Math.max(8, c.rawBox.h * sy);
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
    var badge = figma.createEllipse(); board.appendChild(badge); badge.resize(26, 26);
    badge.x = Math.min(Math.max(-8, x - 10), devW - 18); badge.y = Math.min(Math.max(-8, y - 10), devH - 18);
    badge.fills = [{ type: "SOLID", color: col }];
    var num = makeText(font, String(c.no), 13, { r: 1, g: 1, b: 1 }); board.appendChild(num);
    num.resize(26, 26); num.textAlignHorizontal = "CENTER"; num.textAlignVertical = "CENTER";
    num.x = badge.x; num.y = badge.y;
    var nodes = [rect].concat(spacingNodes,[badge, num]);

    if (c.label) {
      var tagText = makeText(font, c.label, 10, { r: 1, g: 1, b: 1 });
      var tagBg = figma.createRectangle(); board.appendChild(tagBg); tagBg.name = "분류 " + c.no;
      var tagW = tagText.width + 12, tagH = tagText.height + 6;
      tagBg.x = Math.min(badge.x + 30, devW - tagW); tagBg.y = Math.min(badge.y + 3, devH - tagH);
      tagBg.resize(tagW, tagH);
      tagBg.fills = [{ type: "SOLID", color: col }]; tagBg.cornerRadius = 4;
      board.appendChild(tagText);
      tagText.x = tagBg.x + 6; tagText.y = tagBg.y + 3;
      nodes.push(tagBg, tagText);
    }
    var group = figma.group(nodes, board); group.name = "검수 번호 " + c.no;
    group.opacity = statusOpacity(c.status);
    group.setPluginData(CANDIDATE_MARK, c.id);
    group.setPluginData("designNodeIds", JSON.stringify(c.designNodeIds || []));
    candidateNodeById[c.id] = group.id; nodeMap[c.id] = group.id;
  }
  resultNodeByPair[msg.pairId] = board.id;
  figma.currentPage.selection = [board];
  figma.viewport.scrollAndZoomIntoView([root, board]);
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
  figma.currentPage.selection = selection;
  // 번호 영역이 화면 중앙에 오도록 맞춘다. (멀리 있는 디자인 레이어까지 한 화면에 넣지 않는다.)
  var bb = node.absoluteBoundingBox;
  if (bb) {
    var vb = figma.viewport.bounds, z = figma.viewport.zoom, sw = vb.width * z, sh = vb.height * z;
    figma.viewport.zoom = Math.min(2.5, Math.max(0.35, Math.min(sw / (bb.width * 3), sh / (bb.height * 3))));
    figma.viewport.center = { x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 };
  } else {
    figma.viewport.scrollAndZoomIntoView([node]);
  }
}
function clearCandidateFocus() {
  allCandidateGroups().forEach(function (g) { g.opacity = 1; });
}
async function updateCandidateStatus(candidateId, status) {
  var node = candidateNodeById[candidateId] ? await figma.getNodeByIdAsync(candidateNodeById[candidateId]) : null;
  if (!node) return;
  node.opacity = statusOpacity(status);
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

async function toggleOverlay(msg) {
  var existingId = overlayNodeByPair[msg.pairId];
  var existing = existingId ? await figma.getNodeByIdAsync(existingId) : null;
  if (existing) { existing.remove(); delete overlayNodeByPair[msg.pairId]; return { visible: false }; }
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
  figma.currentPage.selection = [board]; figma.viewport.scrollAndZoomIntoView([board]);
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
            bytes: Array.from(bytes), elements: collectDesign(root)
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
    } else if (msg.type === "clear-focus") {
      clearCandidateFocus();
    } else if (msg.type === "candidate-status") {
      await updateCandidateStatus(msg.candidateId, msg.status);
    } else if (msg.type === "toggle-overlay") {
      var overlay = await toggleOverlay(msg);
      figma.ui.postMessage({ type: "overlay-changed", pairId: msg.pairId, visible: overlay.visible });
    } else if (msg.type === "notify") {
      figma.notify(msg.message);
    }
  } catch (err) {
    figma.ui.postMessage({ type: "plugin-error", message: String(err && err.message ? err.message : err) });
  }
};
