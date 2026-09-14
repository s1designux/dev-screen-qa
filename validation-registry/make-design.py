"""시험용 시안 만들기 — measure-ok.json(토큰 안의 정답 화면 값)에서 촬영 준비 플러그인이 보내는 `검수요소` 모양을 만든다.

    python3 validation-registry/make-design.py    → design.json

진짜 피그마에서 읽은 것이 아니라 **정답 화면 값으로 지은 합성 시안**이다. 모양만 플러그인 출력과 같다.
버튼 두 개는 피그마 컴포넌트 **인스턴스**로 두어(`component` 칸) 시안 쪽 정체가 짝 건너 개발 요소로 옮겨지는 길을 시험한다.
"""
import json
import os
import re

여기 = os.path.dirname(os.path.abspath(__file__))


def 헥스(rgb):
    m = re.match(r"rgba?\((\d+), (\d+), (\d+)", rgb or "")
    return "#%02X%02X%02X" % tuple(int(x) for x in m.groups()) if m else None


def main():
    with open(os.path.join(여기, "measure-ok.json"), encoding="utf-8") as f:
        잰것 = json.load(f)
    요소 = []
    for i, e in enumerate(잰것["elements"]):
        st = e["style"]
        base = {"id": "1:%d" % (i + 1), "name": e["cls"] or e["role"].lower(), "type": "TEXT" if e["isText"] else "FRAME",
                "box": dict(e["box"]), "depth": 1, "parentId": None, "parentType": "FRAME"}
        if e["isText"]:
            base.update({"kind": "text", "text": e["text"],
                         "values": {"text": e["text"], "fontSize": st["fontSize"], "fontWeight": st["fontWeight"],
                                    "fontFamily": "Pretendard", "fontStyle": "", "lineHeight": "자동",
                                    "color": 헥스(st["color"]), "textAlign": "LEFT"}})
        else:
            base.update({"kind": "shape", "text": "",
                         "values": {"width": e["box"]["w"], "height": e["box"]["h"],
                                    "fill": 헥스(st["backgroundColor"]) if st["backgroundColor"] != "rgba(0, 0, 0, 0)" else None,
                                    "stroke": 헥스(st["borderColor"]) if st["borderWidth"] > 0 else None,
                                    "strokeWidth": st["borderWidth"], "radius": st["borderRadius"], "opacity": 1}})
        if e["cls"] == "primary-button":
            base["type"] = "INSTANCE"
            base["name"] = "Button"
            base["component"] = {"name": "Size=MD, State=Default, Variant=Primary, Break=PC", "set": "Button",
                                 "props": {"Size": "MD", "State": "Default", "Variant": "Primary", "Break": "PC"}}
        if e["cls"] == "secondary-button":
            base["type"] = "INSTANCE"
            base["name"] = "Button"
            base["component"] = {"name": "Size=MD, State=Default, Variant=Secondary, Break=PC", "set": "Button",
                                 "props": {"Size": "MD", "State": "Default", "Variant": "Secondary", "Break": "PC"}}
        요소.append(base)
        # 상자 안의 글자(버튼 라벨)는 플러그인이 따로 TEXT 로 보내므로 하나 더 만든다
        if not e["isText"] and e["text"] and e["cls"] in ("badge", "primary-button", "secondary-button"):
            요소.append({"id": "1:%d-t" % (i + 1), "name": "label", "type": "TEXT", "kind": "text", "text": e["text"],
                         "box": {"x": e["box"]["x"] + 12, "y": e["box"]["y"] + (e["box"]["h"] - 16) / 2, "w": e["box"]["w"] - 24, "h": 16},
                         "depth": 2, "parentId": base["id"], "parentType": base["type"],
                         "values": {"text": e["text"], "fontSize": st["fontSize"], "fontWeight": st["fontWeight"],
                                    "fontFamily": "Pretendard", "fontStyle": "", "lineHeight": "자동",
                                    "color": 헥스(st["color"]), "textAlign": "CENTER"}})
    꾸러미 = {"이름": "PC/DASH/1", "폭": 잰것["meta"]["artboardWidth"], "높이": 잰것["meta"]["artboardHeight"],
           "검수요소": 요소, "검수설정": None,
           "틀": {"폭": 잰것["meta"]["artboardWidth"], "높이": 잰것["meta"]["artboardHeight"]}}
    with open(os.path.join(여기, "design.json"), "w", encoding="utf-8") as f:
        json.dump(꾸러미, f, ensure_ascii=False, indent=2)
    print("design.json 요소 %d (인스턴스 %d)" % (len(요소), sum(1 for e in 요소 if e.get("component"))))


if __name__ == "__main__":
    main()
