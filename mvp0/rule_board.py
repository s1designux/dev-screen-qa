"""지금 쓰는 검수 규칙 한 장 — 사람이 볼 수 있는 자리.

검수 규칙과 그 규칙을 지키는 채점은 그동안 장부 파일(`규칙장부/`)과 채점표(`시험지/`)에만
있어서, 도구를 돌리지 않으면 아무도 볼 수 없었다. 이 화면은 **읽기만 한다** —
여기서 규칙을 바꾸지 않는다.

GET /policy/쓰는규칙

보이는 것 셋:
 1. 지금 검수기로 잰 성적 한 줄 (시험 화면 수 · 볼 것 · 정답). 검수기가 바뀐 뒤 다시 재지
    않았으면 그 사실을 그대로 말한다 — 숫자를 지어내지 않는다.
 2. 사람이 정해 지금 쓰는 규칙 — 쉬운 말 한 줄 + **그 규칙이 죽으면 채점에 걸리나**.
 3. 검수기가 화면마다 읽는 규칙표(제외·가변·그림·촬영본) — 검수기 파일에서 그대로 읽어 온다.
"""
import gnb as gnb_bar
import hashlib
import json
import re
from html import escape as _e
from pathlib import Path

import policy_ui
import s1_tokens

뿌리 = Path(__file__).resolve().parents[1]
장부길 = 뿌리 / "규칙장부" / "규칙장부.jsonl"
측정장부길 = 뿌리 / "규칙장부" / "측정장부.jsonl"
양면방 = 뿌리 / "시험지" / "양면"
목록길 = 뿌리 / "시험지" / "목록.json"
엔진길 = 뿌리 / "engine" / "ui.html"

# 규칙마다 사람이 쓴 짧은 이름과 한 줄. 장부의 글은 만든 사람이 쓴 것이라 어려워서 여기 다시 쓴다.
# 새 규칙이 장부에 올라오고 여기 줄이 없으면 화면이 '쉬운 말 설명이 아직 없습니다'로 짚는다.
쉬운말 = {
    "P1": ("표 항목 이름", "표의 항목 이름이 달라지면 짚습니다", "짚음"),
    "P5": ("겹친 껍데기", "겉 상자가 이미 걸렸으면 안쪽은 넘깁니다", "넘김"),
    "P8": ("못 찾은 요소", "못 찾은 자리는 크기·색을 말하지 않습니다", "넘김"),
    "P9": ("구역 밀림", "이웃 구역과 좁은 범위 안에서만 견줍니다", "넘김"),
    "P10": ("탭 줄 구성", "열린 탭만 보이므로 탭 구성 차이는 넘깁니다", "넘김"),
    "P12": ("없어짐 후보", "자료가 드는 자리면 넘깁니다", "넘김"),
    "P13": ("사진 밖 자리", "개발 사진 바깥은 짚지 않습니다", "넘김"),
    "P15": ("그림으로 그린 창 틀", "시안에 그려 넣은 브라우저 틀·작업표시줄은 넘깁니다", "넘김"),
    "P16": ("선택된 탭", "탭 줄 안에서 찾아 글자만 맞춰 봅니다", "넘김"),
    "P17": ("칸 밖으로 긴 글자", "글자가 길어지거나 짧아진 것도 잽니다", "짚음"),
    "P21": ("반복 줄의 항목 이름", "되풀이되는 줄 안이라도 항목 이름은 짚습니다", "짚음"),
    "P22": ("입력칸 안 새 단추", "개발에만 생긴 작은 단추를 짚습니다", "짚음"),
    "P23": ("화면 위·아래 틀 띠", "틀에 걸린 부분까지만 넘겨 나머지는 짚습니다", "짚음"),
    "P24": ("키보드 도구 줄", "자판 위 도구 줄까지 함께 잘라냅니다", "넘김"),
}

규칙표들 = [
    ("POLICY_EXCLUDE_RULES", "검수 대상에서 빼는 것"),
    ("POLICY_TEXT_RULES", "자료라서 바뀔 수 있는 글자 / 정해진 글자"),
    ("POLICY_IMAGE_RULES", "그림 한 덩어리로 보는 것"),
    ("CAPTURE_EXCLUDE_RULES", "개발 사진에서 기기 몫으로 잘라내는 것"),
    ("POLICY_LIST_RULES", "후보 목록을 정리하는 것"),
]


def _줄들(길: Path):
    if not 길.exists():
        return []
    본 = []
    for 줄 in 길.read_text(encoding="utf-8").splitlines():
        줄 = 줄.strip()
        if not 줄:
            continue
        try:
            본.append(json.loads(줄))
        except json.JSONDecodeError:
            continue
    return 본


def 지문(길: Path) -> str:
    if not 길.exists():
        return ""
    h = hashlib.sha256()
    with open(길, "rb") as f:
        for 덩이 in iter(lambda: f.read(1 << 20), b""):
            h.update(덩이)
    return h.hexdigest()


