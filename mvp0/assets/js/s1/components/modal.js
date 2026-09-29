export const componentId = "modal";
export const jsRequired = true;

const instances = new WeakMap();

// 초점을 받을 수 있는 요소. 모달 안에 들어오는 코어는 Button 과 닫기 버튼뿐이라 목록이 짧다.
const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])'
].join(",");

function focusables(panel) {
  return [...panel.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null || el === document.activeElement);
}

// 배경 스크롤 잠금은 열려 있는 모달 수를 세어 마지막 하나가 닫힐 때만 되돌린다.
const scrollLock = { count: 0, previous: "" };

function lockScroll() {
  if (scrollLock.count === 0) {
    scrollLock.previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  scrollLock.count += 1;
}

function unlockScroll() {
  scrollLock.count = Math.max(0, scrollLock.count - 1);
  if (scrollLock.count === 0) document.body.style.overflow = scrollLock.previous;
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const panel = root.querySelector('[data-s1-part="panel"]');
  if (!panel) return null;
  const closeButton = root.querySelector('[data-s1-part="close"]');

  let lastFocused = null;
  let locked = false;

  const isOpen = () => !root.hidden;

  const dispatch = (name, detail = {}) => {
    root.dispatchEvent(new CustomEvent(`s1:modal:${name}`, { bubbles: true, detail }));
  };

  const focusFirst = () => {
    const list = focusables(panel);
    (list[0] || panel).focus();
  };

  // 초점 가둠 — Tab 이 마지막에서 처음으로, Shift+Tab 이 처음에서 마지막으로 돈다.
  const trapFocus = (event) => {
    const list = focusables(panel);
    if (list.length === 0) { event.preventDefault(); panel.focus(); return; }
    const first = list[0];
    const last = list[list.length - 1];
    // 초점이 이미 패널 밖(또는 body)으로 빠져 있으면 방향에 맞는 끝으로 되돌린다.
    if (!panel.contains(document.activeElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
      return;
    }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const handleKeydown = (event) => {
    if (!isOpen()) return;
    if (event.key === "Escape") { event.preventDefault(); close({ reason: "escape" }); return; }
    if (event.key === "Tab") trapFocus(event);
  };

  // 초점이 다른 방법으로 모달 밖에 나가면(브라우저 주소창 복귀·프로그램 호출 등) 되돌린다.
  const handleFocusIn = (event) => {
    if (!isOpen()) return;
    if (!root.contains(event.target)) focusFirst();
  };

  /* 초점이 아무 요소도 아닌 곳(document.body)으로 빠지면 focusin 이 아예 오지 않는다.
     그 상태로 Tab 을 누르면 페이지 처음으로 새어 나가므로 여기서 되돌린다. */
  const handleFocusOut = (event) => {
    if (!isOpen()) return;
    if (event.relatedTarget && root.contains(event.relatedTarget)) return;
    queueMicrotask(() => {
      if (!isOpen()) return;
      if (!root.contains(document.activeElement)) focusFirst();
    });
  };

  const handleCloseClick = () => close({ reason: "close-button" });

  function open(detail = {}) {
    if (isOpen()) return;
    lastFocused = document.activeElement;
    root.hidden = false;
    if (!locked) { lockScroll(); locked = true; }
    document.addEventListener("keydown", handleKeydown, true);
    document.addEventListener("focusin", handleFocusIn, true);
    document.addEventListener("focusout", handleFocusOut, true);
    focusFirst();
    dispatch("open", detail);
  }

  function close(detail = {}) {
    if (!isOpen()) return;
    root.hidden = true;
    document.removeEventListener("keydown", handleKeydown, true);
    document.removeEventListener("focusin", handleFocusIn, true);
    document.removeEventListener("focusout", handleFocusOut, true);
    if (locked) { unlockScroll(); locked = false; }
    if (lastFocused && typeof lastFocused.focus === "function" && document.contains(lastFocused)) lastFocused.focus();
    lastFocused = null;
    dispatch("close", detail);
  }

  closeButton?.addEventListener("click", handleCloseClick);

  // 이미 열린 채로 마크업이 들어온 경우(검수 화면·정적 예시)도 계약대로 배선한다.
  if (isOpen()) {
    if (!locked) { lockScroll(); locked = true; }
    document.addEventListener("keydown", handleKeydown, true);
    document.addEventListener("focusin", handleFocusIn, true);
    document.addEventListener("focusout", handleFocusOut, true);
  }

  const api = Object.freeze({
    get isOpen() { return isOpen(); },
    open,
    close,
    destroy() {
      closeButton?.removeEventListener("click", handleCloseClick);
      document.removeEventListener("keydown", handleKeydown, true);
      document.removeEventListener("focusin", handleFocusIn, true);
      document.removeEventListener("focusout", handleFocusOut, true);
      if (locked) { unlockScroll(); locked = false; }
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
