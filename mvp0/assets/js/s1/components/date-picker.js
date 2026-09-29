// Date Picker — 정본 buildDatePicker(트리거)·buildCalendar(패널 Date/Year/Month)·buildCalendarCell·buildCalendarTile·
// buildDatePickerBottomSheet(모바일) 기준. 상호작용 규칙(팝오버 배치·연월 전환·기간 선택·키보드)은 정본에 없어
// 2-canon-readiness.md 의 river 결정(D3~D6)·오케스트레이터 메커니즘 결정(M1~M7)을 따른다 — manifest.notInCanon 참조.
export const componentId = "date-picker";
export const jsRequired = true;

const instances = new WeakMap();
const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"]; // D3: 일요일 시작(river 결정, CU-1)
const MONTH_LABELS = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"];

/* 트리거 안내 문구 — 폭과 상관없이 항상 "날짜 선택"(river 지시 2026-09-23,
   전날의 "날짜를 선택하세요" + 자동 축약을 번복한다). 서비스는 data-placeholder 로 바꾼다. */
const PLACEHOLDER_DEFAULT = "날짜 선택";

function pad2(n) {
  return String(n).padStart(2, "0");
}

function toISO(date) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function parseISO(value) {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(d.getTime()) ? null : d;
}

/* M6: 표시는 정본 트리거 그대로 YY.MM.DD(2자리 연도), 값 입출력은 YYYY-MM-DD(ISO).
   2026-09-08 river 지시로 4자리(YYYY.MM.DD)를 한 번 넣었다가 같은 날 원복했다 — 감사 문서 §9 M-8. */
function formatDisplay(date) {
  const yy = pad2(date.getFullYear() % 100);
  return `${yy}.${pad2(date.getMonth() + 1)}.${pad2(date.getDate())}`;
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function isSameDate(a, b) {
  return !!a && !!b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

// F-3: time-picker.js 의 모바일 시트 포커스 가둠과 동일한 구현(선언과 구현을 맞춘다).
const SHEET_FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  '[tabindex]:not([tabindex="-1"])'
].join(",");

function sheetFocusables(sheetPanel) {
  return [...sheetPanel.querySelectorAll(SHEET_FOCUSABLE)].filter((el) => el.offsetParent !== null);
}

function addMonths(year, month, delta) {
  const d = new Date(year, month + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() };
}

// 5주×7일이 부족하면 6주까지 확장한다(정본 데모는 1월 고정 5주라 6주 케이스가 없음 — 실제 달력은 필요).
function buildMonthGrid(year, month) {
  const first = new Date(year, month, 1);
  const firstWeekday = first.getDay(); // 0=일
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstWeekday; i += 1) {
    const day = daysInPrevMonth - firstWeekday + 1 + i;
    const { year: py, month: pm } = addMonths(year, month, -1);
    cells.push({ date: new Date(py, pm, day), otherMonth: true });
  }
  for (let day = 1; day <= daysInMonth; day += 1) cells.push({ date: new Date(year, month, day), otherMonth: false });
  while (cells.length % 7 !== 0 || cells.length < 35) {
    const { year: ny, month: nm } = addMonths(year, month, 1);
    const day = cells.length - (firstWeekday + daysInMonth) + 1;
    cells.push({ date: new Date(ny, nm, day), otherMonth: true });
  }
  return cells;
}

function getParts(root) {
  return {
    trigger: root.querySelector('[data-s1-part="trigger"]'),
    value: root.querySelector('[data-s1-part="value"]'),
    panel: root.querySelector('[data-s1-part="panel"]'),
    panelCalendar: root.querySelector('[data-s1-part="panel"] [data-s1-part="calendar"]'),
    sheet: root.querySelector('[data-s1-part="sheet"]'),
    sheetBackdrop: root.querySelector('[data-s1-part="sheet-backdrop"]'),
    sheetPanel: root.querySelector('[data-s1-part="sheet-panel"]'),
    sheetClose: root.querySelector('[data-s1-part="sheet-close"]'),
    sheetCalendar: root.querySelector('[data-s1-part="sheet"] [data-s1-part="calendar"]'),
    apply: root.querySelector('[data-s1-part="apply"]')
  };
}

