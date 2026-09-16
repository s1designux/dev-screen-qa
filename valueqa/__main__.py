"""값 대조 한 번 돌리기.

    python3 -m valueqa 시안.json 개발.값.json [-o 후보.json]
    python3 -m valueqa 시안.json 개발.값.json --정본 auto --지시서 수정요청.md --디자이너 시안확인.md

`--정본 auto` 를 주면 회사 디자인 시스템 정본(깃허브)을 그때그때 받아와 토큰·컴포넌트 규정도 대조한다.
받아온 판(커밋)은 지시서 머리에 적힌다. 정본을 저장소 안에 복사해 두지 않는다.

시안.json 은 두 가지 모양을 다 받는다:
  · 촬영 준비 플러그인이 보낸 검수요소 꾸러미  (자동으로 알아보고 바꿔 준다)
  · 이미 값 대조 모양인 것({meta, elements})
"""
import argparse
import json
import os
import sys

from .candidates import 후보뽑기
from .design import 시안값으로


def 시안그림(경로):
    """시안 값 파일 옆에 나란히 놓인 시안 그림(.png). 없으면 None.

    '그림에 아무것도 안 그려지는 껍데기'를 가려내는 데 쓴다(valueqa/design.py 안그려진것).
    """
    for 끝 in (".png", ".PNG"):
        길 = os.path.splitext(경로)[0] + 끝
        if os.path.exists(길):
            return 길
    return None


