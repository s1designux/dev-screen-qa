/* 맨 위 메뉴 줄 오른쪽 끝 — 사람 아이콘을 누르면 계정 쪽지가 열린다.
 *
 * 정본(s1-ui)에는 이 배선이 없다. 정본 gnb.js 가 여닫는 것은 메뉴에 걸린 넓은 하위메뉴뿐이고,
 * 유틸 아이콘에 딸린 쪽지는 "유틸 영역 구성은 host 화면이 정한다"(gnb.manifest notInCanon)에 따라
 * 이 파일이 맡는다. 보이는 것은 전부 정본 Dropdown 부품이 입힌다 — 여기서는 여닫기만 한다.
 */
(function () {
  var 단추 = document.querySelector('[data-s1-component="gnb"] [data-s1-part="account"]');
  var 쪽지 = document.getElementById('gnb-account-menu');
  if (!단추 || !쪽지) return;

  function 연다(열까) {
    쪽지.hidden = !열까;
    단추.setAttribute('aria-expanded', 열까 ? 'true' : 'false');
  }

  단추.addEventListener('click', function (e) {
    e.stopPropagation();
    연다(쪽지.hidden);
  });

  // 밖을 누르면 닫는다. 쪽지 안을 누르는 것은 그 길로 가는 것이라 막지 않는다.
  document.addEventListener('click', function (e) {
    if (!쪽지.hidden && !쪽지.contains(e.target)) 연다(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !쪽지.hidden) {
      연다(false);
      단추.focus();
    }
  });
})();
