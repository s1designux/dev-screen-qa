"""자가검사 — 같은 입력에 같은 답이 나오는지 매번 확인한다.

    python3 -m valueqa.selftest

쓰는 자료는 이미 저장소에 있는 것 그대로다(`validation-auto/`):
  · design-figma.json  — 예시 대시보드 시안 값
  · measure-dev.json   — 일부러 10군데 틀리게 만든 개발 화면을 잰 값

확인하는 것:
  1. 이름표 없이 짝 맞추기 17/17
  2. 심어둔 결함 6군데를 모두 후보로 올림
  3. 헛것 없음 — 구조 차이는 '추가된 배너' 하나만
  4. 위치만 다르면 참고(판정 아님) · 크기 다르면 판정 · 뱃지 교차 짝 · 원 모서리 동등
  5. 안쪽여백만 다른 것은 후보로 올리지 않음 (퍼블리싱 소관)
  6. 플러그인이 보낸 '검수요소'를 값 대조 모양으로 바꾸는 길
  7. 옛 엔진(plugin-value-qa/ui.html)과 셈이 똑같음 — 6·1·7·2·2
  8. 수정 지시서 — 어느 화면의 어느 항목인지가 번호·이름·자리로 나오고, 화면 여러 개도 한 문서로

7번이 어긋나면 둘 중 하나가 혼자 바뀐 것이다. `npm test` 로 저쪽 숫자를 다시 재고 맞춘다.
"""
import json
import os
import sys

from .candidates import 후보뽑기
from .compare import 값견주기
from .design import 시안값으로
from .fixdoc import 지시서, 지시서묶음
from .match import 짝맞추기

여기 = os.path.dirname(os.path.abspath(__file__))
자료 = os.path.normpath(os.path.join(여기, "..", "validation-auto"))

의도한짝 = {
    "app/header": "dev-1", "header/logo": "dev-2", "header/search": "dev-3", "header/avatar": "dev-4",
    "page/title": "dev-5", "stat/card-1": "dev-7", "stat/card-1/label": "dev-8", "stat/value-1": "dev-9",
    "stat/card-2": "dev-10", "stat/card-2/label": "dev-11", "stat/value-2": "dev-12",
    "stat/card-3": "dev-13", "stat/card-3/label": "dev-14", "stat/value-3": "dev-15",
    "content/map": "dev-16", "content/list": "dev-17", "action/export-btn": "dev-22",
}
심어둔결함 = ["action/export-btn", "page/title", "header/avatar", "stat/card-2", "header/search", "stat/value-3"]


def _요소(id="x", name="x", isText=False, text="", box=None, **style):
    s = {"color": "rgb(31, 41, 55)", "backgroundColor": "rgba(0, 0, 0, 0)", "fontSize": 16,
         "fontWeight": 400, "fontFamily": "", "lineHeight": 0, "borderRadius": 0, "borderWidth": 0,
         "borderColor": "rgb(0, 0, 0)", "paddingTop": 0, "paddingRight": 0, "paddingBottom": 0,
         "paddingLeft": 0, "textAlign": "start", "opacity": 1}
    s.update(style)
    return {"id": id, "name": name, "isText": isText, "text": text,
            "box": box or {"x": 0, "y": 0, "w": 100, "h": 40}, "style": s, "contentZone": False}


