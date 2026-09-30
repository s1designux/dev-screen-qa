/* 왼쪽 메뉴 맨 위 프로젝트 셀렉터 — 누르면 다른 프로젝트로 가는 쪽지가 열린다.
 *
 * 생김새는 정본 Select·Dropdown 부품이 전부 입히고, 여기서는 여닫기만 한다.
 * 정본 select.js 를 싣지 않는 이유: 그것은 값을 고르는 배선이고 여기 옵션은 가는 길이다.
 * 맨 위 줄 오른쪽 계정 쪽지(gnb-account.js)와 같은 방식이다.
 */
(function () {
  var 단추 = document.getElementById('lnb-project');
  var 쪽지 = document.getElementById('lnb-project-menu');
  if (!단추 || !쪽지) return;

  function 연다(열까) {
    쪽지.hidden = !열까;
    단추.setAttribute('aria-expanded', 열까 ? 'true' : 'false');
  }

  단추.addEventListener('click', function (e) {
    e.stopPropagation();
    연다(쪽지.hidden);
  });

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

/* 묶음 이름 — 두 번 누르면 고치는 칸이 열린다. Enter 로 보내고 Esc 로 접는다. */
(function () {
  var 글 = document.getElementById('gname-view');
  var 칸 = document.getElementById('gname-edit');
  if (!글 || !칸) return;
  var 입력 = 칸.querySelector('input');

  function 연다() {
    칸.hidden = false;
    글.hidden = true;
    입력.focus();
    입력.select();
  }

  function 접는다() {
    칸.hidden = true;
    글.hidden = false;
    입력.value = 글.textContent.trim();
  }

  글.addEventListener('dblclick', 연다);
  글.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); 연다(); }
  });
  입력.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { e.preventDefault(); 접는다(); 글.focus(); }
  });
  입력.addEventListener('blur', 접는다);
})();