function isOpen(root, trigger) {
  return trigger.getAttribute("aria-expanded") === "true";
}

// ── 캘린더 렌더링 (PC 패널·모바일 시트가 공유) ──────────────────────────────────────────
function renderHeader(headerLabel, s) {
  const y = document.createElement("button");
  y.type = "button"; y.dataset.s1Part = "year-label";
  y.textContent = `${s.viewYear}년`;
  const m = document.createElement("button");
  m.type = "button"; m.dataset.s1Part = "month-label";
  m.textContent = MONTH_LABELS[s.viewMonth];
  headerLabel.replaceChildren(...(s.view === "date" ? [y, m] : [y]));
}

function renderCell(cell, day, s, ctx) {
  const iso = toISO(day.date);
  cell.dataset.date = iso;
  cell.dataset.otherMonth = day.otherMonth ? "true" : "false";
  const weekday = day.date.getDay();
  cell.dataset.weekday = String(weekday);
  const disabled = s.disabledSet.has(iso);
  cell.disabled = disabled;
  cell.setAttribute("role", "gridcell");
  cell.tabIndex = -1;

  let state = "default";
  let selectedForAria = false;
  let bandKind = null;

  if (s.mode === "range") {
    const { start, end } = s.selected || {};
    const startISO = start ? toISO(start) : null;
    const endISO = end ? toISO(end) : null;
    const hoverISO = !end && start && s.hoverISO ? s.hoverISO : null;
    const previewEndISO = hoverISO && hoverISO >= startISO ? hoverISO : null;
    const rangeEndForBand = endISO || previewEndISO;
    if (startISO && iso === startISO && rangeEndForBand && rangeEndForBand !== startISO) {
      state = "today"; bandKind = "start"; selectedForAria = true;
    } else if (rangeEndForBand && iso === rangeEndForBand && rangeEndForBand !== startISO) {
      state = "selected"; bandKind = "end"; selectedForAria = true;
    } else if (startISO && rangeEndForBand && iso > startISO && iso < rangeEndForBand) {
      state = disabled ? "range-disabled" : "range-mid"; bandKind = "mid"; selectedForAria = true;
    } else if (startISO && iso === startISO) {
      state = "today"; selectedForAria = true; // 시작일만 선택된 경우(단일 점)
    } else {
      state = disabled ? "disabled" : "default";
    }
  } else {
    const sel = s.selected ? toISO(s.selected) : null;
    if (sel && iso === sel) { state = "selected"; selectedForAria = true; }
    else if (isSameDate(day.date, s.today)) state = "today";
    else state = disabled ? "disabled" : "default";
  }

  cell.dataset.state = state;
  if (bandKind) cell.dataset.rangeBand = bandKind; else delete cell.dataset.rangeBand;
  cell.setAttribute("aria-selected", String(selectedForAria));
  if (disabled) cell.setAttribute("aria-disabled", "true"); else cell.removeAttribute("aria-disabled");

  let inner = cell.querySelector('[data-s1-part="cell-inner"]');
  if (!inner) {
    inner = document.createElement("span");
    inner.dataset.s1Part = "cell-inner";
    const num = document.createElement("span");
    num.dataset.s1Part = "cell-num";
    inner.appendChild(num);
    cell.appendChild(inner);
  }
  inner.querySelector('[data-s1-part="cell-num"]').textContent = String(day.date.getDate());
}

