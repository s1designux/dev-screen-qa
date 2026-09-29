/* 정본 부품과 우리 화면 사이를 잇는 얇은 배선 — 생김새도 동작도 여기서 만들지 않는다.
 *
 * 정본이 하지 않는 두 가지만 잇는다(gnb 선례 "구성은 host 가 정한다"):
 *   1) 고르개가 고른 값을 폼에 싣기 — 정본 Select 는 s1:select:change 만 쏘고 값은 host 가 담는다.
 *   2) 대화창을 여는 단추 — 정본 Modal 은 open()/close() 를 줄 뿐 여는 쪽을 배선하지 않는다.
 *
 * 동작 자체(여닫기·초점 가둠·키보드·지우개)는 전부 정본 모듈이 한다.
 * 받아 두기: bash scripts/부품받기.sh
 */
import { autoInit } from "/assets/js/s1/s1-ui.auto.js";
import * as 대화 from "/assets/js/s1/components/modal.js";
import * as 대화속 from "/assets/js/s1/components/modal-content.js";

/* 창은 두 갈래다 — 글만 담는 Modal 과 칸이 들어가는 Modal Content. 부를 때 갈라 준다. */
function 창잡기(뿌리) {
  if (!뿌리) return null;
  return 뿌리.dataset.s1Component === "modal-content"
    ? 대화속.init(뿌리) : 대화.init(뿌리);
}

function 고른값잇기(뿌리) {
  var 숨은칸 = 뿌리.querySelector('input[type="hidden"]');
  if (!숨은칸) return;
  뿌리.addEventListener("s1:select:change", function (e) {
    var 값 = (e.detail && e.detail.value) || "";
    if (숨은칸.value === 값) return;
    숨은칸.value = 값;
    숨은칸.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function 켜기(범위) {
  var 곳 = 범위 || document;
  autoInit(곳);
  /* 화면 쪽 onclick 이 `그 칸.s1Modal.close()` 로 부르던 길을 그대로 둔다. */
  Array.prototype.forEach.call(
    곳.querySelectorAll('[data-s1-component="modal"],[data-s1-component="modal-content"]'),
    function (뿌리) { 뿌리.s1Modal = 창잡기(뿌리); });
  Array.prototype.forEach.call(
    곳.querySelectorAll('[data-s1-component="select"]'), function (뿌리) {
      if (뿌리.dataset.s1Form === "1") return;
      뿌리.dataset.s1Form = "1";
      고른값잇기(뿌리);
    });
}

document.addEventListener("click", function (e) {
  var 여는것 = e.target.closest && e.target.closest("[data-s1-modal-open]");
  if (여는것) {
    var 뿌리 = document.getElementById(여는것.getAttribute("data-s1-modal-open"));
    if (뿌리) {
      e.preventDefault();
      var 창 = 창잡기(뿌리);
      if (창) 창.open();
    }
    return;
  }
  var 닫는것 = e.target.closest && e.target.closest("[data-s1-modal-close]");
  if (닫는것) {
    var 판 = 닫는것.closest('[data-s1-component="modal"],[data-s1-component="modal-content"]');
    if (판) {
      e.preventDefault();
      var 창 = 창잡기(판);
      if (창) 창.close();
    }
  }
});

if (document.readyState === "loading")
  document.addEventListener("DOMContentLoaded", function () { 켜기(); });
else 켜기();

/* 화면 쪽 JS 가 대화창을 채운 뒤 직접 열 때 쓴다 — 여는 단추가 값을 먼저 담아야 하는 자리. */
window.s1Modal = function (칸id) {
  var 뿌리 = typeof 칸id === "string" ? document.getElementById(칸id) : 칸id;
  return 창잡기(뿌리);
};

window.s1AutoInit = 켜기;
