"""S-1 디자인가이드 토큰 네 장을 화면 머리에 잇는다.

값(색·간격·모서리·글자크기)은 코드에 적지 않고 여기서 온 `var(--…)` 로만 쓴다.
파일은 `가이드받기.sh --내려두기 mvp0/assets/css` 로 받아 둔 것이다 — 손으로 고치지 않고 다시 받는다.

포털 화면은 `링크()`(브라우저가 /assets/css/ 로 받아 감), 혼자 돌아다니는 출력물(반출한 결과서)은
`품기()`(파일 안에 넣기) 를 쓴다. 반출물은 포털이 꺼져 있어도 열려야 한다.
"""
from pathlib import Path

import s1_components

자리 = Path(__file__).resolve().parent / "assets" / "css"
차례 = ("tokens", "site-base", "component-tokens", "typography")


def 링크():
    """토큰 네 장 + 컴포넌트(단추·표·탭) 한 장. 화면 CSS 보다 **앞에** 와야 한다."""
    return ("".join("<link rel=stylesheet href='/assets/css/%s.css'>" % x for x in 차례)
            + "<style>%s</style>" % s1_components.CSS)


def 품기():
    글 = []
    for x in 차례:
        p = 자리 / ("%s.css" % x)
        if p.exists():
            글.append(p.read_text(encoding="utf-8"))
    글.append(s1_components.CSS)
    return "<style>%s</style>" % "\n".join(글)
