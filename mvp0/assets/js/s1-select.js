/* S-1 Select Box + Dropdown 동작.
 *
 * 생김새는 `assets/css/s1-ui.css`(정본 사본)가 전부 맡는다 — 여기서는 **동작만** 한다.
 * 가이드에 `status: verified` 로 적힌 것만 옮겼다(가이드 §4 Select Box · Dropdown):
 *
 *   Select  : 트리거 누름=열고 닫기(aria-expanded 맞춤) · 옵션 누름=고르고 닫기 ·
 *             Escape=닫고 트리거로 돌아감 · 바깥 누름=닫기 · 꺼두면 열리지 않음
 *   Dropdown: ↑↓ 옮기기 · Home/End 끝으로 · Enter/Space 고르기 ·
 *             고른 것만 탭 차례에 둔다(roving tabindex) · role=listbox / role=option
 *
 * 고른 값은 같은 상자 안 `input[type=hidden]` 에 담아 폼이 그대로 보낸다.
 * 값이 바뀌면 그 hidden 에 `change` 가 뜬다.
 */
(function () {
  "use strict";

  var 열린것 = null;

  function 옵션들(뿌리) {
    return Array.prototype.slice.call(
      뿌리.querySelectorAll('[data-s1-part="option"]'));
  }

  function 트리거(뿌리) { return 뿌리.querySelector('[data-s1-part="trigger"]'); }
  function 판(뿌리) { return 뿌리.querySelector('[data-s1-part="panel"]'); }
  function 값칸(뿌리) { return 뿌리.querySelector('input[type="hidden"]'); }

  /* 폭보다 긴 글자는 CSS 가 말줄임으로 자른다 — 잘린 것에만 마우스 올림 안내를 붙인다. */
  function 말줄임안내(뿌리) {
    옵션들(뿌리).forEach(function (칸) {
      var 글 = 칸.querySelector('[data-s1-part="option-label"]') || 칸;
      if (글.scrollWidth > 글.clientWidth + 1) 글.setAttribute("title", 글.textContent);
      else 글.removeAttribute("title");
    });
  }

  function 열기(뿌리) {
    if (열린것 && 열린것 !== 뿌리) 닫기(열린것, false);
    var t = 트리거(뿌리);
    if (t.disabled) return;
    판(뿌리).hidden = false;
    t.setAttribute("aria-expanded", "true");
    열린것 = 뿌리;
    말줄임안내(뿌리);
    var 고른 = 뿌리.querySelector('[data-s1-part="option"][aria-selected="true"]')
            || 옵션들(뿌리)[0];
    if (고른) 고른.focus();
  }

  function 닫기(뿌리, 돌아가기) {
    판(뿌리).hidden = true;
    트리거(뿌리).setAttribute("aria-expanded", "false");
    if (열린것 === 뿌리) 열린것 = null;
    if (돌아가기) 트리거(뿌리).focus();
  }

  function 고르기(뿌리, 칸) {
    옵션들(뿌리).forEach(function (x) {
      var 이것 = x === 칸;
      x.setAttribute("aria-selected", String(이것));
      x.tabIndex = 이것 ? 0 : -1;                    // 고른 것만 탭 차례에 둔다
    });
    var 글 = 칸.querySelector('[data-s1-part="option-label"]') || 칸;
    var t = 트리거(뿌리);
    t.querySelector('[data-s1-part="value"]').textContent = 글.textContent;
    t.dataset.filled = "true";
    var 칸값 = 값칸(뿌리);
    if (칸값 && 칸값.value !== (칸.dataset.value || "")) {
      칸값.value = 칸.dataset.value || "";
      칸값.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function 옮기기(뿌리, 지금, 어디) {
    var 목록 = 옵션들(뿌리);
    if (!목록.length) return;
    var i = 목록.indexOf(지금);
    var 다음 = 어디 === "home" ? 0
             : 어디 === "end" ? 목록.length - 1
             : 어디 === "up" ? (i <= 0 ? 목록.length - 1 : i - 1)
             : (i < 0 || i >= 목록.length - 1 ? 0 : i + 1);
    목록[다음].focus();
  }

  function 잇기(뿌리) {
    if (뿌리.dataset.s1Ready === "1") return;
    뿌리.dataset.s1Ready = "1";
    var t = 트리거(뿌리);

    t.addEventListener("click", function () {
      if (t.disabled) return;
      if (판(뿌리).hidden) 열기(뿌리); else 닫기(뿌리, true);
    });

    옵션들(뿌리).forEach(function (칸) {
      칸.addEventListener("click", function () {
        고르기(뿌리, 칸);
        닫기(뿌리, true);
      });
      칸.addEventListener("keydown", function (e) {
        // 예전 이름("Down"·"Up"·"Spacebar")으로 오는 브라우저도 있어 둘 다 받는다.
        var 키 = e.key;
        if (키 === "ArrowDown" || 키 === "Down") { e.preventDefault(); 옮기기(뿌리, 칸, "down"); }
        else if (키 === "ArrowUp" || 키 === "Up") { e.preventDefault(); 옮기기(뿌리, 칸, "up"); }
        else if (키 === "Home") { e.preventDefault(); 옮기기(뿌리, 칸, "home"); }
        else if (키 === "End") { e.preventDefault(); 옮기기(뿌리, 칸, "end"); }
        else if (키 === "Enter" || 키 === " " || 키 === "Spacebar") {
          e.preventDefault();
          고르기(뿌리, 칸);
          닫기(뿌리, true);
        }
      });
    });

    뿌리.addEventListener("keydown", function (e) {
      if ((e.key === "Escape" || e.key === "Esc") && !판(뿌리).hidden) {
        e.preventDefault();
        닫기(뿌리, true);
      }
    });
  }

  document.addEventListener("click", function (e) {
    if (열린것 && !열린것.contains(e.target)) 닫기(열린것, false);
  });

  function 전부잇기() {
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-s1-component="select"]'), 잇기);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", 전부잇기);
  else 전부잇기();

  window.S1Select = { 잇기: 전부잇기 };
})();
