// ============================================================
//  개발화면 검수 플러그인 - 메인 스레드 (Figma API 담당)
//  역할: 프로젝트 데이터 저장, 화면마다 캔버스 위에 "보드"(디자인/개발화면
//        자리)를 만들고 채워넣기, 버전별 이미지 보관, 화면 이동/동기화
// ============================================================

figma.showUI(__html__, { width: 420, height: 640, themeColors: true });

var PROJECT_KEY = "qa_project_v1";
var BOARD_MARK = "qaBoard";      // 보드 프레임 표시용 pluginData 키
var SCREEN_MARK = "qaScreenId";  // 보드에 붙는 화면 id

var SLOT_W = 420, SLOT_H = 300;   // 디자인/개발화면 자리 기본 크기 (웹 화면 우선, 레터박스로 비율 보존)
var GAP_X = 40, GAP_Y = 90, TITLE_H = 30, BOARD_PAD = 30;

var LINKABLE = { FRAME: 1, COMPONENT: 1, COMPONENT_SET: 1, INSTANCE: 1, GROUP: 1, SECTION: 1 };

// ---- 저장/불러오기 ----
function loadProject() {
  var raw = figma.root.getPluginData(PROJECT_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (e) { return null; }
}
function saveProject(project) { figma.root.setPluginData(PROJECT_KEY, JSON.stringify(project)); }

// ---- 폰트 (한글이 보이도록 후보를 순서대로 시도) ----
var fontsReady = null;
function ensureFonts() {
  if (fontsReady) return fontsReady;
  fontsReady = (async function () {
    var candidates = [
      { family: "Malgun Gothic", style: "Regular" },
      { family: "Noto Sans KR", style: "Regular" },
      { family: "Apple SD Gothic Neo", style: "Regular" },
      { family: "Inter", style: "Regular" }
    ];
    for (var i = 0; i < candidates.length; i++) {
      try { await figma.loadFontAsync(candidates[i]); return candidates[i]; } catch (e) {}
    }
    return { family: "Inter", style: "Regular" };
  })();
  return fontsReady;
}

async function makeText(str, opts) {
  opts = opts || {};
  var font = await ensureFonts();
  var t = figma.createText();
  t.fontName = font;
  t.characters = str;
  t.fontSize = opts.size || 12;
  if (opts.color) t.fills = [{ type: "SOLID", color: opts.color }];
  if (opts.align) t.textAlignHorizontal = opts.align;
  return t;
}

// ---- 배치 계산: 기존 보드들 아래로 순서대로 쌓기 ----
function nextBoardY() {
  var maxBottom = 0;
  figma.currentPage.children.forEach(function (n) {
    if (n.getPluginData && n.getPluginData(BOARD_MARK) === "1") {
      var bottom = n.y + n.height;
      if (bottom > maxBottom) maxBottom = bottom;
    }
  });
  return maxBottom === 0 ? 0 : maxBottom + GAP_Y;
}

function styleSlot(frame, placeholderKind) {
  // placeholderKind: 'empty' (채워야 함, 주황 점선) | 'blank' (미개발, 회색 실선)
  frame.cornerRadius = 8;
  frame.clipsContent = true;
  if (placeholderKind === "blank") {
    frame.fills = [{ type: "SOLID", color: { r: 0.90, g: 0.90, b: 0.91 } }];
    frame.strokes = [{ type: "SOLID", color: { r: 0.75, g: 0.75, b: 0.76 } }];
    frame.dashPattern = [];
  } else {
    frame.fills = [{ type: "SOLID", color: { r: 0.97, g: 0.97, b: 0.98 } }];
    frame.strokes = [{ type: "SOLID", color: { r: 0.85, g: 0.55, b: 0.25 } }];
    frame.dashPattern = [6, 5];
  }
  frame.strokeWeight = 1.5;
}

async function setSlotPlaceholder(frame, label) {
  frame.children.slice().forEach(function (c) { c.remove(); });
  var t = await makeText(label, { size: 13, color: { r: 0.5, g: 0.52, b: 0.55 }, align: "CENTER" });
  t.textAlignVertical = "CENTER";
  t.resize(frame.width - 24, frame.height - 24);
  t.x = 12; t.y = 12;
  frame.appendChild(t);
}

async function fillSlotWithImage(frame, bytes) {
  frame.children.slice().forEach(function (c) { c.remove(); });
  var image = figma.createImage(new Uint8Array(bytes));
  frame.fills = [{ type: "IMAGE", imageHash: image.hash, scaleMode: "FIT" }];
  frame.strokes = [];
  frame.dashPattern = [];
}

// ---- 보드 생성: 화면 하나 = 캔버스 위 [디자인 자리][개발화면 자리] ----
async function createBoard(screenId, name, state) {
  var board = figma.createFrame();
  board.name = "🧩 " + name;
  board.setPluginData(BOARD_MARK, "1");
  board.setPluginData(SCREEN_MARK, screenId);
  board.fills = [];
  board.resize(BOARD_PAD * 2 + SLOT_W * 2 + GAP_X, BOARD_PAD * 2 + TITLE_H + SLOT_H);
  board.x = 0;
  board.y = nextBoardY();

  var title = await makeText(name + " · v1", { size: 16, color: { r: 0.1, g: 0.11, b: 0.13 } });
  title.x = BOARD_PAD; title.y = BOARD_PAD;
  board.appendChild(title);

  var designSlot = figma.createFrame();
  designSlot.name = "디자인";
  designSlot.x = BOARD_PAD; designSlot.y = BOARD_PAD + TITLE_H;
  designSlot.resize(SLOT_W, SLOT_H);
  designSlot.setPluginData(SCREEN_MARK, screenId);
  styleSlot(designSlot, "empty");
  board.appendChild(designSlot);
  await setSlotPlaceholder(designSlot, "🎨 디자인 연결 필요\n(피그마에서 프레임 선택 후\n패널의 '연결' 버튼)");

  var devSlot = figma.createFrame();
  devSlot.name = "개발화면";
  devSlot.x = BOARD_PAD + SLOT_W + GAP_X; devSlot.y = BOARD_PAD + TITLE_H;
  devSlot.resize(SLOT_W, SLOT_H);
  devSlot.setPluginData(SCREEN_MARK, screenId);
  if (state === "blank") {
    styleSlot(devSlot, "blank");
    await setSlotPlaceholder(devSlot, "🔲 미개발\n(개발 대기)");
  } else {
    styleSlot(devSlot, "empty");
    await setSlotPlaceholder(devSlot, "🖥 캡처 필요\n(패널에서 이미지 넣기)");
  }
  board.appendChild(devSlot);

  figma.currentPage.appendChild(board);
  return { boardId: board.id, designSlotId: designSlot.id, devSlotId: devSlot.id, titleId: title.id };
}

async function updateBoardTitle(titleId, text) {
  var t = await figma.getNodeByIdAsync(titleId);
  if (t && t.type === "TEXT") { t.fontName = await ensureFonts(); t.characters = text; }
}

// ---- 라벨 검수용: 디자인 프레임 안의 실제 글자를 정확히 읽어오기 (OCR 아님, 피그마 데이터 그대로) ----
function collectTextNodes(node, out, frameBox) {
  if (node.type === "TEXT" && node.visible !== false) {
    var b = node.absoluteBoundingBox;
    if (b && frameBox.width > 0 && frameBox.height > 0) {
      out.push({
        characters: node.characters,
        xPercent: (b.x - frameBox.x + b.width / 2) / frameBox.width,
        yPercent: (b.y - frameBox.y + b.height / 2) / frameBox.height,
        wPercent: b.width / frameBox.width,
        hPercent: b.height / frameBox.height,
        fontSize: (typeof node.fontSize === "number") ? node.fontSize : null
      });
    }
  }
  if (node.children) {
    for (var i = 0; i < node.children.length; i++) collectTextNodes(node.children[i], out, frameBox);
  }
}

async function setBoardArchived(boardId, archived) {
  var b = await figma.getNodeByIdAsync(boardId);
  if (b) b.opacity = archived ? 0.35 : 1;
}

// ---- 자동 검수 표시: 개발화면 자리 위에 "다른 영역"을 사각형으로 감싸고 번호를 붙임 ----
var MARK_COLOR = { r: 0.90, g: 0.20, b: 0.20 };
var BADGE_R = 11;
async function addPin(slotId, xPercent, yPercent, wPercent, hPercent, number) {
  var slot = await figma.getNodeByIdAsync(slotId);
  if (!slot) return null;

  var w = Math.max(28, (wPercent || 0.12) * slot.width);
  var h = Math.max(28, (hPercent || 0.10) * slot.height);
  var cx = Math.max(0, Math.min(1, xPercent)) * slot.width;
  var cy = Math.max(0, Math.min(1, yPercent)) * slot.height;
  var bx = cx - w / 2, by = cy - h / 2;

  var box = figma.createRectangle();
  box.resize(w, h);
  box.x = bx; box.y = by;
  box.fills = [{ type: "SOLID", color: { r: 1, g: 0.3, b: 0.3 }, opacity: 0.14 }];
  box.strokes = [{ type: "SOLID", color: MARK_COLOR }];
  box.strokeWeight = 2;
  box.cornerRadius = 4;
  box.name = "다른 영역 " + number;

  var badgeX = Math.max(0, Math.min(slot.width - BADGE_R * 2, bx - BADGE_R));
  var badgeY = Math.max(0, Math.min(slot.height - BADGE_R * 2, by - BADGE_R));
  var badge = figma.createEllipse();
  badge.resize(BADGE_R * 2, BADGE_R * 2);
  badge.x = badgeX; badge.y = badgeY;
  badge.fills = [{ type: "SOLID", color: MARK_COLOR }];
  badge.strokes = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
  badge.strokeWeight = 1.5;
  badge.name = "번호 " + number;

  var label = await makeText(String(number), { size: 11, color: { r: 1, g: 1, b: 1 }, align: "CENTER" });
  label.textAlignVertical = "CENTER";
  label.resize(BADGE_R * 2, BADGE_R * 2);
  label.x = badgeX; label.y = badgeY;

  slot.appendChild(box);
  slot.appendChild(badge);
  slot.appendChild(label);

  var group = figma.group([box, badge, label], slot);
  group.name = "📌 " + number;
  return group.id;
}

async function removeNodeIfExists(nodeId) {
  if (!nodeId) return;
  var n = await figma.getNodeByIdAsync(nodeId);
  if (n) n.remove();
}

// ---- 선택 동기화: 캔버스에서 보드를 클릭하면 패널에 알림 ----
function findScreenIdFromSelection() {
  var sel = figma.currentPage.selection;
  if (!sel || sel.length === 0) return null;
  var node = sel[0];
  while (node) {
    var v = node.getPluginData ? node.getPluginData(SCREEN_MARK) : "";
    if (v) return v;
    node = node.parent && node.parent.type !== "PAGE" ? node.parent : null;
  }
  return null;
}
figma.on("selectionchange", function () {
  var screenId = findScreenIdFromSelection();
  if (screenId) figma.ui.postMessage({ type: "canvas-selected-screen", screenId: screenId });
});

// ============================================================
//  UI 메시지 처리
// ============================================================
figma.ui.onmessage = async function (msg) {
  try {
    if (msg.type === "init") {
      figma.ui.postMessage({ type: "project-loaded", project: loadProject() });
    }

    else if (msg.type === "save-project") {
      saveProject(msg.project);
    }

    else if (msg.type === "create-board") {
      var result = await createBoard(msg.screenId, msg.name, msg.state);
      figma.ui.postMessage({ type: "board-created", screenId: msg.screenId, result: result });
      var boardNode = await figma.getNodeByIdAsync(result.boardId);
      if (boardNode) figma.viewport.scrollAndZoomIntoView([boardNode]);
    }

    else if (msg.type === "rename-board") {
      await updateBoardTitle(msg.titleId, msg.text);
    }

    else if (msg.type === "set-board-archived") {
      await setBoardArchived(msg.boardId, msg.archived);
    }

    else if (msg.type === "set-dev-blank") {
      var slot = await figma.getNodeByIdAsync(msg.slotId);
      if (slot) {
        if (msg.blank) { styleSlot(slot, "blank"); await setSlotPlaceholder(slot, "🔲 미개발\n(개발 대기)"); }
        else { styleSlot(slot, "empty"); await setSlotPlaceholder(slot, "🖥 캡처 필요\n(패널에서 이미지 넣기)"); }
      }
    }

    // 이미지: 클라이언트 저장소(파일 안)에 보관 + 해당 캔버스 슬롯에 즉시 채움
    else if (msg.type === "set-image") {
      var bytesArr = Array.prototype.slice.call(msg.bytes);
      await figma.clientStorage.setAsync(msg.key, bytesArr);
      var target = await figma.getNodeByIdAsync(msg.slotId);
      if (target) await fillSlotWithImage(target, bytesArr);
      figma.ui.postMessage({ type: "image-set", key: msg.key, slotId: msg.slotId });
    }

    // 과거 버전 보기 / 현재로 복귀: 저장된 바이트를 슬롯에 다시 채움
    else if (msg.type === "view-image") {
      var arr = await figma.clientStorage.getAsync(msg.key);
      var slotNode = await figma.getNodeByIdAsync(msg.slotId);
      if (!slotNode) return;
      if (arr && arr.length) await fillSlotWithImage(slotNode, arr);
      else { styleSlot(slotNode, msg.emptyKind || "empty"); await setSlotPlaceholder(slotNode, msg.emptyLabel || "이미지 없음"); }
    }

    else if (msg.type === "reset-slot") {
      var rs = await figma.getNodeByIdAsync(msg.slotId);
      if (rs) { styleSlot(rs, msg.kind || "empty"); await setSlotPlaceholder(rs, msg.label || "캡처 필요"); }
    }

    // 자동 검수용: 저장된 이미지 바이트 돌려주기 (패널에서 픽셀 비교하려고)
    else if (msg.type === "get-image-bytes") {
      var b = await figma.clientStorage.getAsync(msg.key);
      figma.ui.postMessage({ type: "image-bytes", key: msg.key, bytes: b || null });
    }

    // 자동 검수 결과: 개발화면 자리 위에 "다른 영역" 표시하기
    else if (msg.type === "add-pin") {
      var pinId = await addPin(msg.slotId, msg.xPercent, msg.yPercent, msg.wPercent, msg.hPercent, msg.number);
      figma.ui.postMessage({ type: "pin-added", reqId: msg.reqId, pinId: pinId });
    }

    else if (msg.type === "remove-node") {
      await removeNodeIfExists(msg.nodeId);
    }

    // 라벨 검수용: 연결된 디자인 프레임 안의 실제 글자 목록 돌려주기
    else if (msg.type === "get-design-texts") {
      var srcNode = await figma.getNodeByIdAsync(msg.nodeId);
      if (!srcNode) {
        figma.ui.postMessage({ type: "design-texts", screenId: msg.screenId, texts: [], debug: "노드를 찾을 수 없음 (id=" + msg.nodeId + ")" });
        return;
      }
      if (!srcNode.absoluteBoundingBox) {
        figma.ui.postMessage({ type: "design-texts", screenId: msg.screenId, texts: [], debug: "위치 정보 없음 (종류=" + srcNode.type + ")" });
        return;
      }
      var texts = [];
      collectTextNodes(srcNode, texts, srcNode.absoluteBoundingBox);
      var childCount = srcNode.children ? srcNode.children.length : 0;
      figma.ui.postMessage({
        type: "design-texts", screenId: msg.screenId, texts: texts,
        debug: "종류=" + srcNode.type + ", 직속자식=" + childCount + "개, 찾은글자=" + texts.length + "개"
      });
    }

    // 현재 페이지의 연결 가능한 프레임 목록 (우리 보드 자신은 제외)
    else if (msg.type === "list-frames") {
      await figma.loadAllPagesAsync().catch(function () {});
      var frames = figma.currentPage.children
        .filter(function (n) { return LINKABLE[n.type] && n.getPluginData(BOARD_MARK) !== "1"; })
        .map(function (n) { return { id: n.id, name: n.name }; });
      figma.ui.postMessage({ type: "frames-listed", frames: frames });
    }

    else if (msg.type === "use-selection") {
      var sel = figma.currentPage.selection;
      if (!sel || sel.length === 0 || sel[0].getPluginData(BOARD_MARK) === "1") {
        figma.ui.postMessage({ type: "selection-result", error: "피그마에서 비교할 디자인 화면(프레임)을 먼저 선택해 주세요." });
        return;
      }
      var node = sel[0];
      figma.ui.postMessage({ type: "selection-result", node: { id: node.id, name: node.name } });
    }

    // 디자인 프레임을 PNG로 추출 (2배 해상도)
    else if (msg.type === "export-frame") {
      var target2 = await figma.getNodeByIdAsync(msg.nodeId);
      if (!target2) { figma.ui.postMessage({ type: "frame-exported", nodeId: msg.nodeId, error: "연결된 화면을 찾을 수 없어요. 삭제되었을 수 있어요." }); return; }
      if (typeof target2.exportAsync !== "function") { figma.ui.postMessage({ type: "frame-exported", nodeId: msg.nodeId, error: "이 항목은 이미지로 뽑을 수 없어요." }); return; }
      var bytes = await target2.exportAsync({ format: "PNG", constraint: { type: "SCALE", value: 2 } });
      figma.ui.postMessage({ type: "frame-exported", nodeId: msg.nodeId, name: target2.name, bytes: bytes });
    }

    else if (msg.type === "go-to-node") {
      var n = await figma.getNodeByIdAsync(msg.nodeId);
      if (n) { figma.currentPage.selection = [n]; figma.viewport.scrollAndZoomIntoView([n]); }
      else figma.notify("캔버스에서 해당 요소를 찾을 수 없어요.");
    }

    else if (msg.type === "resize") {
      figma.ui.resize(Math.max(360, msg.width | 0), Math.max(480, msg.height | 0));
    }

    else if (msg.type === "notify") {
      figma.notify(msg.message);
    }
  } catch (err) {
    figma.ui.postMessage({ type: "error", message: String(err && err.message ? err.message : err) });
    figma.notify("문제가 생겼어요: " + String(err && err.message ? err.message : err));
  }
};