function renderDateView(view, s, ctx) {
  let weekdaysRow = view.querySelector('[data-s1-part="weekdays"]');
  let grid = view.querySelector('[data-s1-part="grid"]');
  if (!weekdaysRow) {
    weekdaysRow = document.createElement("div");
    weekdaysRow.dataset.s1Part = "weekdays";
    for (let i = 0; i < 7; i += 1) {
      const wk = document.createElement("span");
      wk.dataset.s1Part = "weekday";
      wk.dataset.weekday = String(i);
      wk.textContent = WEEKDAY_LABELS[i];
      weekdaysRow.appendChild(wk);
    }
    view.appendChild(weekdaysRow);
  }
  if (!grid) {
    grid = document.createElement("div");
    grid.dataset.s1Part = "grid";
    grid.setAttribute("role", "grid");
    view.appendChild(grid);
  }
  const cells = buildMonthGrid(s.viewYear, s.viewMonth);
  const weekCount = cells.length / 7;
  const rows = [...grid.querySelectorAll('[data-s1-part="week"]')];
  while (rows.length < weekCount) {
    const row = document.createElement("div");
    row.dataset.s1Part = "week";
    row.setAttribute("role", "row");
    grid.appendChild(row);
    rows.push(row);
  }
  while (rows.length > weekCount) grid.removeChild(rows.pop());
  for (let r = 0; r < weekCount; r += 1) {
    const row = rows[r];
    const rowCells = [...row.querySelectorAll('[data-s1-part="cell"]')];
    for (let c = 0; c < 7; c += 1) {
      let cell = rowCells[c];
      if (!cell) {
        cell = document.createElement("button");
        cell.type = "button";
        cell.dataset.s1Part = "cell";
        row.appendChild(cell);
      }
      renderCell(cell, cells[r * 7 + c], s, ctx);
    }
  }
}

function renderTileView(view, kind, s, ctx) {
  let grid = view.querySelector('[data-s1-part="grid"]');
  if (!grid) {
    grid = document.createElement("div");
    grid.dataset.s1Part = "grid";
    grid.dataset.tileGrid = kind;
    view.appendChild(grid);
  }
  const items = kind === "year"
    ? Array.from({ length: 12 }, (_, i) => Math.floor(s.viewYear / 12) * 12 + i)
    : MONTH_LABELS.map((_, i) => i);
  const rows = [...grid.querySelectorAll('[data-s1-part="tile-row"]')];
  while (rows.length < 4) {
    const row = document.createElement("div");
    row.dataset.s1Part = "tile-row";
    grid.appendChild(row);
    rows.push(row);
  }
  for (let r = 0; r < 4; r += 1) {
    const row = rows[r];
    const tiles = [...row.querySelectorAll('[data-s1-part="tile"]')];
    for (let c = 0; c < 3; c += 1) {
      let tile = tiles[c];
      if (!tile) {
        tile = document.createElement("button");
        tile.type = "button";
        tile.dataset.s1Part = "tile";
        row.appendChild(tile);
      }
      const value = items[r * 3 + c];
      const disabled = kind === "year" ? !!ctx.yearDisabled?.(value) : false;
      tile.disabled = disabled;
      tile.textContent = kind === "year" ? String(value) : MONTH_LABELS[value];
      tile.dataset.value = String(value);
      const isSelected = kind === "year" ? value === s.viewYear : value === s.viewMonth;
      tile.setAttribute("aria-selected", String(isSelected));
    }
  }
}