def 시안읽기(경로, 그림=None):
    with open(경로, encoding="utf-8") as f:
        d = json.load(f)
    그림 = 그림 or 시안그림(경로)
    if isinstance(d, dict) and isinstance(d.get("elements"), list) and d.get("meta", {}).get("artboardWidth"):
        return d                                   # 이미 값 대조 모양
    if isinstance(d, dict) and isinstance(d.get("검수요소"), list):
        return 시안값으로(d["검수요소"], d.get("틀") or d, 그림)
    if isinstance(d, dict) and isinstance(d.get("요소"), list):
        return 시안값으로(d["요소"], d.get("틀") or d, 그림)   # 촬영 준비 사이트가 갈무리해 둔 판(요소/틀)
    if isinstance(d, dict) and isinstance(d.get("elements"), list):
        return 시안값으로(d["elements"], d, 그림)    # 프레임 꾸러미(elements + width/height)
    if isinstance(d, list):
        return 시안값으로(d, None, 그림)
    raise SystemExit("시안 파일 모양을 알아볼 수 없습니다: %s" % 경로)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="valueqa", description="시안 값 ↔ 개발 값을 맞춰 다른 곳을 후보로 뽑는다")
    ap.add_argument("시안")
    ap.add_argument("개발")
    ap.add_argument("-o", "--내보내기", help="후보를 JSON 파일로 저장")
    ap.add_argument("--보기", help="눈으로 볼 한 장(HTML)으로 저장")
    ap.add_argument("--지시서", help="퍼블리싱·개발에 넘길 수정 요청(Markdown)으로 저장")
    ap.add_argument("--차수", type=int, help="지시서에 적을 검수 차수")
    ap.add_argument("--화면키", help="지시서 항목 번호에 쓸 화면 사람키 (예: CV-WEB-012)")
    ap.add_argument("--화면이름", help="지시서에 적을 화면 이름")
    ap.add_argument("--주소", help="지시서에 적을 개발 화면 주소")
    ap.add_argument("--문턱", type=float, default=0.5, help="짝으로 인정하는 점수 (기본 0.5)")
    ap.add_argument("--정본", help="회사 토큰·컴포넌트 규정도 대조. 'auto' 면 깃허브에서 받아오고, 폴더 경로면 그것을 읽는다")
    ap.add_argument("--대응표", help="프로젝트 대응표 JSON — {\"Button\": [\"btn-primary\"]} (컴포넌트 ↔ 이 프로젝트의 클래스 접두사)")
    ap.add_argument("--플랫폼", default="PC", help="컴포넌트 규격을 볼 때 PC / Mobile (기본 PC)")
    ap.add_argument("--디자이너", help="시안 자체가 규정 밖인 곳을 디자이너용 목록(Markdown)으로 저장 (--정본 필요)")
    a = ap.parse_args(argv)

    시안 = 시안읽기(a.시안)
    with open(a.개발, encoding="utf-8") as f:
        개발 = json.load(f)

    결과 = 후보뽑기(시안, 개발, a.문턱)
    셈 = 결과["셈"]
    print("짝 %d / 시안 %d · 개발 %d" % (셈["짝"], 셈["시안요소"], 셈["개발요소"]))
    print("후보 %d (값다름 %d · 더있음 %d · 빠짐 %d) · 주의 %d · 밀림 %d · 일치 %d"
          % (셈["후보"], 셈["값다름"], 셈["더있음"], 셈["빠짐"], 셈["주의"], 셈["밀림"], 셈["일치"]))
    for c in 결과["후보"]:
        다른곳 = ", ".join("%s %s→%s" % (x["속성"], x["시안"], x["개발"]) for x in c["다른곳"])
        print("  [%s] %s (믿음 %.2f) — %s" % (c["갈래"], c["이름"], c["신뢰도"], 다른곳))

    규정 = None
    if a.정본:
        from .registry import 정본가져오기, 토큰셈
        from .rules import 규정검사
        정본 = 정본가져오기(a.정본)
        대응표 = None
        if a.대응표:
            with open(a.대응표, encoding="utf-8") as f:
                대응표 = json.load(f)
        규정 = 규정검사(결과, 정본, 대응표, 0, a.플랫폼)   # 규정은 정확히 같아야 한다 (river 2026-09-14) — 허용차 없음
        n = 토큰셈(정본)
        print("정본 %s — 색 %d · 간격 %d · 크기 %d · 모서리 %d · 글자크기 %d · 컴포넌트 %d"
              % (정본.get("커밋") or "로컬", n["색"], n["간격"], n["크기"], n["모서리"], n["글자크기"], n["컴포넌트"]))
        s = 규정["셈"]
        print("규정: 토큰 밖 %d가지(%d곳) · 컴포넌트 규격 %d · 시안 규정 밖 %d · 알아본 컴포넌트 %d / 못 알아봄 %d"
              % (s["토큰밖"], s["토큰밖자리"], s["규격"], s["시안규정"], s["알아봄"], s["못알아봄"]))
        for c in 규정["토큰밖"]:
            t = c["가까운토큰"]
            print("  [토큰밖] %s %s → %s (%s, 차이 %s) · %d곳" % (c["css"], c["지금"], t["이름"], t["값"], t["차이"], len(c["곳"])))
        for c in 규정["규격"]:
            print("  [규격] %s (%s, 믿음 %.1f) — %s" % (c["규격"], c["길"], c["신뢰도"], "; ".join(r["말"] for r in c["줄"])))

    if a.내보내기:
        내보낼 = {k: v for k, v in 결과.items() if not k.startswith("_")}
        if 규정:
            내보낼["규정"] = {k: v for k, v in 규정.items()}
        with open(a.내보내기, "w", encoding="utf-8") as f:
            json.dump(내보낼, f, ensure_ascii=False, indent=2, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        print("저장: %s" % a.내보내기)

    if a.보기:
        from .report_html import 한장
        이름 = 시안["meta"].get("frameName") or 개발.get("meta", {}).get("label") or "값 대조"
        with open(a.보기, "w", encoding="utf-8") as f:
            f.write(한장(결과, "값 대조 — %s" % 이름))
        print("한 장: %s" % a.보기)

    if a.지시서:
        from .fixdoc import 지시서
        with open(a.지시서, "w", encoding="utf-8") as f:
            f.write(지시서(결과, 화면이름=a.화면이름 or "", 차수=a.차수,
                        화면키=a.화면키, 주소=a.주소, 규정=규정))
        print("지시서: %s" % a.지시서)

    if a.디자이너:
        if not 규정:
            raise SystemExit("--디자이너 는 --정본 과 함께 써야 합니다")
        from .fixdoc import 디자이너목록
        with open(a.디자이너, "w", encoding="utf-8") as f:
            f.write(디자이너목록(규정, 화면이름=a.화면이름 or "", 화면키=a.화면키))
        print("디자이너 목록: %s" % a.디자이너)
    return 0


if __name__ == "__main__":
    sys.exit(main())