def main():
    실패 = []

    def 봄(이름, 참이냐):
        if not 참이냐:
            실패.append(이름)

    with open(os.path.join(자료, "design-figma.json"), encoding="utf-8") as f:
        시안 = json.load(f)
    with open(os.path.join(자료, "measure-dev.json"), encoding="utf-8") as f:
        개발 = json.load(f)

    # 1) 짝 맞추기
    M = 짝맞추기(시안, 개발)
    맞춘것 = {(M["fig"][p["fi"]].get("name") or M["fig"][p["fi"]].get("text")): M["devEls"][p["di"]]["id"]
             for p in M["pairs"]}
    맞음 = sum(1 for k, v in 의도한짝.items() if 맞춘것.get(k) == v)
    봄("짝 맞추기 %d/%d" % (맞음, len(의도한짝)), 맞음 == len(의도한짝))

    # 2·3) 후보
    결과 = 후보뽑기(시안, 개발)
    후보이름 = [c["이름"] for c in 결과["후보"] if c["갈래"] == "값다름"]
    for n in 심어둔결함:
        봄("결함 잡음: " + n, n in 후보이름)
    구조 = 결과["셈"]["더있음"] + 결과["셈"]["빠짐"]
    봄("구조 차이 == 1 (헛것 없음), 지금 %d" % 구조, 구조 == 1)

    # 4) 회귀 고정
    자리만 = 값견주기(_요소(box={"x": 10, "y": 100, "w": 100, "h": 40}, backgroundColor="rgb(255, 255, 255)"),
                  _요소(box={"x": 10, "y": 300, "w": 100, "h": 40}, backgroundColor="rgb(255, 255, 255)"))
    봄("위치만 다르면 참고", 자리만["status"] == "pass" and 자리만["hasDeferred"])
    크기 = 값견주기(_요소(box={"x": 10, "y": 100, "w": 100, "h": 40}, backgroundColor="rgb(255, 255, 255)"),
                 _요소(box={"x": 10, "y": 100, "w": 70, "h": 40}, backgroundColor="rgb(255, 255, 255)"))
    봄("크기 다르면 판정", 크기["status"] == "fail")
    뱃지 = 짝맞추기(
        {"meta": {"artboardWidth": 400, "artboardHeight": 400},
         "elements": [_요소(isText=True, text="완료", box={"x": 10, "y": 10, "w": 40, "h": 20})]},
        {"meta": {"artboardWidth": 400, "artboardHeight": 400},
         "elements": [_요소(id="dev-0", text="완료", box={"x": 11, "y": 10, "w": 40, "h": 20},
                          backgroundColor="rgb(220, 0, 0)")]})
    봄("뱃지 교차 짝 1쌍", len(뱃지["pairs"]) == 1)
    원 = 값견주기(_요소(box={"x": 0, "y": 0, "w": 40, "h": 40}, borderRadius=20, backgroundColor="rgb(200, 200, 200)"),
                _요소(box={"x": 0, "y": 0, "w": 40, "h": 40}, borderRadius=999, backgroundColor="rgb(200, 200, 200)"))
    봄("원 모서리 20↔999 같음", 원["status"] == "pass")

    # 5) 여백만 다른 것은 후보 아님 (퍼블리싱 소관)
    여백 = 값견주기(_요소(backgroundColor="rgb(255, 255, 255)", paddingLeft=16),
                 _요소(backgroundColor="rgb(255, 255, 255)", paddingLeft=4))
    봄("여백만 다르면 후보 아님", 여백["status"] == "pass")

    # 6) 플러그인이 보낸 '검수요소' → 값 대조 모양
    검수요소 = [
        {"id": "1:1", "name": "카드", "type": "FRAME", "kind": "shape", "text": "",
         "box": {"x": 0, "y": 0, "w": 200, "h": 80}, "parentId": None,
         "values": {"fill": "#FFFFFF", "stroke": "#E5E7EB", "strokeWidth": 1, "radius": 8, "opacity": 1}},
        {"id": "1:2", "name": "제목", "type": "TEXT", "kind": "text", "text": "오늘 방문",
         "box": {"x": 16, "y": 16, "w": 80, "h": 20}, "parentId": "1:1",
         "values": {"text": "오늘 방문", "fontSize": 14, "fontWeight": None, "fontFamily": "Pretendard",
                    "fontStyle": "Semi Bold", "color": "#1F2937", "textAlign": "LEFT", "lineHeight": "자동"}},
        {"id": "1:3", "name": "동그라미", "type": "ELLIPSE", "kind": "shape", "text": "",
         "box": {"x": 160, "y": 20, "w": 40, "h": 40}, "parentId": "1:1",
         "values": {"fill": "rgba(0, 0, 0, 0.2)", "stroke": None, "strokeWidth": 0, "radius": None, "opacity": 1}},
        {"id": "1:4", "name": "아이콘 조각", "type": "VECTOR", "kind": "icon", "text": "",
         "box": {"x": 10, "y": 50, "w": 12, "h": 12}, "parentId": "1:1",
         "values": {"fill": "#000000", "stroke": None, "strokeWidth": 0, "radius": None, "opacity": 1}},
        {"id": "1:5", "name": "빈 껍데기", "type": "GROUP", "kind": "shape", "text": "",
         "box": {"x": 0, "y": 0, "w": 200, "h": 80}, "parentId": "1:1",
         "values": {"fill": None, "stroke": None, "strokeWidth": 0, "radius": None, "opacity": 1}},
    ]
    바꾼것 = 시안값으로(검수요소, {"name": "카드", "width": 200, "height": 80})
    이름들 = [e["name"] for e in 바꾼것["elements"]]
    봄("아이콘 조각·빈 껍데기는 뺌", "아이콘 조각" not in 이름들 and "빈 껍데기" not in 이름들)
    카드 = next(e for e in 바꾼것["elements"] if e["name"] == "카드")
    제목 = next(e for e in 바꾼것["elements"] if e["name"] == "제목")
    동그라미 = next(e for e in 바꾼것["elements"] if e["name"] == "동그라미")
    봄("색 표기 바꿈(#FFFFFF → rgb)", 카드["style"]["backgroundColor"] == "rgb(255, 255, 255)")
    봄("테두리 옮김", 카드["style"]["borderWidth"] == 1 and 카드["style"]["borderColor"] == "rgb(229, 231, 235)")
    봄("상자에 속 글자 모음", 카드["text"] == "오늘 방문")
    봄("글자 굵기(Semi Bold → 600)", 제목["isText"] and 제목["style"]["fontWeight"] == 600)
    봄("글자색 바꿈", 제목["style"]["color"] == "rgb(31, 41, 55)")
    봄("원은 완전 둥금(반지름 = 한 변 절반)", 동그라미["style"]["borderRadius"] == 20)
    봄("반투명 칠도 rgb 로", 동그라미["style"]["backgroundColor"] == "rgb(0, 0, 0)")

    # 7) 옛 엔진과 셈이 같은지 (plugin-value-qa/ui.html · npm test 로 잰 값)
    옛엔진 = {"값다름": 6, "더있음": 1, "빠짐": 0, "밀림": 7, "주의": 2, "일치": 2}
    지금 = {k: 결과["셈"][k] for k in 옛엔진}
    봄("옛 엔진과 셈 같음 %s" % 지금, 지금 == 옛엔진)

    # 8) 수정 지시서 — 개발이 바로 반영할 수 있는 모양인지
    글 = 지시서(결과, 차수=1, 화면키="TB-WEB-001", 화면이름="관리자 대시보드",
              주소="https://example.local/admin")
    봄("지시서에 고칠 값이 CSS 이름으로 들어감", "background-color" in 글 and "font-size" in 글)
    봄("지시서에 고칠 자리(태그·class)가 들어감", "button.export-btn" in 글 and "div.value" in 글)
    봄("지시서에 여백 고치라는 줄은 없음", "padding-" not in 글)
    봄("지시서에 체크 목록이 있음", "- [ ] " in 글)
    봄("지시서 맨 앞에 쓰는 법이 있음",
      "## 이 문서 쓰는 법" in 글 and 글.index("이 문서 쓰는 법") < 글.index("고칠 항목"))
    # 어느 화면의 어느 항목인지 — 화면키·주소·항목 번호·화면 안 자리
    봄("지시서에 화면 이름·주소가 들어감", "관리자 대시보드" in 글 and "https://example.local/admin" in 글)
    봄("항목마다 번호가 붙음", "TB-WEB-001-01" in 글 and "TB-WEB-001-06" in 글)
    봄("항목에 화면 안 자리가 적힘", "위쪽 오른편" in 글)

    # 고칠 자리는 개발 화면 기준 — id → 측정 선택자 → 태그.class 차례
    from .candidates import _개발자리
    봄("id 가 있으면 id 로", _개발자리({"role": "BUTTON", "cls": "btn", "domId": "save"})["고르개"] == "#save")
    봄("측정 선택자가 있으면 그것으로",
      _개발자리({"role": "DIV", "cls": "card", "sel": "section.stats > div.card"})["고르개"]
      == "section.stats > div.card")
    봄("옛 측정값이면 태그.class 로 물러남",
      _개발자리({"role": "BUTTON", "cls": "export-btn"})["고르개"] == "button.export-btn")

    # 화면 여러 개를 한 문서로 — 화면이 달라도 같은 고침은 한꺼번에 묶인다
    묶음글 = 지시서묶음([(결과, {"화면키": "A-001", "화면이름": "첫 화면"}),
                    (결과, {"화면키": "B-002", "화면이름": "둘째 화면"})], 차수=1)
    봄("묶음에 화면 둘 다 나옴", "A-001-01" in 묶음글 and "B-002-01" in 묶음글)
    봄("묶음에 '한꺼번에 고칠 것' 이 생김", "한꺼번에 고칠 것" in 묶음글)
    봄("한꺼번에 칸에 두 화면 번호가 같이 적힘",
      "`A-001-01`" in 묶음글.split("## 2.")[0] and "`B-002-01`" in 묶음글.split("## 2.")[0])

    셈 = 결과["셈"]
    print("짝 %d/%d · 후보 %d(값다름 %d·더있음 %d·빠짐 %d) · 주의 %d · 일치 %d"
          % (맞음, len(의도한짝), 셈["후보"], 셈["값다름"], 셈["더있음"], 셈["빠짐"], 셈["주의"], 셈["일치"]))
    if 실패:
        print("\n어긋남: " + " | ".join(실패))
        return 1
    print("\n통과 — 이름표 없이 짝 %d/%d, 심어둔 결함 %d군데 다 잡음, 구조 차이 1(배너)만."
          % (맞음, len(의도한짝), len(심어둔결함)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
