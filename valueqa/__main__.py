"""값 대조 한 번 돌리기.

    python3 -m valueqa 시안.json 개발.값.json [-o 후보.json]

시안.json 은 두 가지 모양을 다 받는다:
  · 촬영 준비 플러그인이 보낸 검수요소 꾸러미  (자동으로 알아보고 바꿔 준다)
  · 이미 값 대조 모양인 것({meta, elements})
"""
import argparse
import json
import sys

from .candidates import 후보뽑기
from .design import 시안값으로


def 시안읽기(경로):
    with open(경로, encoding="utf-8") as f:
        d = json.load(f)
    if isinstance(d, dict) and isinstance(d.get("elements"), list) and d.get("meta", {}).get("artboardWidth"):
        return d                                   # 이미 값 대조 모양
    if isinstance(d, dict) and isinstance(d.get("검수요소"), list):
        return 시안값으로(d["검수요소"], d.get("틀") or d)
    if isinstance(d, dict) and isinstance(d.get("elements"), list):
        return 시안값으로(d["elements"], d)          # 프레임 꾸러미(elements + width/height)
    if isinstance(d, list):
        return 시안값으로(d)
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

    if a.내보내기:
        with open(a.내보내기, "w", encoding="utf-8") as f:
            json.dump(결과, f, ensure_ascii=False, indent=2)
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
                        화면키=a.화면키, 주소=a.주소))
        print("지시서: %s" % a.지시서)
    return 0


if __name__ == "__main__":
    sys.exit(main())
