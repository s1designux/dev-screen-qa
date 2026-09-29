/* Bottom Sheet 런타임 — modal.js 를 그대로 본뜬다(구조·초점 가둠·스크롤 잠금 카운터·이미 열린
   마크업 배선까지). modal.js 를 import 하지 않는다 — 개별 설치에서 끊긴다(3-build-spec.md A-4).
   modal 과 다른 점 한 가지: 딤(backdrop) 클릭으로도 닫는다 — 이미 배포된 date-picker 시트의 동작이며
   빼면 그 화면이 퇴행한다(2-canon-readiness.md D-4). */
export const componentId = "bottom-sheet";
export const jsRequired = true;

const instances = new WeakMap();

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

/* 배경 스크롤 잠금 — 열려 있는 **시트** 수를 세어 마지막 하나가 닫힐 때만 되돌린다.
   모달은 세지 않는다(셀 수 없다 — 별도 모듈이라 서로의 카운터가 안 보인다).

   ★ 그래서 잠그는 자리를 modal 과 **다른 요소**로 둔다: modal·modal-content 는 `body` 의
   인라인 overflow 를, 시트는 `html`(documentElement) 의 인라인 overflow 를 쓴다.
   두 모듈이 같은 자리를 저장·복원하면 겹쳐 열었을 때 서로의 저장값을 덮어써서
   ① 모달이 열려 있는데 배경이 풀리고 ② 다 닫았는데 페이지가 잠긴 채 남는다
   (2026-09-15 독립 검증에서 재현율 100% 로 잡힌 결함). 자리를 나누면 각자 자기 것만
   저장·복원하므로 여는 순서와 닫는 순서에 상관없이 "하나라도 열려 있으면 잠김"이 성립한다.
   html 에 overflow:hidden 을 걸어도 페이지 스크롤은 똑같이 잠긴다(실측 확인).

   한계(정직 표기): 이 분리는 modal 계열과의 충돌만 없앤다. 앞으로 또 다른 컴포넌트가
   html 인라인 overflow 를 쓰면 같은 문제가 생긴다 — 그때는 공용 잠금 장치를 따로 만든다. */
const scrollLock = { count: 0, previous: "" };
const scrollLockTarget = () => document.documentElement;

function lockScroll() {
  if (scrollLock.count === 0) {
    scrollLock.previous = scrollLockTarget().style.overflow;
    scrollLockTarget().style.overflow = "hidden";
  }
  scrollLock.count += 1;
}

function unlockScroll() {
  scrollLock.count = Math.max(0, scrollLock.count - 1);
  if (scrollLock.count === 0) scrollLockTarget().style.overflow = scrollLock.previous;
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const panel = root.querySelector('[data-s1-part="sheet-panel"]');
  if (!panel) return null;
  const closeButton = root.querySelector('[data-s1-part="sheet-close"]');
  const backdrop = root.querySelector('[data-s1-part="sheet-backdrop"]');

  let lastFocused = null;
  let locked = false;

  const isOpen = () => !root.hidden;

  const dispatch = (name, detail = {}) => {
    root.dispatchEvent(new CustomEvent(`s1:bottom-sheet:${name}`, { bubbles: true, detail }));
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

  const handleFocusIn = (event) => {
    if (!isOpen()) return;
    if (!root.contains(event.target)) focusFirst();
  };

  const handleFocusOut = (event) => {
    if (!isOpen()) return;
    if (event.relatedTarget && root.contains(event.relatedTarget)) return;
    queueMicrotask(() => {
      if (!isOpen()) return;
      if (!root.contains(document.activeElement)) focusFirst();
    });
  };

  const handleCloseClick = () => close({ reason: "close-button" });
  const handleBackdropClick = () => close({ reason: "backdrop" });

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
  backdrop?.addEventListener("click", handleBackdropClick);

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
      backdrop?.removeEventListener("click", handleBackdropClick);
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
