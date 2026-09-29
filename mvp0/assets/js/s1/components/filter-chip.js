import { init as initDropdown, destroy as destroyDropdown } from "./dropdown.js";

export const componentId = "filter-chip";
export const jsRequired = true;

const instances = new WeakMap();

function getParts(root) {
  return {
    trigger: root.querySelector('[data-s1-part="trigger"]'),
    title: root.querySelector('[data-s1-part="title"]'),
    value: root.querySelector('[data-s1-part="value"]'),
    panel: root.querySelector('[data-s1-part="panel"]'),
    dropdownRoot: root.querySelector('[data-s1-component="dropdown"]')
  };
}

function isOpen(trigger) {
  return trigger.getAttribute("aria-expanded") === "true";
}

function syncAccessibleName(trigger, title, value) {
  const titleText = title?.textContent.trim();
  const valueText = value?.textContent.trim() ?? "";
  trigger.setAttribute("aria-label", titleText ? `${titleText}, ${valueText}` : valueText);
}

// river 실사용 지적(2026-09-01, ①): dropdown 코어의 min-width:140px 는 트리거가 140px 보다 좁을 때
// 목록이 칩보다 옆으로 삐져나오게 만든다. 셀렉트는 트리거가 항상 140 이상(select.css 자체 min-width)이라
// 영향이 없고, 필터칩만 정본상 트리거가 AUTO(내용만큼 줄어듦)라 실제로 140 보다 좁아진다.
// dropdown.css 공통 규칙(140~320 클램프)은 그대로 두고, 이 인스턴스(필터칩이 소유한 dropdownRoot)에만
// 인라인 style 로 min/max-width 를 덮어써 "트리거 폭 < 140 → 목록 폭 = 트리거 폭"을 강제한다.
// 트리거 폭 >= 140 인 경우는 인라인 style 을 제거해 dropdown.css 의 기존 클램프(140~320, 내용에 맞춰 확장)로 되돌린다.


export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const { trigger, title, value, panel, dropdownRoot } = getParts(root);
  if (!trigger || !panel || !dropdownRoot) return null;

  if (!trigger.hasAttribute("aria-haspopup")) trigger.setAttribute("aria-haspopup", "listbox");
  if (!trigger.hasAttribute("aria-expanded")) trigger.setAttribute("aria-expanded", "false");
  panel.hidden = true;
  syncAccessibleName(trigger, title, value);

  const dropdownApi = initDropdown(dropdownRoot);

  // behavior 계약(component-behavior.pc.json "Filter Chip": on disable → close and block trigger clicks).
  // 클릭 차단은 open() 의 disabled 가드가 이미 담당한다 — 여기서는 열린 채로 비활성화될 때 자동으로 닫는다.
  // 인스턴스마다 자기 trigger 만 관찰하므로 누적되지 않고, destroy() 가 disconnect 한다.
  const disabledObserver = new MutationObserver(() => {
    if (trigger.disabled && isOpen(trigger)) close({ returnFocus: false });
  });
  disabledObserver.observe(trigger, { attributes: true, attributeFilter: ["disabled"] });

  const close = ({ returnFocus = true } = {}) => {
    if (!isOpen(trigger)) return;
    trigger.setAttribute("aria-expanded", "false");
    panel.hidden = true;
    document.removeEventListener("pointerdown", handleOutsidePointer, true);
    if (returnFocus) trigger.focus();
    root.dispatchEvent(new CustomEvent("s1:filter-chip:close", { bubbles: true, detail: {} }));
  };

  const open = () => {
    if (trigger.disabled || isOpen(trigger)) return;
    trigger.setAttribute("aria-expanded", "true");
    panel.hidden = false;
    document.addEventListener("pointerdown", handleOutsidePointer, true);
    dropdownApi?.focusActive();
    root.dispatchEvent(new CustomEvent("s1:filter-chip:open", { bubbles: true, detail: {} }));
  };

  const handleOutsidePointer = (event) => {
    if (!root.contains(event.target)) close({ returnFocus: false });
  };

  const handleTriggerClick = () => {
    if (isOpen(trigger)) close();
    else open();
  };

  // registry filter-chip.json a11y: "Esc 로 드롭다운을 닫을 수 있어야 한다." open() 이 포커스를 패널
  // 안(옵션)으로 옮기므로 트리거에만 걸면 열린 직후 Esc 가 먹지 않는다 — root 범위(트리거+패널) 전체에 건다.
  const handleRootKeydown = (event) => {
    if (event.key === "Escape" && isOpen(trigger)) {
      event.preventDefault();
      close();
    }
  };

  const handleDropdownChange = (event) => {
    if (event.detail?.type !== "text") return;
    if (value) {
      value.textContent = event.detail.option?.querySelector('[data-s1-part="option-label"]')?.textContent ?? event.detail.value ?? "";
    }
    trigger.dataset.complete = "true";
    syncAccessibleName(trigger, title, value);
    close();
    root.dispatchEvent(new CustomEvent("s1:filter-chip:change", { bubbles: true, detail: { value: event.detail.value, option: event.detail.option } }));
  };

  trigger.addEventListener("click", handleTriggerClick);
  root.addEventListener("keydown", handleRootKeydown);
  root.addEventListener("s1:dropdown:change", handleDropdownChange);

  const api = Object.freeze({
    get open() { return isOpen(trigger); },
    openPanel: open,
    closePanel: close,
    destroy() {
      trigger.removeEventListener("click", handleTriggerClick);
      root.removeEventListener("keydown", handleRootKeydown);
      root.removeEventListener("s1:dropdown:change", handleDropdownChange);
      document.removeEventListener("pointerdown", handleOutsidePointer, true);
      disabledObserver.disconnect();
      destroyDropdown(dropdownRoot);
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
