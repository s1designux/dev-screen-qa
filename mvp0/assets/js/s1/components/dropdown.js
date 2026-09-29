export const componentId = "dropdown";
export const jsRequired = true;

const instances = new WeakMap();

function getOptions(root) {
  return [...root.querySelectorAll('[data-s1-part="option"]')];
}

function isCheckboxType(root) {
  return root.dataset.type === "checkbox";
}

function isSelectAll(option) {
  return option.dataset.selectAll === "true";
}

function setActive(root, option) {
  for (const opt of getOptions(root)) opt.tabIndex = opt === option ? 0 : -1;
}

function setChecked(option, checked) {
  option.setAttribute("aria-checked", String(checked));
  const control = option.querySelector('input[type="checkbox"]');
  if (control) control.checked = checked;
}

// 「전체 선택」 은 true/false 만 쓴다 — mixed(부분선택)는 정본에 없다(river 결정 2026-08-31, D2).
// 일부만 켜진 상태에서 select-all 은 false 다.
function syncSelectAll(options) {
  const selectAll = options.find(isSelectAll);
  if (!selectAll) return;
  const others = options.filter((option) => option !== selectAll);
  const allChecked = others.length > 0 && others.every((option) => option.getAttribute("aria-checked") === "true");
  setChecked(selectAll, allChecked);
}

// 말줄임(…)된 옵션만 마우스 올림으로 전체 글자를 보여준다 — river 결정 2026-09-07
// ("말줄임된 글자는 마우스 올림으로 보여주고"). 잘리지 않은 옵션에는 붙이지 않는다(불필요한 툴팁 방지).
// 폭은 목록이 실제로 보일 때만 잴 수 있다(닫힌 패널은 display:none 이라 0). 그래서 ResizeObserver 로
// 패널이 열려 크기가 생기는 순간과 트리거 폭이 바뀌는 순간에 다시 잰다.
// 접근성 이름은 옵션 자신의 텍스트가 이미 제공한다 — title 은 눈으로 보는 사용자를 위한 보조다.
function syncEllipsisTitles(root) {
  for (const option of getOptions(root)) {
    const label = option.querySelector('[data-s1-part="option-label"]');
    if (!label) continue;
    const truncated = label.scrollWidth > label.clientWidth + 1;
    const text = label.textContent.trim();
    if (truncated) {
      if (label.getAttribute("title") !== text) label.setAttribute("title", text);
    } else if (label.hasAttribute("title")) {
      label.removeAttribute("title");
    }
  }
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const checkboxType = isCheckboxType(root);
  const options = getOptions(root);
  if (checkboxType) syncSelectAll(options);
  const initialActive = options.find((option) =>
    checkboxType ? option.getAttribute("aria-checked") === "true" : option.getAttribute("aria-selected") === "true"
  ) || options[0];
  if (initialActive) setActive(root, initialActive);

  const dispatchChange = (detail) => {
    root.dispatchEvent(new CustomEvent("s1:dropdown:change", { bubbles: true, detail }));
  };

  const selectOption = (option) => {
    if (!option) return;
    const currentOptions = getOptions(root);

    if (!checkboxType) {
      for (const opt of currentOptions) opt.setAttribute("aria-selected", String(opt === option));
      setActive(root, option);
      dispatchChange({
        type: "text",
        option,
        value: option.dataset.value ?? option.textContent.trim(),
        selected: true
      });
      return;
    }

    if (isSelectAll(option)) {
      // 전체 선택 행: 꺼져 있었으면 전체 켜기, 켜져 있었으면 전체 끄기(registry component-behavior.pc.json "Dropdown (Checkbox)").
      const next = option.getAttribute("aria-checked") !== "true";
      const affected = currentOptions.filter((opt) => opt !== option);
      for (const opt of affected) setChecked(opt, next);
      setChecked(option, next);
      setActive(root, option);
      dispatchChange({
        type: "checkbox",
        option,
        value: option.dataset.value ?? option.textContent.trim(),
        checked: next,
        selectAll: true,
        affected
      });
      return;
    }

    // 일반 옵션: 그 옵션만 토글하고 나머지는 그대로 둔다. 모두 켜지면 select-all 이 스스로 켜진다.
    const next = option.getAttribute("aria-checked") !== "true";
    setChecked(option, next);
    syncSelectAll(currentOptions);
    setActive(root, option);
    const selectAllRow = currentOptions.find(isSelectAll);
    dispatchChange({
      type: "checkbox",
      option,
      value: option.dataset.value ?? option.textContent.trim(),
      checked: next,
      selectAll: false,
      selectAllChecked: selectAllRow ? selectAllRow.getAttribute("aria-checked") === "true" : undefined
    });
  };

  const moveFocus = (from, delta) => {
    const list = getOptions(root);
    if (!list.length) return;
    const index = list.indexOf(from);
    const next = list[(index < 0 ? 0 : index + delta + list.length) % list.length];
    setActive(root, next);
    next.focus();
  };

  const handleClick = (event) => {
    const option = event.target.closest('[data-s1-part="option"]');
    if (option && root.contains(option)) selectOption(option);
  };

  const handleKeydown = (event) => {
    const current = event.target.closest('[data-s1-part="option"]');
    if (!current || !root.contains(current)) return;
    const list = getOptions(root);
    if (event.key === "ArrowDown") { event.preventDefault(); moveFocus(current, 1); }
    else if (event.key === "ArrowUp") { event.preventDefault(); moveFocus(current, -1); }
    else if (event.key === "Home") { event.preventDefault(); setActive(root, list[0]); list[0]?.focus(); }
    else if (event.key === "End") { event.preventDefault(); setActive(root, list[list.length - 1]); list[list.length - 1]?.focus(); }
    else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectOption(current); }
  };

  root.addEventListener("click", handleClick);
  root.addEventListener("keydown", handleKeydown);

  syncEllipsisTitles(root);
  const sizeObserver = typeof ResizeObserver === "function"
    ? new ResizeObserver(() => syncEllipsisTitles(root))
    : null;
  sizeObserver?.observe(root);

  const api = Object.freeze({
    get options() { return getOptions(root); },
    focusActive() {
      const list = getOptions(root);
      const active = list.find((option) => option.tabIndex === 0) || list[0];
      active?.focus();
    },
    // 옵션을 소비자가 다시 그렸을 때 말줄임 안내를 다시 계산한다.
    refresh() { syncEllipsisTitles(root); },
    destroy() {
      root.removeEventListener("click", handleClick);
      root.removeEventListener("keydown", handleKeydown);
      sizeObserver?.disconnect();
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