function renderCalendar(container, s, ctx) {
  container.dataset.view = s.view;
  // SM 달력은 연/월 타일 뷰에서만 아래 여백이 다르다(정본 CAL_GEO.SM padBottomDate 16 · padBottomTile 20).
  // CSS 는 자식으로 부모를 고를 수 없어 패널에도 같은 표시를 남긴다.
  const panelEl = container.closest('[data-s1-part="panel"]');
  if (panelEl) panelEl.dataset.view = s.view;
  let header = container.querySelector('[data-s1-part="header"]');
  if (!header) {
    header = document.createElement("div");
    header.dataset.s1Part = "header";
    const prev = document.createElement("button");
    prev.type = "button"; prev.dataset.s1Part = "prev"; prev.setAttribute("aria-label", "이전");
    const prevIcon = document.createElement("span");
    prevIcon.dataset.s1Part = "chevron-icon"; prevIcon.setAttribute("aria-hidden", "true");
    prev.appendChild(prevIcon);
    const label = document.createElement("div");
    label.dataset.s1Part = "header-label";
    const next = document.createElement("button");
    next.type = "button"; next.dataset.s1Part = "next"; next.setAttribute("aria-label", "다음");
    const nextIcon = document.createElement("span");
    nextIcon.dataset.s1Part = "chevron-icon"; nextIcon.setAttribute("aria-hidden", "true");
    next.appendChild(nextIcon);
    header.append(prev, label, next);
    container.appendChild(header);
  }
  renderHeader(header.querySelector('[data-s1-part="header-label"]'), s);

  let view = container.querySelector('[data-s1-part="view"]');
  if (!view) {
    view = document.createElement("div");
    view.dataset.s1Part = "view";
    container.appendChild(view);
  }
  if (s.view === "date") {
    view.querySelector('[data-s1-part="grid"][data-tile-grid]')?.remove();
    renderDateView(view, s, ctx);
  } else {
    view.querySelector('[data-s1-part="weekdays"]')?.remove();
    const staleGrid = view.querySelector('[data-s1-part="grid"]:not([data-tile-grid])');
    if (staleGrid) staleGrid.remove();
    const staleTileGrid = view.querySelector(`[data-tile-grid]:not([data-tile-grid="${s.view}"])`);
    if (staleTileGrid) staleTileGrid.remove();
    renderTileView(view, s.view, s, ctx);
  }
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const { trigger, value, panel, panelCalendar, sheet, sheetBackdrop, sheetPanel, sheetClose, sheetCalendar, apply } = getParts(root);
  if (!trigger || !value) return null;

  /* 자기 data-break 가 먼저고, 없으면 감싸는 요소의 화면 선언(data-s1-break)을 따른다.
     감싸기에만 모바일을 적어 두면 높이는 모바일인데 PC 팝업이 열리던 어긋남을 없앤다(2026-09-15). */
  const ownBreak = root.dataset.break;
  const declaredBreak = ownBreak || root.closest("[data-s1-break]")?.dataset.s1Break;
  const brk = declaredBreak === "mobile" ? "mobile" : "pc";
  const mode = root.dataset.mode === "range" ? "range" : "single";
  const disabledSet = new Set((root.dataset.disabledDates || "").split(",").map((s) => s.trim()).filter(Boolean));
  const today = startOfDay(new Date());

  const initialSingle = mode === "single" ? parseISO(root.dataset.value) : null;
  const initialRange = mode === "range"
    ? { start: parseISO(root.dataset.rangeStart), end: parseISO(root.dataset.rangeEnd) }
    : null;
  const anchor = initialSingle || initialRange?.start || today;

  const s = {
    mode,
    view: "date",
    viewYear: anchor.getFullYear(),
    viewMonth: anchor.getMonth(),
    selected: mode === "single" ? initialSingle : initialRange,
    hoverISO: null,
    disabledSet,
    today
  };

  const ctx = {};

  const container = brk === "mobile" ? sheetCalendar : panelCalendar;
  if (!container) return null;

  const applyPlaceholder = () => { value.textContent = root.dataset.placeholder || PLACEHOLDER_DEFAULT; };

  const syncValueText = () => {
    if (mode === "single") {
      if (s.selected) value.textContent = formatDisplay(s.selected); else applyPlaceholder();
      trigger.dataset.filled = s.selected ? "true" : "false";
    } else {
      const { start, end } = s.selected || {};
      if (start && end) { value.textContent = `${formatDisplay(start)} ~ ${formatDisplay(end)}`; trigger.dataset.filled = "true"; }
      else if (start) { value.textContent = `${formatDisplay(start)} ~ `; trigger.dataset.filled = "true"; }
      else { applyPlaceholder(); trigger.dataset.filled = "false"; }
    }
  };

  const rerender = () => renderCalendar(container, s, ctx);

  // M1: 트리거 아래 8px 팝오버, 아래 공간이 모자라면 위로 뒤집는다.
  const positionPanel = () => {
    if (brk !== "pc" || !panel) return;
    panel.removeAttribute("data-flip");
    const rect = trigger.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    const viewportH = window.innerHeight || document.documentElement.clientHeight;
    if (rect.bottom + 8 + panelRect.height > viewportH && rect.top - 8 - panelRect.height >= 0) {
      panel.setAttribute("data-flip", "up");
    }
  };

  const close = ({ returnFocus = true } = {}) => {
    if (!isOpen(root, trigger)) return;
    trigger.setAttribute("aria-expanded", "false");
    if (brk === "pc" && panel) { panel.hidden = true; document.removeEventListener("pointerdown", handleOutsidePointer, true); }
    if (brk === "mobile" && sheet) closeSheet({ returnFocus: false });
    if (returnFocus) trigger.focus();
    root.dispatchEvent(new CustomEvent("s1:date-picker:close", { bubbles: true, detail: {} }));
  };

  let lastFocused = null;
  const openSheet = () => {
    lastFocused = trigger; // 항상 자기 트리거로 복귀(time-picker.js 와 동일 판단 — document.activeElement 는 클릭 방식에 따라 신뢰 불가)
    sheet.hidden = false;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleSheetKeydown, true);
    // F-3: manifest a11y.focus 선언("열리면 시트 안으로") 이행 — time-picker.js 와 동일 구현.
    const firstFocusable = sheetPanel ? sheetFocusables(sheetPanel)[0] : null;
    (firstFocusable || sheetPanel)?.focus();
  };
  const closeSheet = ({ returnFocus = true } = {}) => {
    sheet.hidden = true;
    document.body.style.overflow = "";
    document.removeEventListener("keydown", handleSheetKeydown, true);
    if (returnFocus && lastFocused?.focus) lastFocused.focus();
  };
  // F-3: Tab 가둠 — time-picker.js handleSheetKeydown 과 동일 구현(선언·구현 일치).
  const handleSheetKeydown = (event) => {
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (event.key !== "Tab" || !sheetPanel) return;
    const list = sheetFocusables(sheetPanel);
    if (!list.length) { event.preventDefault(); sheetPanel.focus(); return; }
    const first = list[0];
    const last = list[list.length - 1];
    if (!sheetPanel.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); return; }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  // F-4: 등록과 동일 참조로 제거하기 위한 named handler.
  const handleSheetCloseClick = () => close();

  const open = () => {
    if (trigger.disabled || isOpen(root, trigger)) return;
    trigger.setAttribute("aria-expanded", "true");
    s.view = "date";
    s.viewYear = (s.mode === "single" ? s.selected : s.selected?.start)?.getFullYear() ?? s.viewYear;
    s.viewMonth = (s.mode === "single" ? s.selected : s.selected?.start)?.getMonth() ?? s.viewMonth;
    rerender();
    if (brk === "pc" && panel) {
      panel.hidden = false;
      positionPanel();
      document.addEventListener("pointerdown", handleOutsidePointer, true);
      const firstCell = container.querySelector('[data-s1-part="cell"]:not(:disabled)');
      firstCell?.focus();
    } else if (brk === "mobile" && sheet) {
      openSheet();
    }
    root.dispatchEvent(new CustomEvent("s1:date-picker:open", { bubbles: true, detail: {} }));
  };

  const handleOutsidePointer = (event) => {
    if (!root.contains(event.target)) close({ returnFocus: false });
  };

  const handleTriggerClick = () => { if (isOpen(root, trigger)) close(); else open(); };

  const emitChange = () => {
    const detail = mode === "single"
      ? { value: s.selected ? toISO(s.selected) : null, mode }
      : { start: s.selected?.start ? toISO(s.selected.start) : null, end: s.selected?.end ? toISO(s.selected.end) : null, mode };
    root.dispatchEvent(new CustomEvent("s1:date-picker:change", { bubbles: true, detail }));
  };

  const selectDate = (date) => {
    const iso = toISO(date);
    if (disabledSet.has(iso)) return;
    if (mode === "single") {
      s.selected = date;
      syncValueText();
      emitChange();
      rerender();
      close();
      return;
    }
    // D4: 시작일보다 앞선 날짜를 두 번째로 누르면 그 날짜가 새 시작일이 된다(자동 뒤집기 금지).
    const { start, end } = s.selected || {};
    if (!start || end) {
      s.selected = { start: date, end: null };
    } else if (iso < toISO(start)) {
      s.selected = { start: date, end: null };
    } else if (iso === toISO(start)) {
      s.selected = { start: date, end: date };
    } else {
      s.selected = { start, end: date };
    }
    syncValueText();
    rerender();
    if (s.selected.start && s.selected.end) { emitChange(); close(); }
  };

  const goToMonth = (year, month) => {
    s.viewYear = year; s.viewMonth = month; rerender();
    if (brk === "pc") positionPanel();
  };

  const handleContainerClick = (event) => {
    const prevBtn = event.target.closest('[data-s1-part="prev"]');
    const nextBtn = event.target.closest('[data-s1-part="next"]');
    const yearLabel = event.target.closest('[data-s1-part="year-label"]');
    const monthLabel = event.target.closest('[data-s1-part="month-label"]');
    const cell = event.target.closest('[data-s1-part="cell"]');
    const tile = event.target.closest('[data-s1-part="tile"]');

    if (prevBtn || nextBtn) {
      const delta = prevBtn ? -1 : 1;
      // M2: Date=한 달, Month=1년, Year=12년 이동.
      if (s.view === "date") { const m = addMonths(s.viewYear, s.viewMonth, delta); goToMonth(m.year, m.month); }
      else if (s.view === "month") { s.viewYear += delta; rerender(); }
      else { s.viewYear += delta * 12; rerender(); }
      return;
    }
    if (yearLabel) { s.view = "year"; rerender(); return; }
    if (monthLabel) { s.view = "month"; rerender(); return; }
    if (tile) {
      const val = Number(tile.dataset.value);
      if (s.view === "year") { s.viewYear = val; s.view = "month"; rerender(); }
      else { s.viewMonth = val; s.view = "date"; rerender(); }
      return;
    }
    if (cell && !cell.disabled) {
      // M3: 이전달/다음달 셀 클릭 허용 — 그 달로 이동 후 선택(HD-7).
      const date = parseISO(cell.dataset.date);
      if (!date) return;
      if (cell.dataset.otherMonth === "true") goToMonth(date.getFullYear(), date.getMonth());
      selectDate(date);
    }
  };

  // D6: 시작일만 고른 상태에서 hover 하면 커서 위치까지 밴드를 미리 칠한다.
  const handleContainerMouseover = (event) => {
    if (s.mode !== "range" || s.view !== "date") return;
    const cell = event.target.closest('[data-s1-part="cell"]');
    const iso = cell && !cell.disabled ? cell.dataset.date : null;
    if (iso === s.hoverISO) return;
    s.hoverISO = iso;
    rerender();
  };
  const handleContainerMouseleave = () => {
    if (s.hoverISO) { s.hoverISO = null; rerender(); }
  };

  // M4: 화살표=날짜 이동 · Home/End=주 시작·끝 · PageUp/Down=달 이동 · Enter=선택 · Esc=닫고 트리거 복귀.
  const handleContainerKeydown = (event) => {
    const cell = event.target.closest('[data-s1-part="cell"]');
    const tile = event.target.closest('[data-s1-part="tile"]');
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (cell) {
      const date = parseISO(cell.dataset.date);
      if (!date) return;
      const move = (deltaDays) => {
        const next = new Date(date); next.setDate(next.getDate() + deltaDays);
        if (next.getMonth() !== s.viewMonth || next.getFullYear() !== s.viewYear) goToMonth(next.getFullYear(), next.getMonth());
        else rerender();
        requestAnimationFrame(() => container.querySelector(`[data-s1-part="cell"][data-date="${toISO(next)}"]`)?.focus());
      };
      if (event.key === "ArrowRight") { event.preventDefault(); move(1); }
      else if (event.key === "ArrowLeft") { event.preventDefault(); move(-1); }
      else if (event.key === "ArrowDown") { event.preventDefault(); move(7); }
      else if (event.key === "ArrowUp") { event.preventDefault(); move(-7); }
      else if (event.key === "Home") { event.preventDefault(); move(-date.getDay()); }
      else if (event.key === "End") { event.preventDefault(); move(6 - date.getDay()); }
      else if (event.key === "PageUp") { event.preventDefault(); const m = addMonths(s.viewYear, s.viewMonth, -1); goToMonth(m.year, m.month); }
      else if (event.key === "PageDown") { event.preventDefault(); const m = addMonths(s.viewYear, s.viewMonth, 1); goToMonth(m.year, m.month); }
      else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectDate(date); }
      return;
    }
    if (tile && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); tile.click(); }
  };

  const handleApplyClick = () => {
    // 모바일 시트 "적용" — 단일: 선택된 날짜 확정. 기간: 시작·종료 모두 있어야 확정.
    if (mode === "single" && !s.selected) return;
    if (mode === "range" && (!s.selected?.start || !s.selected?.end)) return;
    syncValueText();
    emitChange();
    close();
  };

  trigger.addEventListener("click", handleTriggerClick);
  container.addEventListener("click", handleContainerClick);
  container.addEventListener("keydown", handleContainerKeydown);
  if (mode === "range") {
    container.addEventListener("mouseover", handleContainerMouseover);
    container.addEventListener("mouseleave", handleContainerMouseleave);
  }
  if (brk === "mobile") {
    sheetClose?.addEventListener("click", handleSheetCloseClick);
    sheetBackdrop?.addEventListener("click", handleSheetCloseClick);
    apply?.addEventListener("click", handleApplyClick);
  }

  /* 폭이 바뀌면 안내 문구 길이를 다시 고른다(창 크기·칸 폭·처음 그려질 때). */
  const disabledObserver = new MutationObserver(() => {
    if (trigger.disabled && isOpen(root, trigger)) close({ returnFocus: false });
  });
  disabledObserver.observe(trigger, { attributes: true, attributeFilter: ["disabled"] });

  syncValueText();
  if (!trigger.hasAttribute("aria-haspopup")) trigger.setAttribute("aria-haspopup", "dialog");
  if (!trigger.hasAttribute("aria-expanded")) trigger.setAttribute("aria-expanded", "false");
  if (panel) panel.hidden = true;
  if (sheet) sheet.hidden = true;

  const api = Object.freeze({
    get open() { return isOpen(root, trigger); },
    openPanel: open,
    closePanel: close,
    destroy() {
      // C-5: 승인된 time-picker.destroy() 와 동일 — 열린 채 destroy 되면 시트가 남고 body 스크롤 잠금이
      // 영구히 풀리지 않는다. close() 를 먼저 불러 시트/패널을 정리한다.
      close({ returnFocus: false });
      trigger.removeEventListener("click", handleTriggerClick);
      container.removeEventListener("click", handleContainerClick);
      container.removeEventListener("keydown", handleContainerKeydown);
      container.removeEventListener("mouseover", handleContainerMouseover);
      container.removeEventListener("mouseleave", handleContainerMouseleave);
      sheetClose?.removeEventListener("click", handleSheetCloseClick);
      sheetBackdrop?.removeEventListener("click", handleSheetCloseClick);
      apply?.removeEventListener("click", handleApplyClick);
      document.removeEventListener("pointerdown", handleOutsidePointer, true);
      document.removeEventListener("keydown", handleSheetKeydown, true);
      disabledObserver.disconnect();
      instances.delete(root);
    }
  });
  instances.set(root, api);
  return api;
}

export function destroy(root) {
  instances.get(root)?.destroy();
}

export const runtime = Object.freeze({ init, destroy });
