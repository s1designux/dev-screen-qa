"""S-1 디자인가이드 토큰 네 장을 화면 머리에 잇는다.

값(색·간격·모서리·글자크기)은 코드에 적지 않고 여기서 온 `var(--…)` 로만 쓴다.
파일은 `가이드받기.sh --내려두기 mvp0/assets/css` 로 받아 둔 것이다 — 손으로 고치지 않고 다시 받는다.

포털 화면은 `부품()`(브라우저가 /assets/css/ 로 받아 감) + `동작()`,
혼자 돌아다니는 출력물(반출한 결과서)은 `품기()`(파일 안에 넣기) 를 쓴다.
반출물은 포털이 꺼져 있어도 열려야 한다.

옛 `링크()`(손으로 옮겨 적은 `s1_components.CSS`) 는 2026-09-29 에 걷었다 — 모든 화면이
정본 부품을 그대로 입는다. `s1_components.py` 는 이력으로만 남긴다(부르는 곳 없음).
"""
from pathlib import Path

자리 = Path(__file__).resolve().parent / "assets" / "css"
차례 = ("tokens", "site-base", "component-tokens", "typography")


def 부품():
    """토큰 네 장 + **정본 부품 CSS 한 장**.

    부품 생김새를 우리가 다시 적지 않고 가이드가 배포한 것을 그대로 받는다.
    마크업에 `data-s1-component` 를 달아야 붙는다 — 뼈대는 `mvp0/s1.py` 가 짓는다.
    받아 두기: `bash scripts/부품받기.sh` (판은 파일 머리에 적힌다).
    """
    return ("".join("<link rel=stylesheet href='/assets/css/%s.css'>" % x for x in 차례)
            + "<link rel=stylesheet href='/assets/css/s1-ui.css'>")


def 동작():
    """정본 부품 **동작** 한 벌(ES 모듈). `부품()` 을 쓰는 화면은 이것도 함께 싣는다.

    입력칸 지우기·고르개 여닫기·대화창·탭·쪽번호 … 를 정본이 스스로 한다.
    받아 두기: `bash scripts/부품받기.sh` (손으로 고치지 않는다).
    """
    return '<script type="module" src="/assets/js/s1-form.js"></script>'


def 품기():
    """토큰 네 장 + 정본 부품 CSS 를 **문서 안에 넣는다**(반출물 전용).

    반출한 결과서는 포털이 꺼져 있어도 열려야 해서 이어 받지 못한다.
    내용은 받아 둔 정본 그대로다 — 여기서 고쳐 넣지 않는다.
    """
    글 = []
    for x in 차례 + ("s1-ui",):
        p = 자리 / ("%s.css" % x)
        if p.exists():
            글.append(p.read_text(encoding="utf-8"))
    # 품고 나가는 것은 가이드 CSS 원본 그대로다 — 토큰 점검기가 '우리가 적은 값' 으로 세지 않게 표시해 둔다
    # (점검기는 tokens.css 같은 낱장은 이름으로 건너뛰지만, 문서 안에 품은 사본은 알아보지 못한다).
    return ("<style>/* s1-제외 시작 — 아래는 S-1 가이드 CSS 원본 사본 */\n%s\n/* s1-제외 끝 */</style>"
            % "\n".join(글))
