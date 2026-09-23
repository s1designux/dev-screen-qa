/* S-1 Modal · Modal Content 동작.
 *
 * 생김새는 `assets/css/s1-ui.css`(정본 사본)가 전부 맡는다 — 여기서는 **동작만** 한다.
 * 가이드에 `status: verified` 로 적힌 것만 옮겼다(가이드 §4 Modal):
 *
 *   열기  : hidden 을 떼고 · 뒤 배경 스크롤을 잠그고 · 패널 안 첫 자리로 초점을 옮기고 · s1:modal:open
 *   닫기  : hidden 을 달고 · 스크롤을 풀고 · 열기 전 초점 자리로 되돌리고 · s1:modal:close
 *   닫기(X) 누름 = reason "close-button" · Escape = reason "escape"
 *   열려 있는 동안 Tab·Shift+Tab 은 패널 안에서만 돈다(초점 가둠)
 *
 * 여는 쪽은 `data-s1-modal-open="<모달 id>"` 를 단추에 달면 된다.
 */
(function () {
  "use strict";

  var 열린것 = [];          // 여럿이 겹칠 수 있다 — 마지막 하나가 닫힐 때 스크롤을 푼다
  var 옛초점 = new WeakMap();

  function 패널(뿌리) { return 뿌리.querySelector('[data-s1-part="panel"]'); }

  function 잡을수있는것(뿌리) {
    var 것 = 패널(뿌리).querySelectorAll(
      'a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),'
      + 'textarea:not(:disabled),[tabindex]:not([tabindex="-1"])');
    return Array.prototype.filter.call(것, function (x) {
      return x.offsetWidth || x.offsetHeight || x.getClientRects().length;
    });
  }

  function 열기(뿌리) {
    if (!뿌리.hidden) return;
    옛초점.set(뿌리, document.activeElement);
    뿌리.hidden = false;
    if (열린것.indexOf(뿌리) < 0) 열린것.push(뿌리);
    document.body.style.overflow = "hidden";
    var 첫 = 잡을수있는것(뿌리)[0];
    if (첫) 첫.focus();
    뿌리.dispatchEvent(new CustomEvent("s1:modal:open", { bubbles: true }));
  }

  function 닫기(뿌리, 까닭) {
    if (뿌리.hidden) return;
    뿌리.hidden = true;
    열린것 = 열린것.filter(function (x) { return x !== 뿌리; });
    if (!열린것.length) document.body.style.overflow = "";
    var 되돌릴곳 = 옛초점.get(뿌리);
    if (되돌릴곳 && 되돌릴곳.focus) 되돌릴곳.focus();
    뿌리.dispatchEvent(new CustomEvent("s1:modal:close", {
      bubbles: true, detail: { reason: 까닭 || "api" } }));
  }

  function 잇기(뿌리) {
    if (뿌리.dataset.s1Ready === "1") return;
    뿌리.dataset.s1Ready = "1";
    var 닫기단추 = 뿌리.querySelector('[data-s1-part="close"]');
    if (닫기단추) 닫기단추.addEventListener("click", function () {
      닫기(뿌리, "close-button");
    });
    뿌리.s1Modal = { open: function () { 열기(뿌리); },
                   close: function (까닭) { 닫기(뿌리, 까닭); } };
  }

  document.addEventListener("keydown", function (e) {
    var 위 = 열린것[열린것.length - 1];
    if (!위) return;
    if (e.key === "Escape" || e.key === "Esc") {
      e.preventDefault();
      닫기(위, "escape");
      return;
    }
    if (e.key !== "Tab") return;
    var 것 = 잡을수있는것(위);
    if (!것.length) return;
    var 처음 = 것[0], 끝 = 것[것.length - 1];
    if (e.shiftKey && (document.activeElement === 처음 || !패널(위).contains(document.activeElement))) {
      e.preventDefault(); 끝.focus();
    } else if (!e.shiftKey && (document.activeElement === 끝 || !패널(위).contains(document.activeElement))) {
      e.preventDefault(); 처음.focus();
    }
  }, true);

  document.addEventListener("click", function (e) {
    var 여는것 = e.target.closest && e.target.closest("[data-s1-modal-open]");
    if (!여는것) return;
    var 뿌리 = document.getElementById(여는것.getAttribute("data-s1-modal-open"));
    if (뿌리) { e.preventDefault(); 잇기(뿌리); 열기(뿌리); }
  });

  function 전부잇기() {
    Array.prototype.forEach.call(document.querySelectorAll(
      '[data-s1-component="modal"],[data-s1-component="modal-content"]'), 잇기);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", 전부잇기);
  else 전부잇기();

  window.S1Modal = { 잇기: 전부잇기, 열기: 열기, 닫기: 닫기 };
})();
