import { init as initDropdown, destroy as destroyDropdown } from "./dropdown.js";

export const componentId = "select";
export const jsRequired = true;

const instances = new WeakMap();

function getParts(root) {
  return {
    trigger: root.querySelector('[data-s1-part="trigger"]'),
    value: root.querySelector('[data-s1-part="value"]'),
    panel: root.querySelector('[data-s1-part="panel"]'),
    dropdownRoot: root.querySelector('[data-s1-component="dropdown"]')
  };
}

function isOpen(trigger) {
  return trigger.getAttribute("aria-expanded") === "true";
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const { trigger, value, panel, dropdownRoot } = getParts(root);
  if (!trigger || !panel || !dropdownRoot) return null;

  if (!trigger.hasAttribute("aria-haspopup")) trigger.setAttribute("aria-haspopup", "listbox");
  if (!trigger.hasAttribute("aria-expanded")) trigger.setAttribute("aria-expanded", "false");
  panel.hidden = true;

  const dropdownApi = initDropdown(dropdownRoot);

  // behavior 계약(component-behavior.pc.json "Select Box": on disable → close and block trigger clicks).
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
    root.dispatchEvent(new CustomEvent("s1:select:close", { bubbles: true, detail: {} }));
  };

  const open = () => {
    if (trigger.disabled || isOpen(trigger)) return;
    trigger.setAttribute("aria-expanded", "true");
    panel.hidden = false;
    document.addEventListener("pointerdown", handleOutsidePointer, true);
    dropdownApi?.focusActive();
    root.dispatchEvent(new CustomEvent("s1:select:open", { bubbles: true, detail: {} }));
  };

  const handleOutsidePointer = (event) => {
    if (!root.contains(event.target)) close({ returnFocus: false });
  };

  const handleTriggerClick = () => {
    if (isOpen(trigger)) close();
    else open();
  };

  // role=listbox 표준 패턴 — 열린 패널 어디에 포커스가 있어도(트리거·옵션 모두) Esc 로 닫고 트리거로 복귀한다.
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
    trigger.dataset.filled = "true";
    close();
    root.dispatchEvent(new CustomEvent("s1:select:change", { bubbles: true, detail: { value: event.detail.value, option: event.detail.option } }));
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