def 지금성적() -> dict:
    """지금 검수기로 잰 **공식** 성적. 없으면 왜 없는지 말한다(숫자를 지어내지 않는다)."""
    엔진지문 = 지문(엔진길)
    잰것들 = [m for m in _줄들(측정장부길)
            if (m.get("엔진") or {}).get("지문") == 엔진지문
            and m.get("판정") == "잼" and m.get("자체검사") != "건너뜀"]
    화면수 = None
    if 목록길.exists():
        try:
            화면수 = len(json.loads(목록길.read_text(encoding="utf-8")).get("화면") or [])
        except json.JSONDecodeError:
            화면수 = None
    if not 잰것들:
        return {"있나": False, "화면수": 화면수,
                "말": "지금 검수기로 잰 성적이 없습니다 — 검수기가 바뀐 뒤 다시 재야 합니다."}
    끝 = 잰것들[-1]
    정답 = (끝.get("정답") or [[None, None, None]])[0]
    return {"있나": True, "측정번호": 끝.get("측정번호", ""), "잰때": 끝.get("잰때", ""),
            "볼것": 끝.get("볼것합계"), "화면수": 화면수,
            "정답이름": 정답[0], "정답산것": 정답[1], "정답전체": 정답[2],
            "자체검사": 끝.get("자체검사", ""), "이름": 끝.get("이름", "")}


def 규칙들() -> list:
    """장부에서 '지금 쓰는 규칙'만 골라 온다. 사건을 쌓아 마지막 결정을 본다."""
    사건 = {}
    순서 = []
    for e in _줄들(장부길):
        제안 = e.get("제안") or ""
        if 제안 not in 사건:
            사건[제안] = []
            순서.append(제안)
        사건[제안].append(e)

    확인 = {}
    if 양면방.exists():
        for p in sorted(양면방.glob("*.json")):
            try:
                확인[p.stem] = str(json.loads(p.read_text(encoding="utf-8"))
                                 .get("규칙 없는 판 확인") or "")
            except json.JSONDecodeError:
                확인[p.stem] = ""

    본 = []
    for 제안 in 순서:
        결정 = [e for e in 사건[제안] if e["사건"] in ("반영", "보류", "거절")]
        if not 결정 or 결정[-1]["사건"] != "반영":
            continue
        끝 = 결정[-1]
        있나 = 제안 in 확인
        값 = 확인.get(제안, "")
        if not 있나:
            지킴 = ("없음", "채점표 없음")
        elif 값[:1].isdigit():
            지킴 = ("좋음", "지켜짐")
        elif 값.startswith("안 됨"):
            지킴 = ("나쁨", "안 지켜짐")
        elif 값.startswith("해당 없음"):
            지킴 = ("없음", "가릴 규칙 없음")
        else:
            지킴 = ("모름", "확인 안 됨")
        이름, 한줄, 짚나 = 쉬운말.get(제안, ("", "", "짚음"))
        본.append({"제안": 제안, "정한날": (끝.get("때") or "")[:10],
                   "이름": 이름, "한줄": 한줄, "짚나": 짚나, "지킴": 지킴})
    return 본


def 검수기규칙표() -> list:
    """검수기 파일에 적힌 규칙표를 그대로 읽어 온다. 못 읽으면 못 읽었다고 말한다."""
    if not 엔진길.exists():
        return []
    줄들 = 엔진길.read_text(encoding="utf-8").splitlines()
    본 = []
    for 표이름, 설명 in 규칙표들:
        시작 = next((i for i, l in enumerate(줄들) if l.startswith(f"var {표이름}=")), None)
        if 시작 is None:
            본.append({"표": 표이름, "설명": 설명, "줄": None})
            continue
        끝 = 시작 + 1
        while 끝 < len(줄들) and not re.match(r"^(var |function )", 줄들[끝]):
            끝 += 1
        덩이 = "\n".join(줄들[시작:끝])
        규칙 = []
        for m in re.finditer(r'id:"([^"]+)"', 덩이):
            t = re.search(r'title:"([^"]*)"', 덩이[m.end():m.end() + 400])
            규칙.append({"id": m.group(1), "제목": t.group(1) if t else ""})
        본.append({"표": 표이름, "설명": 설명, "줄": 규칙})
    return 본


_칠 = {"좋음": "color:var(--color-status-success);font-weight:var(--font-weight-bold)",
      "나쁨": "color:var(--color-text-danger);font-weight:var(--font-weight-bold)",
      "없음": "color:var(--color-text-caption)",
      "모름": "color:var(--color-text-state-caution)"}
_표시 = {"좋음": "○", "나쁨": "✗", "없음": "—", "모름": "?"}


