export const componentId = "input";
export const jsRequired = true;

const instances = new WeakMap();

function refresh(root, control, clearAction, isSearch) {
  const editable = !control.disabled && !control.readOnly;
  /* Search 는 값이 있으면 초점 여부와 무관하게 지우기를 보인다("값 있음" 상태, river D4).
     Base·Password 는 기존 그대로 focus-within(Focus) 일 때만 보인다. */
  const show = isSearch
    ? editable && control.value.length > 0
    : editable && root.matches(":focus-within") && control.value.length > 0;
  clearAction.hidden = !show;
}

function refreshPassword(passwordAction, control) {
  const visible = control.type === "text";
  passwordAction.setAttribute("aria-pressed", String(visible));
  passwordAction.setAttribute("aria-label", visible ? "비밀번호 숨기기" : "비밀번호 보기");
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const control = root.querySelector('[data-s1-part="control"]');
  const clearAction = root.querySelector('[data-s1-part="action"][data-action="clear"]');
  if (!(control instanceof HTMLInputElement) || !(clearAction instanceof HTMLButtonElement)) return null;

  /* Password·Search 는 Input 의 옵션이다 — 액션이 마크업에 없으면 그 경로 자체가 없다. */
  const passwordAction = root.querySelector('[data-s1-part="action"][data-action="password"]');
  const searchAction = root.querySelector('[data-s1-part="action"][data-action="search"]');
  const isSearch = searchAction instanceof HTMLButtonElement;

  const update = () => refresh(root, control, clearAction, isSearch);

  /* 마우스·손가락으로 눌러 들어온 초점은 누른 자리에 커서를 둔다(드래그 선택도 그대로).
     키보드(Tab)로 들어온 초점만 값 끝으로 커서를 옮긴다. (river 지시 2026-09-04)

     판정은 "표식이 켜져 있나"가 아니라 "직전 포인터 조작이 방금이었나"로 한다.
     ① 표식이 켜진 채 굳는 경로가 없다(초점을 못 받는 자리를 눌러도 시간만 지나면 사라진다).
     ② 초점이 pointerdown 과 다른 task 에서 와도 된다 — 모바일은 손을 뗀 뒤 초점을 주는데,
        타이머로 표식을 지우면 그 탭이 '키보드'로 오인돼 글 중간을 눌러도 커서가 끝으로 튄다.
     ③ 화면이 숨겨져 타이머가 밀리는 환경에서도 판정이 흔들리지 않는다(같은 시계의 timeStamp 비교). */
  const POINTER_FOCUS_WINDOW_MS = 500;
  let lastPointerAt = -Infinity;
  const markPointer = (event) => { lastPointerAt = event.timeStamp; };
  const handleFocusIn = (event) => {
    const fromPointer = event.timeStamp - lastPointerAt < POINTER_FOCUS_WINDOW_MS;
    if (event.target === control && !fromPointer) {
      const end = control.value.length;
      if (end > 0) {
        try { control.setSelectionRange(end, end); } catch (_) { /* 캐럿을 못 옮기는 type 은 건너뛴다 */ }
      }
    }
    update();
  };
  const handleFocusOut = () => requestAnimationFrame(update);
  const handleClear = () => {
    control.value = "";
    control.dispatchEvent(new Event("input", { bubbles: true }));
    control.focus();
    update();
    root.dispatchEvent(new CustomEvent("s1:input:clear", { bubbles: true, detail: { value: "" } }));
  };

  /* Password — type 을 password↔text 로 바꾸고 Input 으로 초점을 되돌린다(river 결정). */
  const handlePasswordToggle = passwordAction instanceof HTMLButtonElement
    ? () => {
        control.type = control.type === "password" ? "text" : "password";
        refreshPassword(passwordAction, control);
        control.focus();
      }
    : null;

  /* Search — Enter 키와 돋보기 클릭 둘 다 같은 이벤트를 낸다(river D2).
     IME 조합 중(isComposing)의 Enter 는 문자 확정용이라 제외한다. */
  const dispatchSearch = () => {
    root.dispatchEvent(new CustomEvent("s1:input:search", { bubbles: true, detail: { value: control.value } }));
  };
  const handleSearchClick = isSearch ? () => dispatchSearch() : null;
  const handleSearchKeydown = isSearch
    ? (event) => { if (event.key === "Enter" && !event.isComposing) dispatchSearch(); }
    : null;

  control.addEventListener("input", update);
  root.addEventListener("pointerdown", markPointer);
  root.addEventListener("pointerup", markPointer);
  root.addEventListener("focusin", handleFocusIn);
  root.addEventListener("focusout", handleFocusOut);
  clearAction.addEventListener("click", handleClear);
  if (handlePasswordToggle) passwordAction.addEventListener("click", handlePasswordToggle);
  if (handleSearchClick) searchAction.addEventListener("click", handleSearchClick);
  if (handleSearchKeydown) control.addEventListener("keydown", handleSearchKeydown);

  const api = Object.freeze({
    destroy() {
      control.removeEventListener("input", update);
      root.removeEventListener("pointerdown", markPointer);
      root.removeEventListener("pointerup", markPointer);
      root.removeEventListener("focusin", handleFocusIn);
      root.removeEventListener("focusout", handleFocusOut);
      clearAction.removeEventListener("click", handleClear);
      if (handlePasswordToggle) passwordAction.removeEventListener("click", handlePasswordToggle);
      if (handleSearchClick) searchAction.removeEventListener("click", handleSearchClick);
      if (handleSearchKeydown) control.removeEventListener("keydown", handleSearchKeydown);
      clearAction.hidden = true;
      instances.delete(root);
    },
    update
  });
  instances.set(root, api);
  if (passwordAction instanceof HTMLButtonElement) refreshPassword(passwordAction, control);
  update();
  return api;
}

export function destroy(root) {
  instances.get(root)?.destroy();
}

export const runtime = Object.freeze({ init, destroy });