def page() -> str:
    성적 = 지금성적()
    규칙 = 규칙들()
    표 = 검수기규칙표()

    if not 장부길.exists():
        머리 = ('<p class="note">규칙 장부를 찾지 못했습니다. 이 화면은 저장소의 '
              '<b>규칙장부</b>·<b>시험지</b>를 읽습니다 — 둘이 없는 곳에서는 보여줄 것이 없습니다.</p>')
    elif 성적["있나"]:
        머리 = (f'<p class="sub">시험 화면 <b>{성적["화면수"]}장</b> · '
              f'볼 것 <b>{성적["볼것"]}건</b> · '
              f'정답 <b>{성적["정답산것"]}/{성적["정답전체"]}</b>'
              f'<span style="color:var(--color-text-helper)"> · {_e(성적["잰때"][:10])} 지금 검수기로 잼</span></p>')
    else:
        머리 = (f'<p class="note">{_e(성적["말"])}'
              + (f' 시험 화면은 {성적["화면수"]}장입니다.' if 성적["화면수"] else '') + '</p>')

    def 칸(r):
        빛, 말 = r["지킴"]
        이름 = (f'<b>{_e(r["이름"])}</b>' if r["이름"]
              else '<span style="color:var(--color-text-state-caution)">쉬운 말 설명 없음</span>')
        칠 = ('color:var(--color-action-primary-default)' if r["짚나"] == "짚음"
             else 'color:var(--color-text-caption)')
        return (f'<tr><td>{이름}<div class="help">{_e(r["한줄"])}</div></td>'
                f'<td style="{칠};white-space:nowrap">{"더 짚음" if r["짚나"] == "짚음" else "넘김"}</td>'
                f'<td style="{_칠[빛]};white-space:nowrap">{_표시[빛]} {_e(말)}</td>'
                f'<td class="help" style="white-space:nowrap">{_e(r["정한날"])}</td></tr>')

    머리줄 = '<tr><th>규칙</th><th>하는 일</th><th>채점</th><th>정한 날</th></tr>'
    짚는것 = [r for r in 규칙 if r["짚나"] == "짚음"]
    넘기는것 = [r for r in 규칙 if r["짚나"] == "넘김"]
    지킴수 = sum(1 for r in 규칙 if r["지킴"][0] == "좋음")
    없음수 = sum(1 for r in 규칙 if r["지킴"][1] == "채점표 없음")
    규칙칸 = (f'<h2>지금 쓰는 규칙 {len(규칙)}개</h2>'
            f'<p class="sub">더 짚는 규칙 {len(짚는것)}개 · 넘기는 규칙 {len(넘기는것)}개.<br>'
            f'<b>채점</b> — <span style="{_칠["좋음"]}">○ 지켜짐 {지킴수}개</span>'
            f'(규칙이 망가지면 채점에서 걸립니다) · '
            f'<span style="{_칠["없음"]}">— 채점표 없음 {없음수}개</span>(망가져도 조용히 넘어갑니다)</p>'
            f'<table>{머리줄}' + "".join(칸(r) for r in 짚는것 + 넘기는것) + '</table>'
            if 규칙 else '<h2>지금 쓰는 규칙</h2><p class="sub">장부에서 찾지 못했습니다.</p>')

    속 = ""
    for t in 표:
        if t["줄"] is None:
            속 += f'<p class="note">{_e(t["설명"])} — 검수기에서 그 표를 찾지 못했습니다.</p>'
            continue
        칸 = "".join('<tr><td>'
                    + (_e(x["제목"]) if x["제목"] else '<span style="color:var(--color-text-helper)">제목이 적혀 있지 않습니다</span>')
                    + '</td></tr>' for x in t["줄"])
        속 += (f'<h3 style="font-size:var(--font-size-14);margin:var(--spacing-20) 0 var(--spacing-6)">'
             f'{_e(t["설명"])} <span style="color:var(--color-text-helper);font-weight:normal">({len(t["줄"])}개)</span></h3>'
             f'<table>{칸 or "<tr><td>없습니다.</td></tr>"}</table>')
    표칸 = ('<h2>검수기가 화면마다 읽는 규칙표</h2>'
          '<p class="sub">화면을 볼 때마다 검수기가 읽는 표입니다. 켜고 끄는 값은 '
          '<a href="/policy">검수 규칙</a> 화면에서 정합니다.</p>'
          f'<details><summary style="cursor:pointer;color:var(--color-action-primary-default);font-size:var(--font-size-14)">'
          f'표를 펴서 보기</summary>{속}</details>')

    꼬리 = ('<p class="sub" style="margin-top:var(--spacing-28)">이 화면은 읽기만 합니다.</p>')
    몸 = (f'<h1>지금 쓰는 검수 규칙</h1>{머리}{규칙칸}{표칸}{꼬리}')
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>지금 쓰는 검수 규칙</title>{s1_tokens.링크()}'
            f'<style>{policy_ui.CSS}</style></head><body>{gnb_bar.바("policy")}<div class="wrap">'
            f'<a class="back" href="/policy">← 검수 규칙</a>{몸}</div></body></html>')


def get(handler, path) -> bool:
    if path not in ("/policy/쓰는규칙", "/policy/쓰는규칙/"):
        return False
    handler._html(page(), 200)
    return True
