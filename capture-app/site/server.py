"""촬영 준비 사이트 — 네 걸음으로 앱 개발화면을 찍는다.

  ① 디자인 고르기 → ② 찍을 목록 초안 → ③ 조건 확인 → ④ 전체 촬영

파이썬 표준 http.server만 쓴다(추가 설치 0). 기본은 내 PC에서만 뜨고,
QA_CAPTURE_BIND=0.0.0.0 이면 같은 사무실 네트워크의 동료도 들어올 수 있다.
찍는 일 자체는 기존 lib/runner.py 가 그대로 한다 — 이 사이트는 그 앞의 준비만 맡는다.

실행: ./site.sh   →  http://127.0.0.1:8767
"""
import html
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, quote

여기 = Path(__file__).resolve().parent
뿌리 = 여기.parent
sys.path.insert(0, str(여기))
sys.path.insert(0, str(뿌리 / "lib"))

import design_source as 디자인
import actions as 동작말
import appbook as 앱사전
import 동작점검
import 동작규칙
import 시안요소
import draft as 초안만들기
import 주소기억
import 메뉴훑기
import intake as 접수하기
import nametag
import 계정확인
import 매체

작업파일 = 여기 / "작업.json"

sys.path.insert(0, str(뿌리.parent))
import 설정 as 설정                     # 이 컴퓨터에서만 쓰는 값 (설정.json → 환경변수 → 기본값)

PORT = 설정.값("촬영준비.포트")
# 기본은 내 PC에서만. 설정.json 의 촬영준비.받는자리 를 0.0.0.0 으로 하면 같은 망의 동료도 들어올 수 있다.
BIND = 설정.값("촬영준비.받는자리")
공유중 = BIND in ("0.0.0.0", "")
ADB = str(설정.자리("촬영준비.adb") or "")

_촬영 = {"진행중": False, "폴더": None, "로그": None}


# ────────────────────────────────────────────────── 작업 상태(한 번에 하나)
def 작업읽기():
    if 작업파일.exists():
        try:
            return json.loads(작업파일.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def 작업쓰기(d):
    작업파일.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


유형이름 = {"web": "PC 웹", "mobile-web": "모바일 웹", "android": "앱", "pcapp": "PC S/W"}
유형코드 = {"web": "WEB", "mobile-web": "WEB", "android": "AND", "pcapp": "APP"}

# 서비스 코드를 짐작할 때 뜻이 없는 말 — 주소·꾸러미 이름에 흔히 끼어 있다.
흔한말 = {"www", "dev", "develop", "test", "stage", "staging", "qa", "m", "mobile",
       "web", "portal", "admin", "app", "apps", "site", "front", "new",
       "com", "co", "kr", "net", "org", "io", "go", "or", "local", "localhost"}


def 서비스코드제안(작업):
    """화면 이름 앞에 붙을 코드를 짐작해 준다 — {서비스}-{유형}-{번호} (CLAUDE.md 7번).
    제안일 뿐이라 사람이 칸에서 그냥 고쳐 쓴다. 유형(웹·앱)에 상관없이 같은 차례로 본다."""
    적힌것 = (작업.get("서비스코드") or "").strip()
    if 적힌것:
        return 적힌것.upper()
    이름 = 작업.get("앱이름", "") or ""
    기억 = (앱사전.읽기().get(이름) or {}).get("서비스코드")      # ① 전에 사람이 정해 둔 것
    if 기억:
        return 기억.strip().upper()
    for 낱말 in re.findall(r"[A-Za-z][A-Za-z0-9-]*", 이름):        # ② 이름에 섞인 영문
        if 낱말.lower() not in 흔한말:
            return re.sub(r"[^A-Za-z0-9]", "", 낱말).upper()
    조각 = (urlparse(작업.get("기본주소", "")).hostname or "").split(".") if 웹인가(작업) \
        else (작업.get("앱주소", "") or "").split(".")             # ③ 주소·꾸러미 이름
    쓸것 = [c for c in 조각 if c and c.lower() not in 흔한말]
    return re.sub(r"[^A-Za-z0-9]", "", 쓸것[-1]).upper() if 쓸것 else ""


def 유형(작업=None):
    """플러그인에서 사람이 고른 네 가지 중 하나. 옛 작업 파일은 앱으로 본다."""
    return (작업 if 작업 is not None else 작업읽기()).get("유형") or "android"


def 웹인가(작업=None):
    """웹 둘(PC 웹·모바일 웹)은 브라우저 하나로 같은 길을 간다. (유형표: lib/매체.py)"""
    return 매체.웹인가(유형(작업))


def 찍는중안내(작업=None):
    """찍는 동안 사람이 하지 말아야 할 것 — 유형표(lib/매체.py)가 정한다."""
    return 매체.찍는중안내(유형(작업))


def _e(v):
    return html.escape(str(v if v is not None else ""))


# ────────────────────────────────────────────────── 겉모습
# ── S-1 디자인가이드 토큰 ────────────────────────────────
# 값을 코드에 베껴 적지 않는다 — 가이드는 계속 바뀐다. 받아 둔 CSS 를 그대로 읽어 화면 앞에 붙인다.
#   새로 받기: bash ~/.claude/skills/s1-design/scripts/가이드받기.sh --내려두기 capture-app/site/assets/css
토큰자리 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "css")


def 토큰CSS():
    묶음 = []
    for 이름 in ("tokens.css", "component-tokens.css", "typography.css", "site-base.css"):
        길 = os.path.join(토큰자리, 이름)
        if os.path.exists(길):
            묶음.append(open(길, encoding="utf-8").read())
    return "\n".join(묶음)


토큰 = 토큰CSS()


CSS = """
/* 색·크기·굵기·모서리는 S-1 디자인가이드 토큰만 쓴다. 값을 여기에 베껴 적지 않는다.
   토큰 CSS 는 assets/css/ 에서 그대로 읽어 온다(위 토큰CSS()).
   새로 받기: bash ~/.claude/skills/s1-design/scripts/가이드받기.sh --내려두기 capture-app/site/assets/css */
:root {
  /* 이 사이트에서만 쓰는 별명 — 값이 아니라 가이드 토큰을 가리킨다 */
  --form-bg:            var(--color-form-control-bg-default);
  --form-border:        var(--color-form-control-border-default);
  --form-text:          var(--color-form-control-text-default);
  --form-placeholder:   var(--color-form-control-text-placeholder);
  --form-bg-readonly:   var(--color-bg-level-2);
  --form-text-readonly: var(--color-form-control-text-read-only);
}
* { box-sizing:border-box; }
body { font-family:Pretendard,-apple-system,"Apple SD Gothic Neo",sans-serif;
  color:var(--color-text-primary); margin:0; background:var(--color-bg-level-1);
  font-size:var(--font-size-14); }
header { background:var(--color-surface-default); border-bottom:1px solid var(--color-border-subtle);
  padding:var(--spacing-16) var(--spacing-28); }
h1 { font-size:var(--font-size-18); margin:0; }
.sub { font-size:var(--font-size-12); color:var(--color-text-body-tertiary); margin-top:var(--spacing-4); }
.wrap { max-width:1040px; margin:0 auto; padding:var(--spacing-20) var(--spacing-28) var(--spacing-64); }
.wrap.w2 { max-width:1320px; }   /* 칸이 많은 '찍을 목록' 쪽만 넓게 */
/* 걸음 표시 — S-1 Chip(Solid). 지금 걸음만 고른 것(selected), 나머지는 고르지 않은 것(default).
   지나온 걸음도 '다 됨'으로 따로 칠하지 않는다 — 칩에 그런 상태가 없다. */
.steps { display:flex; gap:var(--spacing-8); margin:var(--spacing-16) 0 var(--spacing-20); flex-wrap:wrap; }
.steps a, .steps span { display:inline-flex; align-items:center; gap:var(--spacing-4);
  height:var(--sizing-34); padding:0 var(--spacing-16); border-radius:var(--radius-full);
  border:var(--border-width-default) solid var(--chip-line-default-border);
  background:var(--chip-line-default-bg); color:var(--chip-line-default-text);
  font-size:var(--font-size-14); font-weight:var(--font-weight-medium); line-height:1;
  text-decoration:none; white-space:nowrap; }
.steps a:hover { background:var(--chip-line-hover-bg); border-color:var(--chip-line-hover-border); }
.steps .on { background:var(--chip-line-selected-bg); border-color:var(--chip-line-selected-border);
  color:var(--chip-line-selected-text); }
.card { background:var(--color-surface-default); border:1px solid var(--color-border-subtle);
  border-radius:var(--radius-12); padding:var(--spacing-20); margin-bottom:var(--spacing-16); }
.card h2 { font-size:var(--font-size-14); margin:0 0 var(--spacing-12); }
label.f { display:block; font-size:var(--font-size-12); color:var(--color-form-control-label-default);
  margin:var(--spacing-10) 0 var(--spacing-4); }
/* 입력칸·셀렉트·단추는 같은 크기 단계를 쓴다 — S-1 MD(PC) 44, 작은 칸(.s)은 XSM 34.
   높이를 값으로 잡으므로 위아래 여백은 0 이다(가운데 정렬은 칸이 알아서 한다). */
input[type=text], input[type=password], select { width:100%; max-width:420px;
  height:44px; padding:0 var(--spacing-12) 0 var(--spacing-16);
  font-size:var(--font-size-14); color:var(--form-text); border:1px solid var(--form-border);
  border-radius:var(--radius-control-sm); font-family:inherit; background:var(--form-bg); }
input::placeholder { color:var(--form-placeholder); }
input[type=text]:focus, input[type=password]:focus, select:focus {
  outline:none; border-color:var(--color-border-focus); box-shadow:0 0 0 2px var(--color-blue-50); }
input[readonly] { background:var(--form-bg-readonly); color:var(--form-text-readonly);
  border-color:var(--color-border-default); }
input[disabled] { background:var(--color-form-control-bg-disabled); color:var(--color-text-disabled);
  border-color:var(--color-form-control-border-disabled); }
/* 인풋 안내메시지(helper) — S-1 Input 의 선택 슬롯. 칸 아래 한 줄로 붙고,
   기본/오류/확인 세 가지 색은 input-* 컴포넌트 토큰이 정한다(확인은 파랑, 초록 아님). */
input[type=text].is-error, input[type=password].is-error { border-color:var(--color-form-control-border-error); }
input[type=text].is-correct, input[type=password].is-correct { border-color:var(--color-form-control-border-correct); }
.helper { font-size:var(--font-size-12); line-height:1.6; margin-top:var(--spacing-6);
  color:var(--input-helper-text); }
.helper.is-error { color:var(--input-error-text); }
.helper.is-correct { color:var(--input-correct-text); }
input.w-xs { max-width:110px; } input.w-sm { max-width:200px; }
input.w-md { max-width:300px; } input.w-lg { max-width:380px; }
input.s { height:34px; padding:0 var(--spacing-8) 0 var(--spacing-12); font-size:var(--font-size-14); }
/* 찍을 목록 — '동작'은 문장이라 한 줄 칸에 가두면 앞부분만 보인다.
   여러 줄로 풀어 쓰는 칸으로 두고, 적은 만큼 칸이 자란다. */
textarea.s { width:100%; box-sizing:border-box; padding:var(--spacing-6) var(--spacing-8);
  font-size:var(--font-size-14); line-height:1.55;
  color:var(--form-text); font-family:inherit; border:1px solid var(--form-border);
  border-radius:var(--radius-control-sm); background:var(--form-bg); resize:vertical;
  overflow:hidden; min-height:34px; }
textarea.s:focus { outline:none; border-color:var(--color-border-focus); box-shadow:0 0 0 2px var(--color-blue-50); }
textarea.s::placeholder { color:var(--form-placeholder); }
table.list td { vertical-align:top; }
table.list input.s { width:100%; max-width:none; box-sizing:border-box; }
/* 비밀번호 칸 — 눈 아이콘을 칸 안 오른쪽에 둔다(S-1 Input · Password 정본).
   숨김 중에는 eye_hide, 보이는 중에는 eye_show. 아이콘 색은 어느 상태에서나 하나다. */
.pw { position:relative; display:inline-block; width:100%; max-width:300px; }
.pw input[type=text], .pw input[type=password] { max-width:none; padding-right:var(--spacing-40); }
.pw .eye { position:absolute; top:50%; right:6px; transform:translateY(-50%);
  width:28px; height:28px; min-width:0; padding:var(--spacing-2); border:0; background:none;
  border-radius:var(--radius-control-sm);
  color:var(--color-form-control-icon-default); display:flex; align-items:center; justify-content:center; cursor:pointer; }
.pw .eye:hover { background:var(--color-bg-level-2); }
.pw .eye svg { display:block; width:24px; height:24px; fill:currentColor; }
.pw .eye .show { display:none; }
.pw .eye[aria-pressed="true"] .show { display:block; }
.pw .eye[aria-pressed="true"] .hide { display:none; }
/* 단추 — S-1 Button (Secondary 기본 · 주요 액션은 Primary) */
button, .btn { font-size:var(--font-size-14); height:44px; min-width:80px;
  padding:0 var(--spacing-16);
  border-radius:var(--radius-button-md); border:1px solid var(--button-secondary-default-border);
  background:var(--button-secondary-default-bg); color:var(--button-secondary-default-text);
  cursor:pointer; text-decoration:none; font-family:inherit;
  display:inline-flex; align-items:center; justify-content:center; }
button:hover, .btn:hover { background:var(--button-secondary-hover-bg); }
button.go { background:var(--button-primary-default-bg); color:var(--button-primary-default-text);
  border-color:var(--button-primary-default-bg); font-weight:var(--font-weight-medium); }
button.go:hover { background:var(--button-primary-hover-bg); border-color:var(--button-primary-hover-bg); }
button.go:active { background:var(--button-primary-pressed-bg); border-color:var(--button-primary-pressed-bg); }
button:disabled { background:var(--button-secondary-disabled-bg);
  border-color:var(--button-secondary-disabled-border); color:var(--button-secondary-disabled-text);
  cursor:not-allowed; }
button.go:disabled { background:var(--button-primary-disabled-bg);
  border-color:var(--button-primary-disabled-border); color:var(--button-primary-disabled-text); }
table { width:100%; border-collapse:collapse; font-size:var(--font-size-14); }
th, td { padding:var(--spacing-8) var(--spacing-10); border-bottom:1px solid var(--color-border-subtle);
  text-align:left; vertical-align:middle; }
th { font-size:var(--font-size-12); color:var(--color-text-body-tertiary); font-weight:var(--font-weight-medium); }
.muted { color:var(--color-text-helper); }
/* 알림 띠 — 스크롤해도 화면 맨 위에 붙어 있다(찍을 목록이 길면 위로 밀려 안 보였다, river 2026-09-16).
   오른쪽 위 ✕ 로 닫는다. 닫아도 줄마다 붙는 빨간 글은 그대로 남는다. */
.alertbar { position:sticky; top:var(--spacing-8); z-index:30; margin:0 0 var(--spacing-14);
  padding:0; background:none; }
.alertbar .err, .alertbar .ok { margin:0; padding-right:var(--spacing-40);
  box-shadow:0 6px 16px -8px rgba(0,0,0,.28); }
.alertbar .jump { color:inherit; text-decoration:underline; text-underline-offset:2px; }
.alertdo { margin-top:var(--spacing-10); }
tr { scroll-margin-top:140px; }   /* 알림 띠에 가리지 않게 — 줄로 뛰었을 때 */
.alertx { position:absolute; top:var(--spacing-8); right:var(--spacing-8); border:0; background:none;
  cursor:pointer; font-size:var(--font-size-16); line-height:1;
  color:var(--color-text-state-error); padding:var(--spacing-4) var(--spacing-8); border-radius:var(--radius-8); }
.alertx:hover { background:var(--color-red-100); }
.err { background:var(--color-red-50); color:var(--color-text-state-error);
  border:1px solid var(--color-red-100); border-radius:var(--radius-8);
  padding:var(--spacing-10) var(--spacing-12);
  font-size:var(--font-size-14); margin-bottom:var(--spacing-14); }
.ok { background:var(--color-green-50); color:var(--color-green-450);
  border:1px solid var(--color-green-150); border-radius:var(--radius-8);
  padding:var(--spacing-10) var(--spacing-12);
  font-size:var(--font-size-14); margin-bottom:var(--spacing-14); }
.hint { font-size:var(--font-size-12); color:var(--color-text-body-tertiary);
  margin-top:var(--spacing-8); line-height:1.6; }
.guide4 { display:grid; grid-template-columns:repeat(4,1fr); gap:var(--spacing-12);
  margin:var(--spacing-14) 0 var(--spacing-4); }
.g4 { border:1px solid var(--color-border-subtle); border-radius:var(--radius-10);
  padding:var(--spacing-12) var(--spacing-12) var(--spacing-14); background:var(--color-bg-level-1);
  position:relative; }
.g4 .pic { background:var(--color-surface-default); border:1px solid var(--color-border-subtle);
  border-radius:var(--radius-8); padding:var(--spacing-8); margin-bottom:var(--spacing-10); }
.g4 .pic svg, .g4 .pic img { display:block; width:100%; height:auto; border-radius:var(--radius-4); }
.g4 .no { position:absolute; top:10px; left:12px; width:19px; height:19px; border-radius:50%;
  background:var(--color-blue-400); color:var(--color-text-inverse); font-size:var(--font-size-10);
  font-weight:var(--font-weight-bold); text-align:center; line-height:19px; }
.g4 .tt { font-size:var(--font-size-14); font-weight:var(--font-weight-bold); margin-bottom:var(--spacing-2); }
.g4 .dd { font-size:var(--font-size-12); color:var(--color-text-body-secondary); line-height:1.6; }
.g4 .g { color:var(--color-text-helper); }
@media (max-width:820px) { .guide4 { grid-template-columns:repeat(2,1fr); } }
code { background:var(--color-bg-level-2); padding:var(--spacing-2) var(--spacing-6);
  border-radius:var(--radius-4); font-size:var(--font-size-12); }
.frames { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
  gap:var(--spacing-8); margin-top:var(--spacing-6); }
.frames label { display:flex; gap:var(--spacing-8); align-items:center; font-size:var(--font-size-14);
  padding:var(--spacing-8) var(--spacing-10);
  border:1px solid var(--color-border-subtle); border-radius:var(--radius-8);
  background:var(--color-surface-default); cursor:pointer; }
.frames label:hover { background:var(--color-bg-level-1); }
.chips { display:flex; flex-wrap:wrap; gap:var(--spacing-6); margin:0 0 var(--spacing-4); }
.chips .chip { font-size:var(--font-size-12); padding:var(--spacing-6) var(--spacing-12);
  border:1px solid var(--color-border-default); border-radius:var(--radius-full);
  background:var(--color-surface-default); color:var(--color-text-body-primary); cursor:pointer; }
.chips .chip.on { background:var(--button-primary-default-bg); color:var(--button-primary-default-text);
  border-color:var(--button-primary-default-bg); }
.chips .chip.on .muted { color:var(--color-blue-100); }
tr.tie td { background:var(--color-bg-level-1); }
.ties { color:var(--color-text-helper); font-size:var(--font-size-12); }
.bad { color:var(--color-text-state-error); font-size:var(--font-size-12); margin-top:var(--spacing-2); }
/* 그림 위에서 고르기 — 시안 두 장을 나란히 놓고 누를 자리를 클릭한다 */
.pickbtn { margin-top:var(--spacing-4); font-size:var(--font-size-12); padding:2px 8px; height:auto; }
.data { color:var(--color-text-state-warning, var(--color-text-body-tertiary)); font-size:var(--font-size-12); margin-top:var(--spacing-2); }
tr.pickrow td { background:var(--color-bg-level-1); padding:var(--spacing-12); }
.pickq { font-size:var(--font-size-14); margin-bottom:var(--spacing-8); display:flex; align-items:center; gap:var(--spacing-8); }
.figs { display:flex; gap:var(--spacing-12); align-items:flex-start; }
.fig { flex:1; min-width:0; }
.figt { font-size:var(--font-size-12); color:var(--color-text-helper); margin-bottom:var(--spacing-4);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.figbox { position:relative; border:1px solid var(--color-border-subtle); background:#fff; }
.figbox img { display:block; width:100%; height:auto; }
.figarrow { align-self:center; color:var(--color-text-helper); font-size:20px; }
.hot { position:absolute; box-sizing:border-box; padding:0; margin:0; min-width:8px; min-height:8px;
  border:1.5px dashed var(--color-border-default); border-radius:4px; background:transparent; cursor:pointer; }
.hot:hover { border-style:solid; border-color:var(--color-border-focus); background:rgba(29,108,235,.10); }
.hot.on { border:2px solid var(--color-border-focus); background:rgba(29,108,235,.18); }
.hot span { display:none; position:absolute; left:0; top:100%; background:var(--color-surface-default);
  border:1px solid var(--color-border-default); font-size:var(--font-size-12); padding:2px 6px; white-space:nowrap; z-index:2; color:var(--color-text-primary); }
.hot:hover span { display:block; }
.hot.box { border-color:var(--color-green-450, #2a7); border-style:dashed; }
.hot.box:hover { background:rgba(34,153,119,.12); }
.hot.box.on { border:2px solid var(--color-green-450, #2a7); background:rgba(34,153,119,.20); }
.fix { font-size:var(--font-size-12); margin-top:var(--spacing-2);
  color:var(--color-text-body-secondary); display:flex; align-items:center; gap:var(--spacing-6);
  flex-wrap:wrap; }
.fix .pickbtn { margin-top:0; }
.vals { margin-top:var(--spacing-10); }
.valt { font-size:var(--font-size-12); color:var(--color-text-helper); margin-bottom:var(--spacing-4); }
.valrow { display:flex; align-items:center; gap:var(--spacing-8); margin-bottom:var(--spacing-4);
  font-size:var(--font-size-12); }
.valrow span { min-width:160px; color:var(--color-text-body-secondary);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.valrow input { flex:0 0 200px; font-size:var(--font-size-12); padding:2px 6px; }
.picks { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
  gap:var(--spacing-12); margin-top:var(--spacing-12); }
.picks figure { margin:0; background:var(--color-surface-default); border:1px solid var(--color-border-default);
  border-radius:var(--radius-8); padding:var(--spacing-8); }
.picks img { width:100%; display:block; border-radius:var(--radius-4); background:var(--color-bg-level-2);
  max-height:220px; object-fit:contain; object-position:top; }
.picks figcaption { font-size:var(--font-size-12); color:var(--color-text-body-secondary);
  margin-top:var(--spacing-6); word-break:break-all; }
.dim2 { display:block; color:var(--color-text-helper); margin-top:var(--spacing-2); }
.dim2.warn { color:var(--color-red-400); }
.sect { font-size:var(--font-size-12); font-weight:var(--font-weight-bold);
  color:var(--color-text-body-primary); margin:var(--spacing-14) 0 var(--spacing-6); }
/* 동작 사양 — 시안에서 채우면 좋을 것. 칸째로 접었다 펴고, 안에서 갈래로 또 접는다. */
.spec { padding:0; border-color:var(--color-red-100); }
.spec > summary { list-style:none; cursor:pointer; display:flex; align-items:center;
  gap:var(--spacing-6); padding:var(--spacing-16) var(--spacing-20);
  font-size:var(--font-size-14); color:var(--color-text-state-caution);
  border-radius:var(--radius-12); }
.spec > summary::-webkit-details-marker { display:none; }
.spec > summary:hover { background:var(--color-red-50); }
.spec[open] > summary { border-radius:var(--radius-12) var(--radius-12) 0 0; }
.spec > summary .ttl { font-weight:var(--font-weight-bold); }
.spec > summary .muted { font-weight:var(--font-weight-medium); }
.spec > summary .arw { margin-left:auto; flex:0 0 auto; transition:transform .15s; }
.spec[open] > summary .arw { transform:rotate(180deg); }
/* 펴 놓으면 길어질 수 있어, 일정 높이부터는 안쪽만 굴러간다(머리말은 제자리에 남는다). */
.spec > .body { padding:0 var(--spacing-20) var(--spacing-16); max-height:440px; overflow-y:auto; }
.spec .body .grp { display:flex; align-items:center; gap:var(--spacing-8);
  border-top:1px solid var(--color-border-subtle); padding:var(--spacing-10) var(--spacing-2);
  font-size:var(--font-size-14); font-weight:var(--font-weight-medium);
  color:var(--color-text-body-primary); }
.spec .body .grp:first-child { border-top:0; }
.spec .body .grp .n { margin-left:auto; font-size:var(--font-size-12);
  font-weight:var(--font-weight-bold); color:var(--color-text-state-caution); }
.spec .it { display:flex; gap:var(--spacing-10); align-items:flex-start;
  padding:var(--spacing-2) var(--spacing-2) var(--spacing-12) var(--spacing-20); font-size:var(--font-size-12); }
.spec .it img, .spec .it .cut { width:360px; height:240px; flex:0 0 360px;
  border:1px solid var(--color-border-subtle); border-radius:var(--radius-8);
  background-color:var(--color-surface-default); }
@media (max-width: 900px) {
  .spec .it { flex-direction:column; }
  .spec .it img, .spec .it .cut { width:100%; flex:0 0 auto; height:auto; aspect-ratio:3/2; }
}
.spec .it img { object-fit:cover; object-position:top center; }
.spec .it .cut { display:block; background-repeat:no-repeat; }
.spec .it .tx { min-width:0; }
.spec > summary .ico { flex:0 0 auto; }
.spec .it .nm { color:var(--color-text-body-primary); word-break:keep-all; }
.spec .it .why { color:var(--color-text-body-tertiary); margin-top:var(--spacing-2); line-height:1.55; }
.spec .more { padding:0 var(--spacing-2) var(--spacing-10) var(--spacing-20); font-size:var(--font-size-12); }
.spec .more a { color:var(--color-text-link); cursor:pointer; }
.cnt { float:right; font-size:var(--font-size-12); font-weight:var(--font-weight-medium);
  color:var(--color-green-450); }
.dim { font-size:var(--font-size-12); color:var(--color-text-helper);
  margin-left:auto; white-space:nowrap; }
/* 보낼 사진 고르기 — 이름이 길어 칸에 갇히면 세로로 쪼개져 읽히지 않는다.
   한 줄에 하나씩, 이름은 왼쪽부터 가로로 풀어 쓴다. */
.rows { display:flex; flex-direction:column; border:1px solid var(--color-border-subtle);
  border-radius:var(--radius-control-sm); overflow:hidden; }
.rows label { display:flex; gap:var(--spacing-10); align-items:center; font-size:var(--font-size-14);
  padding:var(--spacing-10) var(--spacing-12);
  background:var(--color-surface-default); cursor:pointer; }
.rows label + label { border-top:1px solid var(--color-border-subtle); }
.rows label:hover { background:var(--color-bg-level-1); }
.rows .nm { flex:1; min-width:0; word-break:keep-all; }
.bar { display:flex; gap:var(--spacing-10); align-items:center; margin-top:var(--spacing-16); }
/* 적는 칸 밑에 내미는 '닮은 것' 판 — 목록 화살표 대신 적는 대로 따라 나온다. */
.sugwrap { position:relative; flex:1 1 auto; min-width:0; }
.sugwrap input[type=text] { width:100%; }
.sug { position:absolute; left:0; right:0; top:calc(100% + 4px); z-index:20;
  background:var(--form-bg); border:1px solid var(--color-border-default);
  border-radius:var(--radius-control-sm); box-shadow:0 6px 16px -8px rgba(0,0,0,.28);
  overflow:hidden; }
.sugrow { padding:var(--spacing-8) var(--spacing-12); font-size:var(--font-size-14); cursor:pointer; }
.sugrow + .sugrow { border-top:1px solid var(--color-border-subtle); }
.sugrow:hover, .sugrow.on { background:var(--color-bg-level-1); }

/* 칸 한 줄은 두 칸이든 단추가 붙든 오른쪽 끝이 늘 같은 자리에서 끝난다. */
.form { max-width:460px; }
.form input[type=text], .form input[type=password], .form select, .form .pw { max-width:none; }
.form .bar > input { flex:1 1 auto; min-width:0; }
/* 짧은 값 두 개를 한 줄에 — 좁아지면 저절로 아래로 내려간다. */
.two { display:flex; gap:var(--spacing-16); flex-wrap:wrap; align-items:flex-start; }
.two > div { flex:1 1 0; min-width:140px; }
.bar .right { margin-left:auto; }
pre.log { background:var(--color-gray-dark-0); color:var(--color-gray-dark-800);
  font-size:var(--font-size-12); padding:var(--spacing-14); border-radius:var(--radius-10);
  max-height:280px; overflow:auto; margin:0; white-space:pre-wrap; }
.shots { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr));
  gap:var(--spacing-14); margin-top:var(--spacing-8); }
.shots figure { margin:0; background:var(--color-surface-default); border:1px solid var(--color-border-subtle);
  border-radius:var(--radius-10); padding:var(--spacing-8); }
.shots img { width:100%; display:block; border-radius:var(--radius-6); background:var(--color-bg-level-2); }
.shots figcaption { font-size:var(--font-size-12); color:var(--color-text-body-secondary);
  margin-top:var(--spacing-6); word-break:break-all; text-align:center; }
footer { max-width:1040px; margin:0 auto; padding:0 var(--spacing-28) var(--spacing-40);
  font-size:var(--font-size-12); color:var(--color-text-helper); }
"""

# ── 안내 그림 — 실제 Figma 화면을 보고 그렸다.
#    site/그림/1.png … 4.png 를 넣어 두면 그 사진이 대신 보인다.
#    s1-제외 시작 — 아래는 우리 화면이 아니라 '남의 화면을 그린 삽화'다(사진 대용).
#    사진을 디자인가이드 색으로 칠하지 않듯, 여기 색·크기도 토큰으로 바꾸지 않는다.
_틀 = ('<svg viewBox="0 0 200 104" xmlns="http://www.w3.org/2000/svg" '
      'font-family="-apple-system,sans-serif">')
_끝 = "</svg>"

_그림_설정 = _틀 + \
    '<rect x="2" y="2" width="196" height="100" rx="7" fill="#fff" stroke="#e5e7eb"/>' \
    '<rect x="2" y="2" width="196" height="16" rx="7" fill="#fbfbfb"/>' \
    '<rect x="2" y="11" width="196" height="7" fill="#fbfbfb"/>' \
    '<line x1="2" y1="18" x2="198" y2="18" stroke="#eef0f2"/>' \
    '<circle cx="14" cy="10" r="4.6" fill="#0d9f6e"/>' \
    '<text x="12" y="12" font-size="5" fill="#fff">R</text>' \
    '<text x="22" y="12" font-size="6.5" fill="#374151">river</text>' \
    '<text x="38" y="12" font-size="6" fill="#9ca3af">&#9662;</text>' \
    '<rect x="8" y="24" width="86" height="66" rx="7" fill="#2c2c2c"/>' \
    '<circle cx="51" cy="38" r="8" fill="#0d9f6e"/>' \
    '<text x="48" y="41" font-size="7" fill="#fff">R</text>' \
    '<text x="38" y="53" font-size="5.5" fill="#e5e7eb">river</text>' \
    '<line x1="14" y1="59" x2="88" y2="59" stroke="#4b5563"/>' \
    '<text x="16" y="68" font-size="5.5" fill="#d1d5db">Change theme</text>' \
    '<rect x="12" y="71" width="78" height="10" rx="4" fill="#3f3f46"/>' \
    '<text x="16" y="78" font-size="6" fill="#fff" font-weight="700">Settings</text>' \
    '<text x="16" y="88" font-size="5.5" fill="#d1d5db">Get desktop app</text>' + _끝

_그림_보안 = _틀 + \
    '<rect x="2" y="2" width="196" height="100" rx="7" fill="#fff" stroke="#e5e7eb"/>' \
    '<text x="12" y="15" font-size="6" fill="#9ca3af">Account</text>' \
    '<text x="44" y="15" font-size="6" fill="#9ca3af">Community</text>' \
    '<text x="86" y="15" font-size="6" fill="#9ca3af">Notifications</text>' \
    '<rect x="130" y="7" width="34" height="11" rx="4" fill="#f0f1f3"/>' \
    '<text x="134" y="15" font-size="6" fill="#111827" font-weight="700">Security</text>' \
    '<line x1="2" y1="22" x2="198" y2="22" stroke="#eef0f2"/>' \
    '<text x="12" y="35" font-size="6.5" fill="#111827" font-weight="700">Password</text>' \
    '<text x="12" y="45" font-size="6" fill="#2563eb">Change password</text>' \
    '<line x1="12" y1="52" x2="188" y2="52" stroke="#f0f1f3"/>' \
    '<text x="12" y="65" font-size="6.5" fill="#111827" font-weight="700">Personal access tokens</text>' \
    '<text x="12" y="75" font-size="5.5" fill="#9ca3af">Personal access tokens allow you to access…</text>' \
    '<rect x="10" y="81" width="60" height="12" rx="4" fill="#eff6ff"/>' \
    '<text x="13" y="89.5" font-size="6" fill="#2563eb">Generate new token</text>' + _끝

_그림_범위 = _틀 + \
    '<rect x="2" y="2" width="196" height="100" rx="7" fill="#fff" stroke="#e5e7eb"/>' \
    '<text x="12" y="13" font-size="6.5" fill="#111827" font-weight="700">Scopes</text>' \
    '<text x="12" y="24" font-size="5.5" fill="#9ca3af">Files</text>' \
    '<rect x="11" y="28" width="6" height="6" rx="1.5" fill="#fff" stroke="#d1d5db"/>' \
    '<text x="21" y="33.5" font-size="6" fill="#9ca3af" font-family="ui-monospace,monospace">file_comments:read</text>' \
    '<rect x="8" y="39" width="184" height="20" rx="5" fill="#f2fdf7" stroke="#a7e3c3"/>' \
    '<rect x="11" y="43" width="6" height="6" rx="1.5" fill="#12864e"/>' \
    '<path d="M12.2 46 l1.4 1.4 l2.4 -2.6" stroke="#fff" stroke-width="1" fill="none"/>' \
    '<text x="21" y="48.5" font-size="6" fill="#12864e" font-weight="700" ' \
    'font-family="ui-monospace,monospace">file_content:read</text>' \
    '<text x="21" y="56" font-size="5" fill="#4b5563">Read the contents of and render images from files</text>' \
    '<rect x="11" y="64" width="6" height="6" rx="1.5" fill="#fff" stroke="#d1d5db"/>' \
    '<text x="21" y="69.5" font-size="6" fill="#9ca3af" font-family="ui-monospace,monospace">file_metadata:read</text>' \
    '<rect x="11" y="76" width="6" height="6" rx="1.5" fill="#fff" stroke="#d1d5db"/>' \
    '<text x="21" y="81.5" font-size="6" fill="#9ca3af" font-family="ui-monospace,monospace">file_versions:read</text>' \
    '<rect x="11" y="88" width="6" height="6" rx="1.5" fill="#fff" stroke="#d1d5db"/>' \
    '<text x="21" y="93.5" font-size="6" fill="#9ca3af" font-family="ui-monospace,monospace">library_assets:read</text>' + _끝

_그림_복사 = _틀 + \
    '<rect x="2" y="2" width="196" height="100" rx="7" fill="#fff" stroke="#e5e7eb"/>' \
    '<text x="12" y="14" font-size="6" fill="#6b7280">Token name</text>' \
    '<rect x="11" y="18" width="178" height="12" rx="4" fill="#fff" stroke="#d1d5db"/>' \
    '<text x="15" y="26.5" font-size="6" fill="#374151">촬영 준비</text>' \
    '<text x="12" y="40" font-size="6" fill="#6b7280">Expiration</text>' \
    '<rect x="11" y="44" width="46" height="12" rx="4" fill="#fff" stroke="#d1d5db"/>' \
    '<text x="15" y="52.5" font-size="6" fill="#374151">90 days &#9662;</text>' \
    '<rect x="11" y="64" width="178" height="14" rx="4" fill="#f9fafb" stroke="#d1d5db"/>' \
    '<text x="16" y="73.5" font-size="6.5" fill="#374151" ' \
    'font-family="ui-monospace,monospace">figd_4kZ…q7</text>' \
    '<rect x="152" y="66" width="33" height="10" rx="5" fill="#111827"/>' \
    '<text x="158" y="73.5" font-size="6" fill="#fff">복사</text>' \
    '<text x="12" y="90" font-size="5.5" fill="#b42318">이 글자는 이때 한 번만 보입니다</text>' + _끝


# s1-제외 끝


def _그림(번호, 기본):
    """site/그림/<번호>.png 가 있으면 그 사진을, 없으면 그린 그림을 보여 준다."""
    if (여기 / "그림" / f"{번호}.png").exists():
        return f'<img src="/안내그림/{번호}.png" alt="">'
    return 기본


# 눈 아이콘 — S-1 UX 디자인시스템 Input·Password 정본(eye_hide / eye_show)을 그대로 옮겼다.
# 폐쇄망이라 파일을 불러오지 않고 글자로 박아 둔다.
눈아이콘 = """<svg class="hide" viewBox="0 0 24 24" aria-hidden="true"><g transform="translate(3 4.651)">
<path d="M8.99516 1.98854C8.006 1.98854 7.03683 2.11843 6.1276 2.35823L6.97688 3.20751C7.63632 3.07762 8.30575 2.98769 9.00515 2.98769C12.4622 2.98769 15.5396 4.69624 16.9384 7.35398C16.2989 8.56295 15.2998 9.57209 14.0808 10.3115L14.8002 11.0309C16.1591 10.1516 17.2581 8.98259 17.9475 7.5638C18.0175 7.42392 18.0175 7.26405 17.9475 7.13417C16.4488 4.00683 12.9318 1.98854 9.00515 1.98854H8.99516Z"/>
<path d="M8.99485 11.71C5.53779 11.71 2.46041 10.0014 1.0616 7.34367C1.70105 6.1347 2.7002 5.12556 3.91917 4.38619L3.19978 3.6668C1.84093 4.54605 0.731877 5.71506 0.0524554 7.13385C-0.0174851 7.27373 -0.0174851 7.4336 0.0524554 7.56349C1.56117 10.6908 5.06819 12.7091 8.99485 12.7091C9.98401 12.7091 10.9532 12.5792 11.8624 12.3394L11.0131 11.4901C10.3537 11.62 9.68426 11.71 8.98486 11.71H8.99485Z"/>
<path d="M9.92453 10.4011L5.93792 6.41447C5.84799 6.71421 5.78804 7.02395 5.78804 7.34367C5.78804 9.11217 7.22682 10.5509 8.99532 10.5509C9.32504 10.5509 9.63477 10.491 9.92453 10.4011Z"/>
<path d="M12.2019 7.3434C12.2019 5.57491 10.7631 4.13613 8.99461 4.13613C8.6649 4.13613 8.35516 4.19608 8.0654 4.286L12.052 8.27261C12.1419 7.97287 12.2019 7.66313 12.2019 7.3434Z"/>
<path d="M13.1512 10.8008L11.5825 9.22215L7.11629 4.76595L5.84737 3.49703L5.06803 2.7077L2.35034 0L1.65094 0.709397L4.08887 3.14732L4.83823 3.89669L6.40689 5.46535L10.8731 9.93155L12.142 11.2005L12.9214 11.9798L15.639 14.6975L16.3384 13.9881L13.9005 11.5402L13.1512 10.8008Z"/>
</g></svg><svg class="show" viewBox="0 0 24 24" aria-hidden="true"><g transform="translate(3 6.636)">
<path d="M9 0C5.07109 0 1.55207 2.01944 0.0524854 5.14857C-0.0174951 5.28853 -0.0174951 5.44849 0.0524854 5.57845C1.55207 8.70758 5.07109 10.727 9 10.727C12.9289 10.727 16.4379 8.70758 17.9475 5.57845C18.0175 5.43849 18.0175 5.27853 17.9475 5.14857C16.4379 2.01944 12.9289 0 9 0ZM9 9.7273C5.54096 9.7273 2.46182 8.01777 1.0622 5.35851C2.46182 2.70925 5.54096 0.999722 9 0.999722C12.459 0.999722 15.5382 2.70925 16.9378 5.36851C15.5382 8.02777 12.459 9.73729 9 9.73729V9.7273Z"/>
<path d="M9.00047 8.57777C10.7728 8.57777 12.2096 7.14101 12.2096 5.36866C12.2096 3.59632 10.7728 2.15956 9.00047 2.15956C7.22813 2.15956 5.79136 3.59632 5.79136 5.36866C5.79136 7.14101 7.22813 8.57777 9.00047 8.57777Z"/>
</g></svg>"""

걸음 = [("/", "① 디자인 업로드"), ("/초안", "② 찍을 목록"),
      ("/조건", "③ 조건 확인"), ("/촬영", "④ 전체 촬영")]


def _무리(이름):
    """이름 앞부분으로 화면 갈래를 잡는다 — '웹_로그인 화면_비밀번호 숨김' → '로그인 화면'."""
    조각 = [t.strip() for t in (이름 or "").split("_") if t.strip()]
    if not 조각:
        return "(이름 없음)"
    앞머리 = {"웹", "앱", "web", "app", "aos", "ios", "pc", "mo", "mobile"}
    if len(조각) >= 2 and 조각[0].lower() in 앞머리:
        return 조각[1]
    return 조각[0]


def _그대로단추(글="이대로 진행"):
    """알림 띠 안에서 누르는 '그대로 진행'.

    목록이 길면 맨 아래 단추가 한참 밑에 있어 못 찾는다(river 2026-09-16) — 띠 안에 같은 단추를 둔다.
    `form=` 로 ② 찍을 목록 폼을 가리켜, 띠가 폼 바깥에 있어도 적어 둔 값 그대로 넘어간다.
    """
    return (f'<div class="alertdo"><button class="go" type="submit" name="그래도" value="1"'
            f' form="초안폼">{글} →</button></div>')


def _알림띠(알림):
    """알림을 화면 맨 위에 붙는 띠로 감싼다 — 스크롤해도 따라오고, ✕ 로 닫는다."""
    if not 알림:
        return ""
    return ('<div class="alertbar" id="alertbar" role="alert">' + 알림
            + '<button type="button" class="alertx" aria-label="알림 닫기" title="닫기"'
              ' onclick="document.getElementById(\'alertbar\').remove()">&#10005;</button></div>')


def 껍데기(지금, 본문, 부제="", 알림=""):
    작업 = 작업읽기()
    칩 = ""
    for 길, 이름 in 걸음:
        # 지금 걸음만 고른 것으로 보인다. 지나온 걸음도 '고르지 않은 것'이다(S-1 Chip 상태: default/selected).
        cls = "on" if 길 == 지금 else ""
        칩 += (f'<a class="{cls}" href="{길}">{이름}</a>' if cls != "on"
               else f'<span class="{cls}">{이름}</span>')
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>촬영 준비 — {_e(dict(걸음)[지금])}</title><style>{토큰}{CSS}</style></head><body>
<header><h1>자동 캡쳐 <span class="muted" style="font-weight:400;font-size:var(--font-size-14)">· {_e(유형이름.get(유형(작업), '앱'))} 개발화면</span></h1>
<div class="sub">{_e(부제) or "디자인에서 찍을 화면을 고르고, 목록을 확인한 뒤, 한 번에 찍는다"}</div></header>
<div class="wrap{' w2' if 지금 == '/초안' else ''}"><div class="steps">{칩}</div>{_알림띠(알림)}{본문}</div>
<footer>{_어디서열리나()} · 찍힌 사진은 capture-app/shots/ 에 쌓인다</footer>
</body></html>"""


# ────────────────────────────────────────────────── ① 디자인 고르기
def _동작사양칸(고른것, 유형=None):
    """① 디자인 업로드 — 받은 시안 칸 바로 아래에 붙는 '디자인 수정 필요' 칸.

    색·크기 같은 눈에 보이는 기준은 여기서 말하지 않는다(디자인 쪽 GUI 검수기 몫).
    의견일 뿐이라 고르는 단추는 두지 않고, 촬영을 막지도 않는다.
    """
    나온것 = 동작점검.점검(고른것, 유형)
    if not 나온것:
        return ""
    첫줄 = 5                                   # 갈래마다 처음 보일 줄 수 — 나머지는 '더 보기'
    덩이 = ""
    for gi, (갈래, 항목) in enumerate(동작점검.갈래별(나온것)):
        줄 = ""
        for i, it in enumerate(항목):
            숨김 = ' class="it hid" style="display:none"' if i >= 첫줄 else ' class="it"'
            그림 = ""
            if it.get("자리"):
                주소 = f'/받은그림/{it["자리"]:03d}.png'
                ㅈ = it.get("잘라")
                if ㅈ and ㅈ["w"] < 99 and ㅈ["h"] < 99:
                    # 칸·버튼 있는 데만 확대해 보여 준다 — 시안 한 장을 통째로 줄이면 단추가 점만 해진다.
                    px = ㅈ["x"] / (100 - ㅈ["w"]) * 100 if ㅈ["w"] < 100 else 0
                    py = ㅈ["y"] / (100 - ㅈ["h"]) * 100 if ㅈ["h"] < 100 else 0
                    그림 = (f'<span class="cut" style="background-image:url({주소});'
                          f'background-size:{100 / ㅈ["w"] * 100:.1f}% auto;'
                          f'background-position:{px:.1f}% {py:.1f}%"></span>')
                else:
                    그림 = f'<img src="{주소}" alt="" loading="lazy">'
            줄 += (f'<div{숨김} data-g="{gi}">{그림}<div class="tx">'
                   f'<div class="nm">{_e(it["화면"])}</div>'
                   f'<div class="why">{_e(it["말"])}</div></div></div>')
        if len(항목) > 첫줄:
            줄 += (f'<div class="more" data-g="{gi}">'
                   f'<a onclick="더보기({gi}, this)">… {len(항목) - 첫줄}개 더 보기</a></div>')
        # 갈래 머리말은 접지 않는다 — 칸 자체가 접히므로 안에서 또 접으면 두 번 눌러야 한다.
        덩이 += (f'<div class="grp">{_e(갈래)}'
                 f'<span class="n">{len(항목)}</span></div>{줄}')
    주의아이콘 = ('<svg class="ico" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">'
              '<path fill="var(--color-icon-red)" d="M12 3.2 1.6 20.8h20.8L12 3.2Zm0 4.4 6.9 11.6H5.1L12 7.6Z"/>'
              '<path fill="var(--color-icon-red)" d="M11.1 10.6h1.8v4.9h-1.8zM11.1 16.7h1.8v1.8h-1.8z"/></svg>')
    # 접혔을 때는 머리말만 보이고, 오른쪽 화살표가 펼 수 있다고 알린다.
    화살표 = ('<svg class="arw" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">'
            '<path fill="none" stroke="var(--color-icon-red)" stroke-width="2" stroke-linecap="round"'
            ' stroke-linejoin="round" d="m7 10 5 5 5-5"/></svg>')
    return f"""
    <details class="card spec">
      <summary>{주의아이콘}<span class="ttl">디자인 수정 필요</span>
        <span class="muted">· 받은 {len(고른것)}개 중 {len(나온것)}건</span>{화살표}</summary>
      <div class="body">
      {덩이}
      <script>
        function 더보기(g, el) {{
          document.querySelectorAll('.spec .it.hid[data-g="' + g + '"]')
            .forEach(function(d) {{ d.style.display = ''; }});
          el.parentNode.style.display = 'none';
        }}
      </script>
      </div>
    </details>"""


def 화면_디자인(오류=""):
    작업 = 작업읽기()
    알림 = f'<div class="err">{_e(오류)}</div>' if 오류 else ""
    열쇠있음 = bool(디자인.열쇠())

    열쇠칸 = "" if 열쇠있음 else """
    <div class="card"><h2>Figma 열쇠 넣기 <span class="muted">· 처음 한 번만 · 1분</span></h2>
      <div class="hint" style="margin-top:0">디자인 파일의 화면 목록을 <b>읽기만</b> 하는 열쇠입니다.
        Figma에서 만들어 마지막 칸에 붙여넣으세요.</div>

      <div class="guide4">
        <div class="g4">
          <div class="pic">""" + _그림(1, _그림_설정) + """</div>
          <div class="no">1</div>
          <div class="tt">Figma 설정 열기</div>
          <div class="dd">figma.com 오른쪽 위 <b>내 얼굴</b> → <b>Settings</b></div>
        </div>
        <div class="g4">
          <div class="pic">""" + _그림(2, _그림_보안) + """</div>
          <div class="no">2</div>
          <div class="tt">Security 탭</div>
          <div class="dd">위쪽 탭에서 <b>Security</b> → 아래 <b>Personal access tokens</b></div>
        </div>
        <div class="g4">
          <div class="pic">""" + _그림(3, _그림_범위) + """</div>
          <div class="no">3</div>
          <div class="tt">켤 항목 하나만</div>
          <div class="dd">Scopes에서 <b>file_content:read</b> 한 칸만 체크<br>
            <span class="g">나머지 칸은 모두 비워 둡니다</span></div>
        </div>
        <div class="g4">
          <div class="pic">""" + _그림(4, _그림_복사) + """</div>
          <div class="no">4</div>
          <div class="tt">만들고 복사</div>
          <div class="dd">이름 아무거나 · 기간 <b>90 days</b> · <b>Generate token</b><br>
            <span class="g">나온 <code>figd_…</code> 글자는 한 번만 보입니다</span></div>
        </div>
      </div>

      <form method="post" action="/열쇠">
        <label class="f">열쇠 붙여넣기</label>
        <input type="password" name="토큰" placeholder="figd_..." autocomplete="off">
        <div class="bar"><button class="go" type="submit">저장</button></div>
      </form>
      <div class="hint">열쇠는 이 PC 안(<code>~/.figma-token</code>)에만 저장되고 어디로도 보내지 않습니다.</div>
    </div>"""

    작업 = 작업읽기()
    플러그인 = 작업.get("온곳") == "figma-플러그인"

    안내 = """
    <div class="card"><h2>Figma에서 골라 보내기</h2>
      <div class="hint" style="margin-top:0">
        <b>1</b> Figma 캔버스에서 찍을 화면들을 <b>드래그로 감싸 고릅니다</b>.<br>
        <b>2</b> Plugins → Development → <b>검수 화면 보내기</b> 를 실행합니다.<br>
        <b>3</b> 목록을 눈으로 확인하고 <b>보내기</b> 를 누르면 아래에 그대로 들어옵니다.
      </div>
      <div class="hint">플러그인을 아직 안 깔았다면 Figma 메뉴
        <b>Plugins → Development → Import plugin from manifest…</b> 에서
        <code>capture-app/plugin-pick/manifest.json</code> 을 고르면 됩니다.</div>
    </div>"""

    if 플러그인:
        고른것 = 작업.get("고른화면", [])
        칸 = ""
        for i, f in enumerate(고른것, 1):
            # 폰으로 찍기엔 넓다는 경고 — 웹은 넓은 게 정상이라 붙이지 않는다.
            넓음 = (f.get("폭") or 0) >= 1400 and not 웹인가(작업)
            칸 += (f'<figure class="pick"><img src="/받은그림/{i:03d}.png" alt="">'
                   f'<figcaption>{_e(f.get("이름",""))}'
                   f'<span class="dim2{" warn" if 넓음 else ""}">{f.get("폭")}×{f.get("높이")}'
                   f'{" ⚠︎ 폰치고 넓음" if 넓음 else ""}</span></figcaption></figure>')
        # '디자인 수정 필요'는 걸음 칩 바로 아래 — 받은 화면을 보기 전에 먼저 눈에 띄게 둔다.
        본문 = _동작사양칸(고른것, 작업.get("유형")) + f"""
        <div class="card"><h2>{_e(작업["파일"].get("파일이름"))} —
            {_e(고른것[0].get("페이지", "") if 고른것 else "")}
            <span class="cnt">받은 화면 {len(고른것)}개</span></h2>
          <div class="hint" style="margin-top:0">Figma에서 고른 그대로입니다. 맞으면 다음으로 넘어가세요.
            빼거나 더 넣으려면 Figma에서 다시 고르고 보내면 됩니다.</div>
          <div class="picks">{칸}</div>
          <div class="bar"><a class="btn" href="/비우기">비우고 다시 받기</a>
            <span class="right"></span>
            <a class="btn go" href="/초안">다음 — 찍을 목록 만들기 →</a></div>
        </div>""" + 안내
        return 껍데기("/", 본문, "Figma에서 고른 화면만 가져온다", 알림)

    본문 = 안내 + 열쇠칸 + f"""
    <div class="card"><h2>디자인 파일 주소 <span class="muted">· 플러그인 없이 목록으로 고르기</span></h2>
      <form method="post" action="/디자인">
        <input type="text" name="주소" class="w-lg" placeholder="https://www.figma.com/design/..."
               value="{_e(작업.get('파일주소',''))}">
        <div class="bar"><button class="go" type="submit"{'' if 열쇠있음 else ' disabled'}>화면 목록 읽기</button>
          <span class="hint">{'' if 열쇠있음 else '열쇠를 먼저 넣어 주세요.'}</span></div>
      </form>
      <div class="hint">Figma에서 파일을 열고 주소창을 그대로 붙여넣으세요.</div>
    </div>"""

    파일 = 작업.get("파일")
    if 파일:
        페이지들 = 파일.get("페이지", [])
        고른페이지 = 작업.get("고른페이지") or (페이지들[0]["id"] if 페이지들 else "")
        고른것 = 작업.get("고른화면", [])
        고른수 = {}
        for f in 고른것:
            고른수[f.get("페이지", "")] = 고른수.get(f.get("페이지", ""), 0) + 1
        옵션 = ""
        for p in 페이지들:
            뽑힘 = 고른수.get(p["id"], 0)
            꼬리 = f" · 고른 것 {뽑힘}개" if 뽑힘 else ""
            골랐음 = " selected" if p["id"] == 고른페이지 else ""
            옵션 += (f'<option value="{_e(p["id"])}"{골랐음}>'
                   f'{_e(p["이름"])} · 화면 {len(p["화면"])}개{꼬리}</option>')
        본문 += f"""
        <div class="card"><h2>{_e(파일.get("파일이름"))} — 페이지 고르기</h2>
          <form method="get" action="/">
            <select name="페이지" onchange="this.form.submit()">{옵션}</select>
          </form>
          <div class="hint">페이지를 옮겨도 고른 것은 남습니다.</div>
        </div>"""

        이미고름 = {f["id"] for f in 고른것}
        이페이지수 = len([f for f in 고른것 if f.get("페이지") == 고른페이지])
        현재 = next((p for p in 페이지들 if p["id"] == 고른페이지), None)
        if 현재:
            묶음별 = []
            for f in 현재["화면"]:
                이름 = f.get("묶음", "")
                if not 묶음별 or 묶음별[-1][0] != 이름:
                    묶음별.append((이름, []))
                묶음별[-1][1].append(f)

            덩이 = ""
            for 묶음이름, 목록 in 묶음별:
                칸 = ""
                for f in 목록:
                    체크 = " checked" if f["id"] in 이미고름 else ""
                    무리 = _무리(f["이름"])
                    칸 += (f'<label data-name="{_e(f["이름"])}" data-group="{_e(무리)}">'
                           f'<input type="checkbox" name="화면" value="{_e(f["id"])}"{체크}>'
                           f'<span>{_e(f["이름"])}</span>'
                           f'<span class="dim">{f["폭"]}×{f["높이"]}</span></label>')
                제목 = (f'<div class="sect">{_e(묶음이름)} '
                      f'<span class="muted">· {len(목록)}</span></div>' if 묶음이름 else "")
                덩이 += 제목 + f'<div class="frames">{칸}</div>'

            갈래 = {}
            for f in 현재["화면"]:
                g = _무리(f["이름"])
                갈래[g] = 갈래.get(g, 0) + 1
            칩 = '<span class="chip on" data-g="" onclick="갈래고르기(this)">전체</span>'
            for g, n in sorted(갈래.items(), key=lambda kv: -kv[1])[:14]:
                칩 += (f'<span class="chip" data-g="{_e(g)}" onclick="갈래고르기(this)">'
                      f'{_e(g)} <span class="muted">{n}</span></span>')

            본문 += f"""
            <div class="card"><h2>찍을 화면 고르기
                <span class="muted">· 이 페이지 {len(현재["화면"])}개</span>
                <span class="cnt" id="cnt">고른 것 {len(고른것)}개</span></h2>
              <form method="post" action="/고르기">
                <input type="hidden" name="페이지" value="{_e(고른페이지)}">
                <div class="bar" style="margin:0 0 var(--spacing-8)">
                  <input type="text" class="s" id="찾기" placeholder="이름으로 걸러내기 (예: 로그인 -회원)"
                         style="max-width:300px" oninput="걸러()">
                  <button type="button" onclick="pick(true)">보이는 것 전체 선택</button>
                  <button type="button" onclick="pick(false)">전체 해제</button></div>
                <div class="hint" style="margin:0 0 var(--spacing-8)">낱말을 띄어 쓰면 <b>둘 다</b> 든 것만,
                  낱말 앞에 <b>-</b> 를 붙이면 그 낱말이 든 것은 뺍니다.</div>
                <div class="chips">{칩}</div>
                {덩이 or '<p class="muted">이 페이지에는 화면(프레임)이 없습니다.</p>'}
                <div class="bar"><span class="hint">여러 페이지에서 골라 모을 수 있습니다.</span>
                  <span class="right"></span>
                  <button class="go" type="submit">다음 — 찍을 목록 만들기 →</button></div>
              </form>
              <script>
                function 보임(l) {{ return l.style.display !== 'none'; }}
                function pick(v) {{
                  Array.prototype.slice.call(document.querySelectorAll('.frames label'))
                    .filter(보임).forEach(function(l) {{ l.querySelector('input').checked = v; }});
                  세기();
                }}
                var 고른갈래 = '';
                function 갈래고르기(el) {{
                  document.querySelectorAll('.chips .chip').forEach(function(c) {{
                    c.classList.remove('on'); }});
                  el.classList.add('on');
                  고른갈래 = el.dataset.g;
                  걸러();
                }}
                function 걸러() {{
                  var q = (document.getElementById('찾기').value || '').trim().toLowerCase();
                  var 낱말 = q ? q.split(/\s+/) : [];
                  var 들것 = 낱말.filter(function(w) {{ return w[0] !== '-'; }});
                  var 뺄것 = 낱말.filter(function(w) {{ return w[0] === '-' && w.length > 1; }})
                                .map(function(w) {{ return w.slice(1); }});
                  document.querySelectorAll('.frames label').forEach(function(l) {{
                    var 이름 = l.dataset.name.toLowerCase();
                    var 맞음 = (!고른갈래 || l.dataset.group === 고른갈래)
                      && 들것.every(function(w) {{ return 이름.indexOf(w) >= 0; }})
                      && !뺄것.some(function(w) {{ return 이름.indexOf(w) >= 0; }});
                    l.style.display = 맞음 ? '' : 'none';
                  }});
                  document.querySelectorAll('.frames').forEach(function(g) {{
                    var 남음 = Array.prototype.slice.call(g.querySelectorAll('label')).filter(보임).length;
                    g.style.display = 남음 ? '' : 'none';
                    var 앞 = g.previousElementSibling;
                    if (앞 && 앞.className === 'sect') 앞.style.display = 남음 ? '' : 'none';
                  }});
                }}
                function 세기() {{
                  var n = document.querySelectorAll('.frames input:checked').length
                        + {len(고른것)} - {이페이지수};
                  document.getElementById('cnt').textContent = '고른 것 ' + n + '개';
                }}
                document.addEventListener('change', function(e) {{
                  if (e.target.name === '화면') 세기();
                }});
              </script>
            </div>"""
    return 껍데기("/", 본문, "찍을 화면을 디자인 원본에서 고른다", 알림)


def _메뉴띠말(것):
    """'읽고 있는 티' 한 줄 — 무엇을 몇 개째 읽고 있는지 그대로 보인다."""
    if 것.get("까닭"):
        return f"메뉴를 읽지 못했습니다 — {것['까닭']}"
    if 것.get("진행중"):
        지금, 전부 = 것.get("지금", 0), 것.get("전부", 0)
        읽는것 = 것.get("읽는것") or ""
        셈 = f" · {지금}/{전부}" if 전부 else ""
        return f"{것.get('말') or '메뉴를 읽는 중'}{셈}" + (f" — {읽는것}" if 읽는것 else "")
    if 것.get("메뉴"):
        때 = 것.get("때") or ""
        return f"메뉴 {len(것['메뉴'])}개를 읽어 두었습니다" + (f" · {때}" if 때 else "")
    return "메뉴는 아직 읽지 않았습니다"


# ────────────────────────────────────────────────── ② 찍을 목록 초안
def 화면_초안(알림=""):
    작업 = 작업읽기()
    if not 작업.get("초안"):
        return 껍데기("/초안", '<div class="card"><p class="muted">먼저 ① 에서 디자인 화면을 고르세요.</p></div>',
                   "찍을 목록")
    웹 = 웹인가(작업)

    def 셋째칸(i, r, 이어서):
        if 웹:      # 웹은 누를 메뉴가 아니라 '개발 주소'를 적는다(메뉴를 훑어 두면 저절로 채워진다)
            return (f'<td><input class="s" type="text" name="주소_{i}" id="주소_{i}" '
                    f'list="메뉴들" value="{_e(r.get("주소",""))}" placeholder="/login" '
                    f'autocomplete="off">'
                    f'<div class="hint" id="닮음_{i}"></div></td>')
        return (f'<td><input class="s" type="text" name="누를것_{i}" value="{_e(r["누를것"])}" '
                f'{"disabled" if 이어서 else ""}></td>')

    행 = ""
    그림자료 = []          # 줄마다 시안 그림 주소와 '누를 수 있는 것' — 그림 위에서 고르기용
    바탕i = 0
    for i, r in enumerate(작업["초안"]):
        이어서 = r.get("이어서") == "예"
        if not 이어서:
            바탕i = i
        # 왼쪽에 놓을 화면. 같은 묶음이면 그 묶음의 바탕 화면, **묶음의 첫 장이면 바로 앞 줄**이다
        # (river 확정 2026-09-16: '회원 가입' 첫 장은 앞 화면인 로그인의 `회원가입` 을 눌러 들어간다 —
        #  자기 화면만 띄우면 누를 것이 아예 없다). 목록 맨 첫 줄만 왼쪽이 없다.
        왼쪽 = 바탕i if 이어서 else (i - 1 if i > 0 else -1)
        그림자료.append({"그림": f"/받은그림/{Path(r['디자인그림']).name}" if r.get("디자인그림") else "",
                     "누를것": 동작규칙.누를것들(시안요소.전체목록(r), 유형(작업), 넓게=True),
                     "왼쪽": 왼쪽, "앞화면": not 이어서, "이름": r.get("이름", "")})
        자료조건 = r.get("자료조건") or ""
        표시 = ('<span class="ties">↳ 같은 화면</span>' if 이어서
              else f'<b>{_e(r.get("화면묶음",""))}</b>')
        칸이름들 = [h["글자"] for h in 그림자료[i]["누를것"] if h.get("칸")]
        틀림 = 동작말.확인(r.get("동작", ""), 유형(작업))
        # 틀리게 썼으면 혼내지 말고 고친 문장을 내민다 — 받아들일지는 사람이 누른다
        제안 = 동작말.고쳐보기(r.get("동작", ""), 유형(작업), 칸이름들) if 틀림 else ""
        고침칸 = ""
        if 틀림 and 제안:
            고침칸 = (f'<div class="fix">이렇게 쓰신 거죠? <code>{_e(제안)}</code> '
                   f'<button type="button" class="pickbtn" data-fix="{_e(제안)}" '
                   f'onclick="고침({i},this)">이대로 바꾸기</button></div>')
        elif 틀림 and 칸이름들:
            고침칸 = ('<div class="hint" style="margin-top:var(--spacing-2)">이 화면의 적는 칸: '
                   + " · ".join(f"<code>{_e(c)}</code>" for c in 칸이름들[:4]) + '</div>')
        빈동작 = 이어서 and not (r.get("동작", "") or "").strip()
        행 += f"""<tr id="줄{i+1}" class="{'tie' if 이어서 else ''}">
          <td class="muted">{i+1}</td>
          <td><input class="s" type="text" name="번호_{i}" value="{_e(r['번호'])}"></td>
          <td><textarea class="s act" name="이름_{i}" rows="2" wrap="soft">{_e(r['이름'])}</textarea></td>
          <td><textarea class="s act" name="상태_{i}" rows="2" wrap="soft">{_e(r['상태'])}</textarea></td>
          {셋째칸(i, r, 이어서)}
          <td><textarea class="s act" name="동작_{i}" rows="2" wrap="soft"
                 placeholder="{_e(r.get('힌트','') or '예: 입력 아이디=test01 → 탭 로그인')}">{_e(r.get('동작',''))}</textarea>
              <div class="fixbox" id="fixbox_{i}">{(f'<div class="bad">이 말은 못 알아듣습니다</div>{고침칸}' if 제안
                    else f'<div class="bad">{_e(틀림)}</div>{고침칸}') if 틀림
                else ('<div class="bad">비면 앞 장과 똑같은 사진이 찍힙니다</div>' if 빈동작 else '')}</div>
              {f'<div class="hint" style="margin-top:var(--spacing-2)">짚은 근거: {_e(r.get("근거"))} — 틀리면 고치세요</div>' if r.get("근거") and (r.get("동작") or "").strip() else ''}
              {f'<div class="data">자료 조건 화면 — "{_e(자료조건)}" 은 눌러서 못 만듭니다. 시험 계정·자료가 그 상태여야 찍힙니다.</div>' if 자료조건 else ''}
              {f'<button type="button" class="pickbtn" onclick="그림고르기({i})">그림에서 고르기</button>' if 그림자료[i]["그림"] else ''}</td>
          <td style="font-size:var(--font-size-12)">{표시}<div class="muted" style="font-size:var(--font-size-10)">{_e(r.get('디자인이름',''))}</div></td>
        </tr>
        <tr class="pickrow" id="pick_{i}" hidden><td colspan="7"><div class="pickpanel" id="pickpanel_{i}"></div></td></tr>"""
    # 시안 글자가 <script> 안에 들어가므로 '</' 만 막아 둔다(닫는 꼬리표로 오해받지 않게).
    그림자료글 = json.dumps(그림자료, ensure_ascii=False).replace("</", "<\\/")
    겹침 = 초안만들기.겹친번호(작업["초안"])
    경고 = (f'<div class="err">번호가 겹칩니다 — {", ".join(겹침)}. '
           f'같은 번호는 사진이 덮어써집니다.</div>' if 겹침 else "")

    사전 = 앱사전.읽기()
    # 웹 화면에는 앱 이름이 섞여 나오지 않게, 그 갈래에 맞는 것만 보여 준다.
    보일사전 = {k: v for k, v in 사전.items()
             if bool(v.get("기본주소")) == 웹인가(작업)} or (
                 {} if 웹인가(작업) else 사전)
    제안코드 = 서비스코드제안(작업)
    제안출처 = ("적힌것" if (작업.get("서비스코드") or "").strip()
            else "기억" if (사전.get(작업.get("앱이름", "")) or {}).get("서비스코드") else "짐작")
    자리코드 = "WEB" if 웹 else "AND"
    깔린앱 = "".join(f'<option value="{_e(pkg)}">' for pkg in 깔린앱목록())

    # 웹이면 들어오자마자 사이트 메뉴를 훑어 둔다 — 아무것도 누르지 않아도 주소가 채워지게.
    # 계정·주소가 비어 있으면 돌지 않는다(로그인을 잘못 여러 번 해 잠기지 않게).
    메뉴상태 = {}
    if 웹:
        메뉴훑기.자동시작(작업)
        메뉴상태 = 메뉴훑기.상태()

    # 사이트·앱 정보 칸. 서비스 코드와 찍을 폭은 짧은 값이라 한 줄에 나란히 놓는다.
    코드칸 = (
        '<label class="f">서비스 코드</label>'
        '<input type="text" name="서비스코드" id="서비스코드" class="w-md" autocomplete="off"'
        f' value="{_e(제안코드)}" placeholder="예: UV" oninput="이름미리()">')
    이름힌트 = ""
    if 웹:
        폭 = 작업.get("찍을폭") or (작업["고른화면"][0]["폭"] if 작업.get("고른화면") else 1440)
        정보칸 = (
            '<div class="two">'
            f'<div>{코드칸}</div>'
            '<div><label class="f">찍을 폭</label>'
            f'<input type="text" name="화면폭" id="화면폭" class="w-sm" value="{폭}"></div>'
            '</div>'
            + 이름힌트
            + '<label class="f">기본 주소</label>'
            '<div class="bar" style="margin:0">'
            '<input type="text" name="기본주소" id="기본주소" autocomplete="off"'
            f' class="w-md" value="{_e(작업.get("기본주소",""))}" placeholder="https://dev.example.com"'
            ' aria-describedby="메뉴말">'
            '<button type="button" class="go" id="IA단추" onclick="메뉴다시()" style="white-space:nowrap"'
            f'{" disabled" if 메뉴상태.get("진행중") else ""}>'
            f'{"읽는 중" if 메뉴상태.get("진행중") else "IA 읽어오기"}</button>'
            '</div>'
            f'<div class="helper" id="메뉴말" role="status">{_e(_메뉴띠말(메뉴상태))}</div>')
    else:
        정보칸 = (코드칸 + 이름힌트
               + '<label class="f">앱 주소</label>'
               '<input type="text" name="앱주소" id="앱주소" list="깔린앱들" autocomplete="off"'
               f' class="w-md" value="{_e(작업.get("앱주소",""))}">'
               f'<datalist id="깔린앱들">{깔린앱}</datalist>')

    # 로그인 화면을 안 찍고 홈·메뉴만 찍을 때 지나는 길 — 앱은 적어 둬야 하고, 웹은 저절로 들어간다.
    들머리칸 = "" if 웹 else (
        '<label class="f">들어가는 길</label>'
        '<input type="text" name="들어가는길" id="들어가는길" class="w-md" autocomplete="off"'
        f' value="{_e(작업.get("들어가는길", ""))}"'
        ' placeholder="입력 아이디=&lt;아이디&gt; → 입력 비밀번호=&lt;비번&gt; → 탭 로그인">'
        '<div class="hint">로그인 화면을 안 찍고 홈·메뉴만 찍을 때 씁니다. '
        '찍기 전에 이 동작으로 한 번 들어갑니다.</div>')

    본문 = f"""{경고}
    <form method="post" action="/초안" id="초안폼">
    <div class="card"><h2>{'사이트 정보' if 웹 else '앱 정보'}
      <span class="muted">· {_e(유형이름.get(유형(작업), '앱'))} <span style="font-weight:400">— 플러그인에서 고른 유형</span></span></h2>
      <div class="form">
      <label class="f">{'사이트 이름' if 웹 else '앱 이름'}</label>
      <div class="bar" style="margin:0">
        <div class="sugwrap">
          <input type="text" name="앱이름" id="앱이름" autocomplete="off"
                 class="w-md" value="{_e(작업.get('앱이름',''))}" aria-describedby="읽은말"
                 role="combobox" aria-expanded="false" aria-autocomplete="list" aria-controls="이름제안">
          <div class="sug" id="이름제안" role="listbox" hidden></div>
        </div>
        <button type="button" class="go" onclick="읽기()" style="white-space:nowrap">읽기</button>
      </div>
      <div class="helper" id="읽은말" role="status" hidden></div>

      <div id="계정칸">
        <div class="two">
          <div>
            <label class="f">시험 아이디</label>
            <input type="text" name="시험아이디" id="시험아이디" class="w-md" autocomplete="off"
                   value="{_e(작업.get('시험아이디',''))}">
          </div>
          <div>
            <label class="f">시험 비밀번호</label>
            <div class="pw">
              <input type="password" name="시험비밀번호" id="시험비밀번호" autocomplete="new-password"
                     value="{_e(작업.get('시험비밀번호',''))}">
              <button type="button" class="eye" id="비번보기버튼" onclick="비번보기()"
                      aria-pressed="false" aria-label="비밀번호 보기" aria-controls="시험비밀번호">{눈아이콘}</button>
            </div>
          </div>
        </div>
        {들머리칸}
      </div>

      {정보칸}

      <script>
        var 사전 = {json.dumps(보일사전, ensure_ascii=False)};
        var 웹 = {1 if 웹 else 0};
        var 칸들 = 웹 ? ['서비스코드', '기본주소', '화면폭', '시험아이디', '시험비밀번호']
                     : ['서비스코드', '앱주소', '시험아이디', '시험비밀번호', '들어가는길'];
        // 이름을 읽으면 사전에 적힌 값으로 새로 채운다. 잠그지 않는다 — 어느 유형이든 그냥 고쳐 쓴다.
        var 덮을칸 = 웹 ? ['서비스코드', '기본주소', '화면폭'] : ['서비스코드', '앱주소'];
        var 흔한말 = ['www','dev','develop','test','stage','staging','qa','m','mobile','web','portal',
                    'admin','app','apps','site','front','new','com','co','kr','net','org','io','go','or','local','localhost'];
        function 칸(k) {{ return document.getElementById(k); }}
        function 비번보기() {{
          var e = 칸('시험비밀번호'), 단추 = document.getElementById('비번보기버튼');
          var 보임 = e.type !== 'password';
          e.type = 보임 ? 'password' : 'text';
          단추.setAttribute('aria-pressed', String(!보임));
          단추.setAttribute('aria-label', 보임 ? '비밀번호 보기' : '비밀번호 숨기기');
          e.focus();
        }}
        function 말(글, 상태) {{                       // 상태: '' | 'error' | 'correct'
          var e = document.getElementById('읽은말'), 칸 = document.getElementById('앱이름');
          e.innerHTML = 글;
          e.hidden = !글;
          e.className = 'helper' + (상태 ? ' is-' + 상태 : '');
          칸.classList.toggle('is-error', 상태 === 'error');
          칸.classList.toggle('is-correct', 상태 === 'correct');
        }}
        function 이름미리() {{
          var e = document.getElementById('이름미리보기');
          if (e) e.textContent = ((칸('서비스코드').value || '코드').toUpperCase()) + '-{자리코드}-001';
        }}
        function 쓸만한조각(글) {{                      // 주소·꾸러미 이름에서 뜻 있는 조각만
          var 남은 = (글 || '').split('.').filter(function(c) {{
            return c && 흔한말.indexOf(c.toLowerCase()) < 0;
          }});
          return 남은.length ? 남은[남은.length - 1] : '';
        }}
        function 코드제안() {{                          // 서버가 하는 것과 같은 차례(서비스코드제안)
          if (칸('서비스코드').value.trim()) return;
          var 이름 = document.getElementById('앱이름').value.trim();
          var 영문 = 이름.match(/[A-Za-z][A-Za-z0-9-]*/g) || [];
          for (var i = 0; i < 영문.length; i++) {{
            if (흔한말.indexOf(영문[i].toLowerCase()) < 0) {{
              칸('서비스코드').value = 영문[i].replace(/[^A-Za-z0-9]/g, '').toUpperCase();
              return 이름미리();
            }}
          }}
          var 주소 = 웹 ? (칸('기본주소') ? 칸('기본주소').value : '') : (칸('앱주소') ? 칸('앱주소').value : '');
          var 조각 = 쓸만한조각(주소.replace(/^[a-z]+:\/\//i, '').split('/')[0]);
          칸('서비스코드').value = 조각.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
          이름미리();
        }}
        function 읽기() {{
          var 이름 = document.getElementById('앱이름').value.trim();
          if (!이름) {{ 말((웹 ? '사이트' : '앱') + ' 이름을 먼저 적어 주세요.', 'error'); return; }}
          var 것 = 사전[이름];
          if (!것) {{
            코드제안();
            말('<b>' + 이름 + '</b> 은(는) 아직 모르는 ' + (웹 ? '사이트' : '앱') + '입니다. 아래 칸을 직접 적어 주세요.', 'error');
            return;
          }}
          칸들.forEach(function(k) {{
            if (덮을칸.indexOf(k) >= 0 || !칸(k).value) 칸(k).value = 것[k] || '';
          }});
          이름미리();
          말('<b>' + 이름 + '</b> 을(를) 찾았습니다. 다르면 그냥 고쳐 쓰세요.', 'correct');
        }}
        ['기본주소', '앱주소'].forEach(function(k) {{        // 주소를 적으면 빈 코드 칸을 채워 준다
          var e = 칸(k);
          if (e) e.addEventListener('blur', 코드제안);
        }});

        /* 적는 대로 전에 쓴 것 중 닮은 것을 밑에 내민다 — 고르면 그 자리에서 읽는다.
           목록에서 고르는 칸이 아니라 적는 칸이다. 안 고르고 그냥 적어도 된다. */
        (function () {{
          var 칸이름 = document.getElementById('앱이름');
          var 판 = document.getElementById('이름제안');
          var 이름들 = Object.keys(사전);
          var 고른줄 = -1;
          function 민글(t) {{ return (t || '').toLowerCase().replace(/\s+/g, ''); }}
          function 주소(k) {{ var 것 = 사전[k] || {{}}; return 것.기본주소 || 것.앱주소 || ''; }}
          function 닮은것(q) {{
            var g = 민글(q);
            if (!g) return [];
            var 앞 = [], 속 = [];
            이름들.forEach(function (k) {{
              var n = 민글(k), a = 민글(주소(k));
              if (n.indexOf(g) === 0) 앞.push(k);
              else if (n.indexOf(g) > 0 || a.indexOf(g) >= 0) 속.push(k);
            }});
            return 앞.concat(속).slice(0, 6);
          }}
          function 닫기() {{
            판.hidden = true; 판.innerHTML = ''; 고른줄 = -1;
            칸이름.setAttribute('aria-expanded', 'false');
          }}
          function 넣기(k) {{ 칸이름.value = k; 닫기(); 읽기(); }}
          function 칠하기() {{
            [].forEach.call(판.children, function (e, i) {{
              e.classList.toggle('on', i === 고른줄);
            }});
          }}
          function 그리기() {{
            var 것들 = 닮은것(칸이름.value);
            if (!것들.length) return 닫기();
            판.innerHTML = 것들.map(function (k) {{
              return '<div class="sugrow" role="option" data-이름="' + k + '">' + k
                + (주소(k) ? '<span class="muted"> · ' + 주소(k) + '</span>' : '') + '</div>';
            }}).join('');
            [].forEach.call(판.children, function (e) {{
              e.addEventListener('mousedown', function (ev) {{
                ev.preventDefault(); 넣기(e.getAttribute('data-이름'));
              }});
            }});
            고른줄 = -1; 판.hidden = false;
            칸이름.setAttribute('aria-expanded', 'true');
          }}
          칸이름.addEventListener('input', 그리기);
          칸이름.addEventListener('focus', 그리기);
          칸이름.addEventListener('blur', function () {{ setTimeout(닫기, 120); }});
          칸이름.addEventListener('keydown', function (e) {{
            var 열림 = !판.hidden && 판.children.length;
            if (e.key === 'ArrowDown' && 열림) {{
              e.preventDefault(); 고른줄 = (고른줄 + 1) % 판.children.length; 칠하기();
            }} else if (e.key === 'ArrowUp' && 열림) {{
              e.preventDefault(); 고른줄 = (고른줄 - 1 + 판.children.length) % 판.children.length; 칠하기();
            }} else if (e.key === 'Enter') {{
              e.preventDefault();
              if (열림 && 고른줄 >= 0) 넣기(판.children[고른줄].getAttribute('data-이름'));
              else {{ 닫기(); 읽기(); }}
            }} else if (e.key === 'Escape') {{
              닫기();
            }}
          }});
        }})();
      </script>
      </div>
    </div>
    <div class="card"><h2>찍을 목록 <span class="muted">· {len(작업["초안"])}개 · 디자인에 놓인 차례 그대로 · 틀린 건 고치세요</span></h2>
      <table class="list">
        <colgroup><col style="width:30px"><col style="width:72px"><col style="width:18%">
          <col style="width:15%"><col style="width:12%"><col><col style="width:120px"></colgroup>
        <thead><tr><th></th><th>번호</th><th>화면 이름</th><th>상태</th>
        <th>{'개발 주소 <span class="muted">(기본 주소 뒤에 붙는 부분)</span>'
             if 웹 else '눌러 들어갈 메뉴 <span class="muted">(앱 켜면 바로 나오는 화면은 -)</span>'}</th>
        <th>동작 <span class="muted">— 그 상태를 만드는 법</span></th>
        <th>화면 묶음</th></tr></thead>
        <tbody>{행}</tbody></table>
      <datalist id="메뉴들"></datalist>
      <script>
        /* 사이트 메뉴를 읽는 동안, 읽는 대로 주소 칸을 채운다.
           사람이 적고 있는 칸과 이미 적힌 칸은 건드리지 않는다. */
        (function () {{
          var 웹 = {1 if 웹 else 0};
          if (!웹) return;
          function 그리기(것) {{
            var 말 = document.getElementById('메뉴말');
            if (말) {{
              말.textContent = 것.말줄 || '';
              말.className = 'helper' + (것.까닭 ? ' is-error' : '');
            }}
            var 단추 = document.getElementById('IA단추');
            if (단추) {{
              단추.disabled = !!것.진행중;
              단추.textContent = 것.진행중 ? '읽는 중' : 'IA 읽어오기';
            }}
            var 목록 = document.getElementById('메뉴들');
            if (목록 && 것.메뉴) {{
              목록.innerHTML = 것.메뉴.map(function (m) {{
                return '<option value="' + m.주소길 + '">' + m.이름 + '</option>';
              }}).join('');
            }}
            Object.keys(것.짝 || {{}}).forEach(function (i) {{
              var 칸 = document.getElementById('주소_' + i);
              var 표 = document.getElementById('닮음_' + i);
              var 하나 = 것.짝[i];
              if (!칸 || !표) return;
              if (하나.확정) {{
                if (!칸.value && document.activeElement !== 칸) {{
                  칸.value = 하나.주소;
                  표.textContent = '자동으로 넣었습니다 — ' + 하나.메뉴이름
                    + ' · 닮음 ' + 하나.닮음 + '%. 다르면 고치세요';
                }} else if (칸.value === 하나.주소) {{
                  표.textContent = '자동으로 넣었습니다 — ' + 하나.메뉴이름 + ' · 닮음 ' + 하나.닮음 + '%';
                }}
                return;
              }}
              /* 애매한 것은 넣지 않는다 — 가장 닮은 것만 내밀고 사람이 누른다. */
              if (칸.value) return;
              표.innerHTML = '어느 메뉴인지 애매합니다. 가장 닮은 것은 <b>' + 하나.메뉴이름
                + '</b> (' + 하나.닮음 + '%) '
                + '<button type="button" class="pickbtn" data-주소="' + 하나.주소
                + '" data-줄="' + i + '">이걸로</button>';
              var 단추 = 표.querySelector('button');
              if (단추) 단추.onclick = function () {{
                칸.value = 단추.getAttribute('data-주소');
                표.textContent = '눌러서 넣었습니다 — ' + 하나.메뉴이름;
              }};
            }});
          }}
          function 한번() {{
            fetch('/메뉴훑기/상태').then(function (r) {{ return r.json(); }}).then(function (것) {{
              그리기(것);
              if (것.진행중) setTimeout(한번, 1200);
            }}).catch(function () {{}});
          }}
          window.메뉴다시 = function () {{
            fetch('/메뉴훑기', {{method: 'POST'}}).then(function () {{ setTimeout(한번, 300); }});
          }};
          한번();
        }})();
      </script>
      <script>
        /* 동작 칸은 적은 글만큼 스스로 자란다 — 긴 문장도 잘리지 않게. */
        (function () {{
          var 칸들 = document.querySelectorAll('textarea.act');
          function 맞추기(t) {{ t.style.height = 'auto'; t.style.height = (t.scrollHeight + 2) + 'px'; }}
          칸들.forEach(function (t) {{ 맞추기(t); t.addEventListener('input', function () {{ 맞추기(t); }}); }});
          window.addEventListener('resize', function () {{ 칸들.forEach(맞추기); }});
        }})();
      </script>
      <script>
        /* 그림 위에서 고르기 — "이 화면이 나오려면 어디를 누르나요?" 에 클릭으로 답한다.
           점선 칸은 시안 속 짧은 글자 전부(서버 동작규칙.누를것들 넓게). 누른 차례대로 '탭 A → 탭 B → 기다림 1.2' 가 된다.
           왼쪽에 놓이는 것: 같은 묶음이면 그 묶음의 바탕 화면, 묶음의 첫 장이면 바로 앞 줄의 화면. */
        var 그림자료 = {그림자료글};
        var 고른 = {{}};
        function 동작칸(i) {{ return document.getElementsByName('동작_' + i)[0]; }}
        function 마디들(글) {{ return (글 || '').split(/\\s*(?:→|->|;|\\n)\\s*/).map(function (s) {{ return s.trim(); }}).filter(Boolean); }}
        function 글자막기(s) {{ return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }}
        function 그림그리기(i, 자료, 제목) {{
          if (!자료 || !자료.그림) return '';
          var 점 = 자료.누를것.map(function (h) {{
            var z = h.자리;
            return '<button type="button" class="hot' + (h.칸 ? ' box' : '') + '"' +
              ' data-act="' + 글자막기(h.동작) + '" data-val="' + 글자막기(h.값제안 || '') + '"' +
              ' style="left:' + z.x + '%;top:' + z.y + '%;width:' + z.w + '%;height:' + z.h + '%"' +
              ' onclick="누름(' + i + ',this)"><span>' + (h.칸 ? '적는 칸 · ' : '') + 글자막기(h.글자) + '</span></button>';
          }}).join('');
          return '<div class="fig"><div class="figt">' + 글자막기(제목) + '</div><div class="figbox"><img src="' + 자료.그림 + '" alt="">' + 점 + '</div></div>';
        }}
        function 표시(i) {{
          var 든것 = 마디들(동작칸(i).value);
          document.querySelectorAll('#pickpanel_' + i + ' .hot').forEach(function (b) {{
            var a = b.getAttribute('data-act');
            b.classList.toggle('on', 든것.some(function (m) {{
              return a.slice(-1) === '=' ? m.indexOf(a) === 0 : m === a;
            }}));
          }});
        }}
        /* 적는 칸을 고르면 "무슨 글자를 넣을까요?" 만 물어본다 — 문장은 도구가 짓는다 */
        function 값칸그리기(i) {{
          var 통 = document.getElementById('vals_' + i);
          if (!통) return;
          var 줄 = [];
          (고른[i] || []).forEach(function (m, idx) {{
            if (m.indexOf('입력 ') !== 0) return;
            var 칸이름 = m.slice(3).split('=')[0], 값 = m.slice(3).split('=').slice(1).join('=');
            줄.push('<label class="valrow"><span>' + 글자막기(칸이름) + '</span>' +
              '<input type="text" value="' + 글자막기(값) + '" placeholder="예: 1234" ' +
              'oninput="값바꿈(' + i + ',' + idx + ',this)"></label>');
          }});
          통.innerHTML = 줄.length
            ? '<div class="valt">적는 칸에 넣을 글자</div>' + 줄.join('') +
              '<div class="hint" style="margin:var(--spacing-4) 0 0">아이디·비밀번호는 ' +
              '<code>&lt;아이디&gt;</code> · <code>&lt;비번&gt;</code> 라고 두면 앱 정보에 적어 둔 시험 계정이 들어갑니다.</div>'
            : '';
        }}
        function 값바꿈(i, idx, el) {{
          var m = 고른[i][idx];
          고른[i][idx] = '입력 ' + m.slice(3).split('=')[0] + '=' + el.value;
          쓰기(i);
        }}
        function 쓰기(i) {{
          var 칸 = 동작칸(i);
          칸.value = 고른[i].length ? 고른[i].join(' → ') + ' → 기다림 1.2' : '';
          칸.dispatchEvent(new Event('input'));
          표시(i);
        }}
        function 그림고르기(i) {{
          var 줄 = document.getElementById('pick_' + i), 판 = document.getElementById('pickpanel_' + i);
          if (!줄.hidden) {{ 줄.hidden = true; return; }}
          var 나 = 그림자료[i];
          var 왼 = (나.왼쪽 >= 0 && 나.왼쪽 !== i) ? 그림자료[나.왼쪽] : null;
          if (왼 && !왼.그림) 왼 = null;
          var 앞 = 왼 && 나.앞화면;
          var 물음 = !왼 ? '이 화면에서 누를 것을 차례로 누르세요'
                   : (앞 ? '이 화면으로 들어가려면 <b>앞 화면</b> 어디를 누르나요? — 점선 칸을 차례로 누르세요'
                         : '오른쪽 화면이 나오려면 왼쪽 화면 <b>어디</b>를 누르나요? — 점선 칸을 차례로 누르세요');
          판.innerHTML = '<div class="pickq">' + 물음 +
            '<span class="right"><button type="button" class="btn" onclick="지움(' + i + ')">지우기</button> ' +
            '<button type="button" class="btn" onclick="그림고르기(' + i + ')">닫기</button></span></div>' +
            '<div class="figs">' + (!왼 ? 그림그리기(i, 나, '이 화면')
              : 그림그리기(i, 왼, (앞 ? '앞 화면 · ' : '기본 화면 · ') + 왼.이름) + '<div class="figarrow">→</div>' +
                그림그리기(i, 나, (앞 ? '들어갈 화면 · ' : '만들 화면 · ') + 나.이름)) + '</div>' +
            '<div class="vals" id="vals_' + i + '"></div>';
          줄.hidden = false;
          고른[i] = 마디들(동작칸(i).value).filter(function (m) {{ return m.indexOf('기다림') !== 0; }});
          표시(i);
          값칸그리기(i);
        }}
        function 누름(i, b) {{
          var 동작 = b.getAttribute('data-act'), 칸인가 = 동작.slice(-1) === '=';
          고른[i] = 고른[i] || [];
          var at = -1;
          고른[i].forEach(function (m, k) {{
            if (at < 0 && (칸인가 ? m.indexOf(동작) === 0 : m === 동작)) at = k;
          }});
          if (at >= 0) 고른[i].splice(at, 1);
          else 고른[i].push(칸인가 ? 동작 + (b.getAttribute('data-val') || '') : 동작);
          쓰기(i);
          값칸그리기(i);
        }}
        function 지움(i) {{ 고른[i] = []; 쓰기(i); 값칸그리기(i); }}
        /* 틀리게 쓴 줄을 고친 문장으로 바꿔 준다 */
        function 고침(i, b) {{
          var 칸 = 동작칸(i);
          칸.value = b.getAttribute('data-fix');
          칸.dispatchEvent(new Event('input'));
          var 통 = document.getElementById('fixbox_' + i);
          if (통) 통.innerHTML = '<div class="hint" style="margin:var(--spacing-2) 0 0">바꿨습니다</div>';
        }}
      </script>
      <div class="bar"><a class="btn" href="/">← 다시 고르기</a>
        <span class="right"></span>
        <button type="submit" name="그래도" value="1">그대로 진행</button>
        <button class="go" type="submit">다음 — 조건 확인 →</button></div>
    </div></form>"""
    return 껍데기("/초안", 본문, "자동으로 채운 초안이다. 확정은 사람이 한다", 알림)


# ────────────────────────────────────────────────── ③ 조건 확인
def 폰목록():
    try:
        out = subprocess.run([ADB, "devices", "-l"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return []
    폰 = []
    for line in out.splitlines()[1:]:
        if not line.strip() or ("\tdevice" not in line and " device " not in line):
            continue
        아이디 = line.split()[0]
        m = re.search(r"model:(\S+)", line)
        폰.append({"id": 아이디, "이름": (m.group(1).replace("_", " ") if m else 아이디)})
    return 폰


def 깔린앱목록():
    """폰이 꽂혀 있으면 깔린 앱의 속이름을 목록으로 보여 준다(고르기 쉽게)."""
    글 = _adb("shell", "pm", "list", "packages", "-3")
    return sorted(l.replace("package:", "").strip() for l in 글.splitlines() if l.strip())


def _adb(*args):
    try:
        return subprocess.run([ADB, *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _계정칸(작업, 다시촬영=False, 접기=True):
    """아이디·비밀번호를 고쳐 넣는 칸 — ③ 조건과 ④ 촬영에서 같은 것을 쓴다."""
    숨김 = '<input type="hidden" name="다시촬영" value="1">' if 다시촬영 else ""
    단추 = "고쳐서 다시 촬영 →" if 다시촬영 else "고쳐서 다시 해 보기"
    return f"""<form method="post" action="/계정" style="margin-top:var(--spacing-10)">{숨김}
      <label class="f">시험 아이디</label>
      <input type="text" name="시험아이디" class="w-md" autocomplete="off"
             value="{_e(작업.get('시험아이디',''))}">
      <label class="f">시험 비밀번호</label>
      <input type="password" name="시험비밀번호" class="w-md" autocomplete="off"
             value="{_e(작업.get('시험비밀번호',''))}">
      <div class="bar"><button class="go" type="submit">{단추}</button></div></form>"""


def _계정카드(작업):
    """찍기 전에 '시험 계정으로 정말 들어가지나' 를 한 번 해 보는 칸 (매체 공통).

    막지는 않는다 — 못 해 보는 매체(앱·PC 설치형)도 있고, 로그인이 없는 화면도 있다.
    """
    본것 = 작업.get("계정확인") or {}
    됨 = 본것.get("됨")
    계정 = (f"{_e(작업.get('시험아이디'))} · 비밀번호 "
          + ("•" * len(작업.get("시험비밀번호") or "") or '<span class="muted">비어 있음</span>')
          if 작업.get("시험아이디") else '<span class="muted">적지 않음</span>')
    말 = {True: ("✅", "로그인됩니다", "var(--color-green-450)"),
         False: ("⚠️", "로그인이 안 됩니다", "var(--color-text-state-error)"),
         None: ("ℹ️", "미리 해 보지 못했습니다", "var(--color-text-body-tertiary)")}.get(됨) \
        if 본것 else ("", "아직 해 보지 않았습니다", "var(--color-text-body-tertiary)")
    표, 글, 색 = 말
    까닭 = f'<div class="hint" style="margin-top:var(--spacing-4)">{_e(본것.get("까닭",""))}</div>' if 본것 else ""
    고치기 = _계정칸(작업) if 됨 is False else ""
    return f"""
    <div class="card"><h2>시험 계정</h2>
      <table><tbody>
        <tr><td class="muted" style="width:120px">계정</td><td>{계정}</td></tr>
        <tr><td class="muted">한 번 해 본 결과</td>
            <td style="color:{색}">{표} {_e(글)}{까닭}</td></tr>
      </tbody></table>
      <div class="hint">찍기 전에 이 계정으로 한 번 들어가 봅니다. 틀린 계정으로 찍으면
        엉뚱한 화면만 잔뜩 남습니다.</div>
      <form method="post" action="/계정확인">
        <div class="bar"><button type="submit">시험 로그인 해 보기</button>
          <span class="hint" style="margin:0">10초쯤 걸립니다 · 창이 떴다 닫힙니다</span></div>
      </form>{고치기}</div>"""


def 화면_조건(알림=""):
    작업 = 작업읽기()
    if not 작업.get("이름표경로"):
        return 껍데기("/조건", '<div class="card"><p class="muted">먼저 ② 에서 찍을 목록을 저장하세요.</p></div>',
                   "조건 확인")
    if 웹인가(작업):
        return 화면_조건_웹(작업, 알림)
    폰 = 폰목록()
    앱주소 = 작업.get("앱주소", "")
    깔림 = bool(_adb("shell", "pm", "path", 앱주소)) if (폰 and 앱주소) else False
    잠김 = _adb("shell", "dumpsys", "window").find("mDreamingLockscreen=true") >= 0 if 폰 else True

    def 줄(제목, 됨, 설명):
        표 = "✅" if 됨 else "⚠️"
        return (f'<tr><td style="width:34px">{표}</td><td><b>{_e(제목)}</b><div class="hint" '
                f'style="margin:var(--spacing-2) 0 0">{설명}</div></td></tr>')

    폰이름 = 폰[0]["이름"] if 폰 else ""
    검사 = (줄("폰이 연결됐다", bool(폰),
             _e(폰이름) if 폰 else "USB로 꽂고 폰에서 <b>USB 디버깅</b>을 켜 주세요.")
          + 줄("폰 잠금이 풀려 있다", bool(폰) and not 잠김,
               "잠긴 채로는 앱 화면이 찍히지 않습니다. 잠금은 사람이 풀어야 합니다.")
          + 줄("앱이 폰에 깔려 있다", 깔림,
               _e(앱주소) if 앱주소 else "② 에서 앱 주소를 적어 주세요."))

    계정말 = (f"{_e(작업.get('시험아이디'))} · 비밀번호 "
           + ("•" * len(작업.get("시험비밀번호") or "") or '<span class="muted">비어 있음</span>')
           if 작업.get("시험아이디") else '<span class="muted">적지 않음</span>')
    준비됨 = bool(폰) and not 잠김 and 깔림
    본문 = f"""
    <div class="card"><h2>폰 상태</h2><table><tbody>{검사}</tbody></table>
      <div class="bar"><a class="btn" href="/조건">다시 확인</a></div></div>
    {_계정카드(작업)}
    <div class="card"><h2>이렇게 찍습니다</h2>
      <table><tbody>
        <tr><td class="muted" style="width:120px">앱</td><td>{_e(작업.get('앱이름'))} · {_e(앱주소)}</td></tr>
        <tr><td class="muted">폰</td><td>{_e(폰이름) or '<span class="muted">없음</span>'}</td></tr>
        <tr><td class="muted">찍을 화면</td><td>{len(작업.get('초안',[]))}개</td></tr>
        <tr><td class="muted">사진 이름</td><td>{_e(작업.get('서비스코드'))}-AND-번호@상태.png</td></tr>
        <tr><td class="muted">시험 계정</td><td>{계정말}</td></tr>
      </tbody></table>
      <div class="hint">화면 한 장마다 앱을 껐다 켭니다. 화면 수 × 약 10초쯤 걸립니다.
        찍는 동안 {찍는중안내(작업)}</div>
      <form method="post" action="/조건">
        <div class="bar"><a class="btn" href="/초안">← 목록 고치기</a>
          <span class="right"></span>
          <button class="go" type="submit"{'' if 준비됨 else ' disabled'}>전체 촬영 시작 →</button></div>
      </form></div>"""
    return 껍데기("/조건", 본문, "찍기 전에 폰 상태를 확인한다", 알림)


def 브라우저찾기():
    """이미 깔려 있는 크롬·엣지를 빌려 쓴다(따로 내려받지 않는다)."""
    자리 = {
        "Chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                   r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
        "Edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    }
    찾은것 = [이름 for 이름, 길들 in 자리.items() if any(os.path.exists(g) for g in 길들)]
    return 찾은것


def 연장있나():
    """웹을 찍는 연장(Playwright)이 깔려 있는지."""
    try:
        import importlib.util
        return importlib.util.find_spec("playwright") is not None
    except Exception:
        return False


def 화면_조건_웹(작업, 알림=""):
    """웹은 폰을 꽂지 않는다 — 브라우저와 주소만 본다."""
    브라우저 = 브라우저찾기()
    연장 = 연장있나()
    바탕 = 작업.get("기본주소", "")
    주소없는줄 = [r["이름"] for r in 작업.get("초안", []) if not (r.get("주소") or "").strip()]
    주소됨 = bool(바탕) or not 주소없는줄

    def 줄(제목, 됨, 설명):
        표 = "✅" if 됨 else "⚠️"
        return (f'<tr><td style="width:34px">{표}</td><td><b>{_e(제목)}</b><div class="hint" '
                f'style="margin:var(--spacing-2) 0 0">{설명}</div></td></tr>')

    검사 = (줄("브라우저가 있다", bool(브라우저),
             " · ".join(브라우저) if 브라우저 else "크롬이나 엣지를 깔아 주세요.")
          + 줄("웹을 찍는 연장이 있다", 연장,
               "깔려 있습니다." if 연장 else
               "명령창에서 <b>py -3 -m pip install playwright</b> 를 한 번 실행해 주세요.")
          + 줄("주소가 다 적혀 있다", 주소됨,
               _e(바탕) if 바탕 else ("주소가 빈 줄: " + _e(", ".join(주소없는줄))
                                    if 주소없는줄 else "줄마다 전체 주소를 적었습니다.")))

    계정말 = (f"{_e(작업.get('시험아이디'))} · 비밀번호 "
           + ("•" * len(작업.get("시험비밀번호") or "") or '<span class="muted">비어 있음</span>')
           if 작업.get("시험아이디") else '<span class="muted">적지 않음</span>')
    준비됨 = bool(브라우저) and 연장 and 주소됨
    # 다 갖춰졌으면 확인 표를 굳이 보이지 않는다 — 모자란 것이 있을 때만 짚어 준다.
    준비카드 = "" if 준비됨 else f"""
    <div class="card"><h2>아직 모자란 것</h2><table><tbody>{검사}</tbody></table>
      <div class="bar"><a class="btn" href="/조건">다시 확인</a></div></div>"""
    본문 = f"""{준비카드}{_계정카드(작업)}
    <div class="card"><h2>이렇게 찍습니다</h2>
      <table><tbody>
        <tr><td class="muted" style="width:120px">사이트</td><td>{_e(작업.get('앱이름'))} · {_e(바탕) or '<span class="muted">줄마다 전체 주소</span>'}</td></tr>
        <tr><td class="muted">찍을 폭</td><td>{작업.get('찍을폭') or 1440}px <span class="muted">· 시안과 같게</span></td></tr>
        <tr><td class="muted">찍을 화면</td><td>{len(작업.get('초안',[]))}개</td></tr>
        <tr><td class="muted">사진 이름</td><td>{_e(작업.get('서비스코드'))}-WEB-번호@상태.png</td></tr>
        <tr><td class="muted">함께 남기는 것</td><td>값 파일(*.값.json) — 검수는 이 값으로 합니다</td></tr>
        <tr><td class="muted">시험 계정</td><td>{계정말}</td></tr>
      </tbody></table>
      <div class="hint">브라우저가 화면을 하나씩 열어 값을 재고 그림을 남깁니다. 폰은 꽂지 않아도 됩니다.</div>
      <form method="post" action="/조건">
        <div class="bar"><a class="btn" href="/초안">← 목록 고치기</a>
          <span class="right"></span>
          <button class="go" type="submit"{'' if 준비됨 else ' disabled'}>전체 촬영 시작 →</button></div>
      </form></div>"""
    return 껍데기("/조건", 본문, "찍기 전에 브라우저와 주소를 확인한다", 알림)


def 계정한번(작업):
    """적어 둔 시험 계정으로 한 번 로그인해 본다(공통 조각 lib/계정확인.py 가 한다)."""
    본것 = 계정확인.확인({"앱이름": 작업.get("앱이름", ""),
                    "유형": 유형(작업), "플랫폼": 작업.get("유형", ""),
                    "기본주소": 작업.get("기본주소", ""),
                    "화면폭": 작업.get("찍을폭") or 1440,
                    "로그인": 작업.get("로그인", ""),
                    "시험아이디": 작업.get("시험아이디", ""),
                    "시험비밀번호": 작업.get("시험비밀번호", "")})
    본것["때"] = time.strftime("%H:%M")
    return 본것


# ────────────────────────────────────────────────── ④ 전체 촬영
def 촬영시작():
    작업 = 작업읽기()
    폴더이름 = time.strftime("%Y%m%d-%H%M") + "-" + (작업.get("서비스코드") or "APP")
    결과폴더 = 뿌리 / "shots" / 폴더이름
    결과폴더.mkdir(parents=True, exist_ok=True)
    로그 = 결과폴더 / "촬영기록.txt"

    작업["결과폴더"] = str(결과폴더)
    작업쓰기(작업)
    _촬영.update({"진행중": True, "폴더": str(결과폴더), "로그": str(로그)})

    def 돌리기():
        with open(로그, "w", encoding="utf-8") as f:
            subprocess.run([sys.executable, str(뿌리 / "lib" / "runner.py"),
                            작업["이름표경로"], str(결과폴더)],
                           stdout=f, stderr=subprocess.STDOUT, text=True)
        _촬영["진행중"] = False

    threading.Thread(target=돌리기, daemon=True).start()


def 진행줄(글):
    """촬영기록에서 '지금 몇 번째인지'를 읽는다 — `[3/8] 이름 →` 줄과 그 아래 ✗ 를 센다.

    돌아가는 것을 눈으로 볼 수 있게 하려는 것뿐이다(사람이 '멈춘 건가' 하고 기다리지 않게).
    """
    지금, 전부, 이름 = 0, 0, ""
    결과 = []          # 화면마다 True(찍힘)/False(못 찍음)
    for 줄 in (글 or "").splitlines():
        m = re.match(r"\s*\[(\d+)/(\d+)\]\s*(.*?)\s*→", 줄)
        if m:
            지금, 전부, 이름 = int(m.group(1)), int(m.group(2)), m.group(3)
            결과.append(True)
            continue
        if "✗" in 줄 and 결과:
            결과[-1] = False
    return {"지금": 지금, "전부": 전부, "이름": 이름,
            "찍힘": sum(1 for x in 결과 if x), "못찍음": sum(1 for x in 결과 if not x)}


def 진행바(글, 끝남=False):
    """찍는 동안 '몇 번째 / 몇 개'를 막대와 글로 보여 준다."""
    r = 진행줄(글)
    if not r["전부"]:
        return '<div class="hint" style="margin:var(--spacing-8) 0 0">시작하는 중…</div>' if not 끝남 else ""
    찬만큼 = round(100 * (r["전부"] if 끝남 else max(0, r["찍힘"] + r["못찍음"] - 1)) / r["전부"])
    센말 = f'찍은 것 {r["찍힘"]}장' + (f' · 못 찍은 것 {r["못찍음"]}장' if r["못찍음"] else "")
    말 = (f'{r["전부"]}장 다 돌았습니다 · {센말}' if 끝남
         else f'{r["지금"]} / {r["전부"]}번째 — {_e(r["이름"])} <span class="muted">· {센말}</span>')
    return f"""
    <div style="margin:var(--spacing-10) 0 0">
      <div style="height:8px;border-radius:var(--radius-full);background:var(--color-gray-100);overflow:hidden">
        <div style="height:100%;width:{찬만큼}%;background:var(--color-blue-400);transition:width .3s"></div>
      </div>
      <div class="hint" style="margin:var(--spacing-6) 0 0">{말}</div>
    </div>"""


def 화면_촬영():
    작업 = 작업읽기()
    폴더 = 작업.get("결과폴더")
    if not 폴더:
        return 껍데기("/촬영", '<div class="card"><p class="muted">먼저 ③ 에서 촬영을 시작하세요.</p></div>',
                   "전체 촬영")
    폴더 = Path(폴더)
    로그 = 폴더 / "촬영기록.txt"
    글 = 로그.read_text(encoding="utf-8", errors="replace") if 로그.exists() else "시작하는 중…"
    목록파일 = 폴더 / "찍은목록.json"
    # 목록을 못 남기고 끝났어도 '끝난 것'으로 본다 — 아니면 3초마다 새로고침만 끝없이 돈다.
    끝남 = not _촬영["진행중"]

    막힘 = ""
    막힌줄 = [l for l in 글.splitlines() if l.startswith(계정확인.막힘표)]
    if 막힌줄 and not 목록파일.exists():
        까닭 = 막힌줄[0].split(":", 1)[-1].strip()
        잠김 = "(잠김)" in 막힌줄[0]
        막힘 = (f'<div class="card"><div class="err" style="margin:0 0 var(--spacing-10)">'
              f'<b>시험 계정으로 로그인이 안 돼 촬영을 멈췄습니다.</b><br>{_e(까닭)}</div>'
              + ('<div class="hint" style="margin-top:0">계정이 잠긴 것 같습니다. '
                 '잠시 뒤에 다시 해 보세요.</div>' if 잠김 else
                 '<div class="hint" style="margin-top:0">아이디·비밀번호를 고치면 '
                 '그 자리에서 다시 찍기 시작합니다.</div>')
              + _계정칸(작업, 다시촬영=True) + '</div>')

    결과 = ""
    if 목록파일.exists():
        목록 = json.loads(목록파일.read_text(encoding="utf-8"))
        사진 = ""
        for s in 목록.get("찍힌것", []):
            사진 += (f'<figure><img src="/사진/{_e(s["파일"])}" alt="{_e(s["화면이름"])}">'
                   f'<figcaption>{_e(s["화면이름"])}<br>{_e(s["파일"])}</figcaption></figure>')
        못 = 목록.get("못찍은것", [])
        결과 = (f'<div class="ok">찍힌 것 {len(목록.get("찍힌것",[]))}장'
              + (f' · 못 찍은 것 {len(못)}장' if 못 else "") + "</div>")
        if 못:
            못목록 = "".join(f'<tr><td>{_e(m["화면이름"])}</td><td class="muted">{_e(m["까닭"])}</td></tr>'
                          for m in 못)
            결과 += f'<div class="card"><h2>못 찍은 화면</h2><table><tbody>{못목록}</tbody></table></div>'
        결과 += f'<div class="card"><h2>찍힌 사진</h2><div class="shots">{사진}</div></div>'

    보냄 = 작업.get("접수결과")
    고를칸 = ""
    if 목록파일.exists():
        for s2 in json.loads(목록파일.read_text(encoding="utf-8")).get("찍힌것", []):
            고를칸 += (f'<label><input type="checkbox" name="사진" value="{_e(s2["파일"])}" checked>'
                    f'<span class="dim" style="margin:0">{_e(s2["화면번호"])}</span>'
                    f'<span class="nm">{_e(s2.get("화면이름") or s2.get("상태",""))}</span>'
                    f'<span class="dim">{_e(s2.get("상태",""))}</span></label>')
    보내기 = ""
    if 끝남 and not 보냄:
        보내기 = f"""
        <div class="card"><h2>검수로 보내기</h2>
          <div class="hint" style="margin-top:0">보낼 사진만 골라 주세요.
            상태마다 검수 페이지 한 장으로 들어갑니다.</div>
          <form method="post" action="/접수" id="보내기폼">
            <div class="rows" style="margin:var(--spacing-10) 0 0">{고를칸}</div>
            <div class="bar"><button class="go" type="submit">검수로 보낸 후 포털 열기 →</button>
              <span class="hint" style="margin:0">포털이 꺼져 있으면 먼저 켜 주세요.</span></div>
          </form>
          <script>
          // 보내기와 포털 열기를 한 번에. 새 창은 **누른 그 순간** 열어 둬야 팝업 막기에 안 걸린다.
          document.getElementById('보내기폼').addEventListener('submit', function (e) {{
            var 창 = window.open('', '_blank');
            if (!창) return;                       // 팝업이 막혔으면 예전처럼 폼 그대로 보낸다
            e.preventDefault();
            // URLSearchParams 로 보낸다 — 서버가 읽는 모양(urlencoded)이 폼을 그냥 보낼 때와 같아야 한다.
            fetch('/접수?json=1', {{ method: 'POST', body: new URLSearchParams(new FormData(this)) }})
              .then(function (r) {{ return r.json(); }})
              .then(function (d) {{
                if (d && d.포털주소) {{ 창.location = d.포털주소; }} else {{ 창.close(); }}
                location.href = '/촬영';
              }})
              .catch(function () {{ 창.close(); location.href = '/촬영'; }});
          }});
          </script></div>"""
    elif 보냄:
        쪽 = " · ".join(_e(x) for x in 보냄.get("페이지", []))
        보내기 = f"""
        <div class="card"><h2>검수로 보냈습니다</h2>
          <table><tbody>
            <tr><td class="muted" style="width:110px">화면</td>
                <td><b>{_e(보냄.get("화면"))}</b> {_e(보냄.get("화면이름"))}</td></tr>
            <tr><td class="muted">검수 페이지</td><td>{쪽}</td></tr>
          </tbody></table>
          <div class="bar"><a class="btn" href="{_e(보냄.get("포털주소"))}" target="_blank">
            포털 다시 열기 →</a>
            <span class="hint" style="margin:0">보낼 때 포털을 새 창으로 열었습니다.</span></div>
        </div>"""

    끝남 = 끝남 or bool(막힘)          # 로그인이 막혀 멈췄으면 더 기다리지 않는다
    # 다 돌기 전에 멎었으면(목록도 못 남겼으면) 그렇다고 말한다 — '다 됐다'고 하지 않는다.
    멎음 = (끝남 and not 목록파일.exists() and not 막힘)
    if 멎음:
        결과 = ('<div class="card"><div class="err" style="margin:0">'
              '<b>촬영이 끝까지 가지 못하고 멎었습니다.</b><br>'
              '아래 기록의 마지막 줄을 보고 다시 시작해 주세요.</div></div>') + 결과
    새로고침 = "" if 끝남 else '<meta http-equiv="refresh" content="3">'
    본문 = f"""{새로고침}
    <div class="card"><h2>{('멎었습니다' if 멎음 else '끝났습니다') if 끝남 else '찍는 중…'}
      <span class="muted">· {_e(폴더.name)}</span></h2>
      {진행바(글, 끝남 and not 멎음)}
      <pre class="log">{_e(글)}</pre>
      <div class="bar">{'<a class="btn" href="/">처음으로</a>' if 끝남 else f'<span class="hint">{찍는중안내(작업)}</span>'}</div>
    </div>{막힘}{보내기}{결과}"""
    return 껍데기("/촬영", 본문, "찍고 이름 붙이는 중")


# ────────────────────────────────────────────────── 이름표 저장
def 이름표쓰기(작업):
    웹 = 웹인가(작업)
    줄 = ["# 자동 캡쳐 사이트가 만든 이름표 — 손으로 고쳐도 된다.",
         f"앱이름: {작업['앱이름']}",
         "플랫폼: web" if 웹 else "플랫폼: android",
         f"유형: {유형(작업)}"]        # 유형표(lib/매체.py) 열쇠 — 웹 둘을 갈라 본다
    if 웹:
        줄 += [f"기본주소: {작업.get('기본주소','')}",
              f"화면폭: {작업.get('찍을폭') or 1440}"]
    else:
        줄 += [f"앱주소: {작업['앱주소']}"]
    줄 += [f"서비스코드: {작업['서비스코드']}",
          f"로그인: {작업.get('로그인','없음') or '없음'}"]
    들머리 = (작업.get("들어가는길") or "").strip()
    if 들머리:
        # 로그인 화면을 안 찍고 홈·메뉴만 찍을 때 지나는 길(lib/들어가는길.py)
        줄 += [f"들어가는길: {들머리}"]
    줄 += ["", "화면:"]
    for r in 작업["초안"]:
        줄 += [f'  - 번호: "{r["번호"]}"', f'    이름: {r["이름"]}',
              f'    상태: {r["상태"]}']
        줄 += ([f'    주소: {r.get("주소","")}'] if 웹 else [f'    누를것: {r["누를것"]}'])
        줄 += [f'    동작: {r.get("동작") or "-"}',
              f'    이어서: {r.get("이어서", "아니오")}']
    코드 = re.sub(r"[^A-Za-z0-9_-]", "", 작업["서비스코드"]).lower() or "app"
    경로 = 뿌리 / "apps" / f"{코드}.yaml"
    경로.write_text("\n".join(줄) + "\n", encoding="utf-8")
    return str(경로)


# ────────────────────────────────────────────────── 웹 서버
class 손님(BaseHTTPRequestHandler):
    # 브라우저가 '미리 열어 두는' 연결이 아무 말 없이 붙어 있어도 오래 붙잡지 않는다.
    timeout = 20

    def do_GET(self):
        길 = unquote(urlparse(self.path).path)
        q = parse_qs(urlparse(self.path).query)
        if 길 == "/":
            if "페이지" in q:
                작업 = 작업읽기()
                작업["고른페이지"] = q["페이지"][0]
                작업쓰기(작업)
                return self._이동("/")
            return self._html(화면_디자인(q.get("오류", [""])[0]))
        if 길 == "/초안":
            return self._html(화면_초안())
        if 길 == "/메뉴훑기/상태":
            것 = 메뉴훑기.상태()
            것["말줄"] = _메뉴띠말(것)
            return self._json(것)
        if 길 == "/조건":
            return self._html(화면_조건())
        if 길 == "/촬영":
            return self._html(화면_촬영())
        if 길 == "/비우기":
            작업 = 작업읽기()
            for k in ("온곳", "고른화면", "초안", "파일", "접수결과"):
                작업.pop(k, None)
            작업쓰기(작업)
            return self._이동("/")
        if 길.startswith("/받은그림/"):
            fp = 여기 / "디자인" / Path(길[len("/받은그림/"):]).name
            if fp.exists() and fp.suffix == ".png":
                return self._png(fp.read_bytes())
        if 길.startswith("/안내그림/"):
            fp = 여기 / "그림" / Path(길[len("/안내그림/"):]).name
            if fp.exists() and fp.suffix == ".png":
                return self._png(fp.read_bytes())
        if 길.startswith("/사진/"):
            폴더 = 작업읽기().get("결과폴더")
            이름 = Path(길[len("/사진/"):]).name
            fp = Path(폴더) / 이름 if 폴더 else None
            if fp and fp.exists() and fp.suffix == ".png":
                return self._png(fp.read_bytes())
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):                     # 플러그인 창이 미리 물어보는 것
        self.send_response(204)
        self._곁들이기()
        self.end_headers()

    def _곁들이기(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _받기(self, 자료):
        """Figma에서 드래그로 고른 화면 꾸러미를 받아 ②로 넘긴다."""
        꾸러미 = json.loads(자료.decode("utf-8"))
        그림자리 = 여기 / "디자인"
        그림자리.mkdir(exist_ok=True)
        고른화면 = []
        for i, f in enumerate(꾸러미.get("화면들", []), 1):
            줄 = {k: f.get(k) for k in ("id", "이름", "폭", "높이", "x", "y")}
            줄["속"] = f.get("속") or []
            줄["페이지"] = 꾸러미.get("페이지이름", "")
            줄["페이지차례"] = 0
            줄["묶음"] = ""
            if f.get("그림"):
                이름 = f"{i:03d}.png"
                (그림자리 / 이름).write_bytes(bytes(f["그림"]))
                줄["디자인그림"] = str(그림자리 / 이름)
            if isinstance(f.get("검수요소"), list):
                # 검수 포털의 자동 검수용 요소 목록 — 크므로 파일로 두고 자리만 적는다.
                요소파일 = 그림자리 / f"{i:03d}_elements.json"
                요소파일.write_text(json.dumps({"틀": f.get("틀") or {}, "설정": f.get("검수설정"), "요소": f["검수요소"]},
                                            ensure_ascii=False), encoding="utf-8")
                줄["검수요소파일"] = str(요소파일)
            고른화면.append(줄)

        작업 = 작업읽기()
        작업["파일"] = {"파일이름": 꾸러미.get("파일이름", ""),
                     "파일열쇠": 꾸러미.get("파일열쇠", ""),
                     "페이지": []}
        작업["파일주소"] = ""
        작업["온곳"] = "figma-플러그인"
        작업["유형"] = 꾸러미.get("플랫폼") or "android"
        작업["찍을폭"] = int(꾸러미.get("찍을폭") or 0)
        작업["고른화면"] = 고른화면
        작업["초안"] = 초안만들기.만들기(고른화면, 작업.get("유형"))
        # 전에 한 번 적어 둔 개발 주소는 다시 적지 않는다 — 빈 칸만 기억으로 채운다.
        주소기억.채우기(작업.get("앱이름", ""), 작업["초안"])
        작업.pop("접수결과", None)
        작업.setdefault("앱이름", "")
        작업.setdefault("서비스코드", "")
        작업.setdefault("앱주소", "")
        작업.setdefault("기본주소", "")
        작업쓰기(작업)
        return len(고른화면)

    def do_POST(self):
        길 = unquote(urlparse(self.path).path)
        if 길 in ("/받기", "/pick"):
            자료 = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                수 = self._받기(자료)
            except Exception as e:
                self.send_response(400)
                self._곁들이기()
                self.end_headers()
                return self.wfile.write(str(e).encode("utf-8"))
            self.send_response(200)
            self._곁들이기()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return self.wfile.write(json.dumps({"받음": 수}).encode("utf-8"))

        폼 = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))

        def 한개(k, d=""):
            return 폼.get(k, [d])[0].strip()

        if 길 == "/열쇠":
            토큰 = 한개("토큰")
            if 토큰:
                p = Path(디자인.열쇠파일)
                p.write_text(토큰 + "\n", encoding="utf-8")
                os.chmod(p, 0o600)
            return self._이동("/")

        if 길 == "/디자인":
            주소 = 한개("주소")
            try:
                파일 = 디자인.파일읽기(주소)
            except 디자인.읽기오류 as e:
                return self._html(화면_디자인(str(e)))
            작업 = 작업읽기()
            작업.update({"파일주소": 주소, "파일": 파일,
                       "고른페이지": (파일["페이지"][0]["id"] if 파일["페이지"] else ""),
                       "고른화면": [], "초안": []})
            작업쓰기(작업)
            return self._이동("/")

        if 길 == "/고르기":
            작업 = 작업읽기()
            고름 = 폼.get("화면", [])
            이페이지 = 한개("페이지")
            페이지 = next((p for p in 작업.get("파일", {}).get("페이지", [])
                       if p["id"] == 이페이지), None)
            페이지들 = 작업.get("파일", {}).get("페이지", [])
            차례 = next((i for i, p in enumerate(페이지들) if p["id"] == 이페이지), 0)
            방금 = [dict(f, 페이지=이페이지, 페이지차례=차례)
                  for f in (페이지["화면"] if 페이지 else []) if f["id"] in 고름]
            남긴것 = [f for f in 작업.get("고른화면", []) if f.get("페이지") != 이페이지]
            골라진 = 남긴것 + 방금
            if not 골라진:
                return self._html(화면_디자인("화면을 한 개 이상 고르세요."))
            작업["고른페이지"] = 이페이지
            작업["고른화면"] = 골라진
            작업["초안"] = 초안만들기.만들기(골라진, 작업.get("유형"))
            주소기억.채우기(작업.get("앱이름", ""), 작업["초안"])
            작업.setdefault("앱이름", "")
            작업.setdefault("서비스코드", "")
            작업.setdefault("앱주소", "")
            작업쓰기(작업)
            return self._이동("/초안")

        if 길 == "/초안":
            작업 = 작업읽기()
            웹 = 웹인가(작업)
            틀린것, 빈줄 = [], []
            for i, r in enumerate(작업.get("초안", [])):
                for k in ("번호", "이름", "상태") + (() if 웹 else ("누를것",)):
                    v = " ".join(한개(f"{k}_{i}").split())   # 여러 줄 칸 — 줄바꿈은 공백으로
                    if v:
                        r[k] = v
                if 웹:
                    r["주소"] = 한개(f"주소_{i}")
                # 동작 칸은 여러 줄로 적을 수 있다 — 줄바꿈은 화살표 앞뒤 공백과 같이 다룬다.
                이전동작 = " ".join((r.get("동작") or "").split())
                r["동작"] = " ".join(한개(f"동작_{i}").split())
                if r["동작"] != 이전동작:
                    r["근거"] = ""              # 사람이 고쳤으면 엔진이 짚은 근거는 더 이상 맞지 않는다
                까닭 = 동작말.확인(r["동작"], 유형(작업))
                앞줄 = 작업["초안"][i - 1] if i else None
                # 앱은 앞 화면에 이어 찍으므로 동작이 비면 같은 사진이 나온다.
                # 웹은 화면마다 주소가 달라서, 주소까지 같을 때만 같은 사진이 된다.
                같아짐 = ((앞줄 is not None and (r.get("주소") or "") == (앞줄.get("주소") or ""))
                       if 웹 else r.get("이어서") == "예")
                if 까닭:
                    틀린것.append(f"{i+1}번째 줄 — {까닭}")
                elif 같아짐 and not r["동작"].strip():
                    빈줄.append((i + 1, f"{i+1}번째 줄 · {r['이름']}"))
            작업["앱이름"] = 한개("앱이름") or "이름없는 앱"
            작업["서비스코드"] = re.sub(r"[^A-Za-z0-9_-]", "", 한개("서비스코드")).upper()
            if 웹:
                # 주소는 유형표가 정한 대로 다듬는다 — 웹은 끝 빗금을 떼지 않는다(뗐더니 404 를 찍었다).
                작업["기본주소"] = 매체.주소다듬기(한개("기본주소"), 유형(작업))
                작업["찍을폭"] = int(re.sub(r"[^0-9]", "", 한개("화면폭")) or 0) or 1440
            else:
                작업["앱주소"] = 한개("앱주소")
            작업["시험아이디"] = 한개("시험아이디")
            작업["시험비밀번호"] = 한개("시험비밀번호")
            작업["들어가는길"] = 한개("들어가는길")     # 로그인 화면을 안 찍을 때 지나는 길(앱)
            if 웹:
                # 이름을 이제 적었을 수도 있다 — 빈 칸을 한 번 더 채우고, 적힌 주소는 기억에 쌓는다.
                주소기억.채우기(작업["앱이름"], 작업["초안"])
                주소기억.적어두기(작업["앱이름"], 작업["초안"])
            # 로그인 여부는 따로 묻지 않는다 — 시험 계정을 적었으면 로그인이 있는 앱이다
            작업["로그인"] = "필요" if 작업["시험아이디"] else "없음"
            작업쓰기(작업)
            if 빈줄 and 한개("그래도") != "1":
                return self._html(화면_초안(
                    '<div class="err">아래 줄은 <b>동작이 비어 있어</b> 앞 장과 '
                    '똑같은 사진이 찍힙니다.<br>'
                    + "<br>".join(f'<a class="jump" href="#줄{n}">{_e(t)}</a>' for n, t in 빈줄)
                    + '<div style="margin-top:var(--spacing-8)">그 상태를 만드는 동작을 적어 주세요. '
                      '일부러 같은 화면을 두 번 찍는 것이면 아래 단추를 누르세요.</div>'
                    + _그대로단추() + '</div>'))
            if 틀린것:
                return self._html(화면_초안('<div class="err">동작을 알아듣지 못했습니다.<br>'
                                        + "<br>".join(_e(t) for t in 틀린것) + '</div>'))
            if not 작업["서비스코드"]:
                return self._html(화면_초안('<div class="err">서비스 코드가 비었습니다. '
                                        '사진 이름 앞에 붙는 글자(영문·숫자)를 적어 주세요 — 예: UV.</div>'))
            if 웹:
                주소없는줄 = [f'{n}번째 줄 · {r["이름"]}' for n, r in enumerate(작업["초안"], 1)
                          if not (r.get("주소") or "").strip()]
                if not 작업["기본주소"] and 주소없는줄:
                    return self._html(화면_초안('<div class="err">기본 주소가 비었습니다. '
                                            '사이트 주소(예: https://dev.example.com)를 적거나, '
                                            '줄마다 전체 주소를 적어 주세요.</div>'))
                if 주소없는줄 and not 작업["기본주소"]:
                    return self._html(화면_초안('<div class="err">주소가 빈 줄이 있습니다.<br>'
                                            + "<br>".join(_e(t) for t in 주소없는줄) + '</div>'))
            elif not 작업["앱주소"]:
                return self._html(화면_초안('<div class="err">앱 주소가 비었습니다. '
                                        '안드로이드 앱의 속이름(예: kr.co.s1.samsungbus)을 적어 주세요.</div>'))
            빠진계정 = [n for n, r in enumerate(작업["초안"], 1)
                    if ("<아이디>" in (r.get("동작") or "") and not 작업["시험아이디"])
                    or (("<비번>" in (r.get("동작") or "") or "<틀린비번>" in (r.get("동작") or ""))
                        and not 작업["시험비밀번호"])]
            if 빠진계정 and 한개("그래도") != "1":
                return self._html(화면_초안(
                    '<div class="err">아래 줄은 <b>로그인이 필요한 동작</b>인데 '
                    '<b>시험 아이디·비밀번호</b>가 비어 있습니다 — '
                    + ", ".join(f"{n}번째 줄" for n in 빠진계정)
                    + '<div style="margin-top:var(--spacing-8)">위 <b>앱 정보</b>에 검수용 시험 계정을 적어 주세요. '
                      '로그인 없이 그냥 찍을 것이면 아래 단추를 누르세요.</div>'
                    + _그대로단추() + '</div>'))
            앱사전.적어두기(작업["앱이름"], 작업["서비스코드"], 작업.get("앱주소", ""),
                       작업["로그인"], 작업["시험아이디"], 작업["시험비밀번호"],
                       작업.get("기본주소", ""), 작업.get("찍을폭", ""),
                       작업.get("들어가는길", ""))
            작업["이름표경로"] = 이름표쓰기(작업)
            작업쓰기(작업)
            return self._이동("/조건")

        if 길 == "/접수":
            물음 = parse_qs(urlparse(self.path).query)
            그릇 = 물음.get("json", [""])[0] == "1"     # 단추 하나로 보내고 바로 포털을 여는 길
            작업 = 작업읽기()
            try:
                작업["접수결과"] = 접수하기.접수(작업.get("결과폴더", ""), 작업,
                                          폼.get("사진", []))
                작업쓰기(작업)
            except 접수하기.접수오류 as e:
                if 그릇:
                    return self._json({"탈": str(e)})
                return self._html(껍데기("/촬영", "", "검수로 보내기",
                                     f'<div class="err">{_e(str(e))}</div>'
                                     + '<div class="card"><a class="btn" href="/촬영">← 돌아가기</a></div>'))
            if 그릇:
                return self._json({"포털주소": 작업["접수결과"].get("포털주소", "")})
            return self._이동("/촬영")

        if 길 == "/조건":
            작업 = 작업읽기()
            작업["조건확인"] = True
            작업쓰기(작업)
            촬영시작()
            return self._이동("/촬영")

        if 길 == "/메뉴훑기":
            # '다시 읽기' — 기억을 무시하고 사이트를 한 번 더 훑는다.
            메뉴훑기.자동시작(작업읽기(), 다시=True)
            return self._json({"시작": True})

        if 길 == "/계정확인":
            작업 = 작업읽기()
            작업["계정확인"] = 계정한번(작업)
            작업쓰기(작업)
            return self._이동("/조건")

        if 길 == "/계정":
            # 틀린 계정을 고쳐 넣는 곳 — ③ 조건과 ④ 촬영이 같은 칸을 쓴다.
            작업 = 작업읽기()
            작업["시험아이디"] = 한개("시험아이디")
            작업["시험비밀번호"] = 한개("시험비밀번호")
            작업["로그인"] = "필요" if 작업["시험아이디"] else "없음"
            앱사전.적어두기(작업.get("앱이름", ""), 작업.get("서비스코드", ""), 작업.get("앱주소", ""),
                       작업["로그인"], 작업["시험아이디"], 작업["시험비밀번호"],
                       작업.get("기본주소", ""), 작업.get("찍을폭", ""),
                       작업.get("들어가는길", ""))
            작업["계정확인"] = 계정한번(작업)
            작업쓰기(작업)
            if 한개("다시촬영") == "1" and 작업["계정확인"].get("됨") is not False:
                촬영시작()
                return self._이동("/촬영")
            return self._이동("/조건")

        self.send_response(404)
        self.end_headers()

    def _png(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, 본문, code=200):
        data = 본문.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _이동(self, 길):
        self.send_response(303)
        self.send_header("Location", quote(길))   # 한글 주소는 그대로 못 담는다
        self.end_headers()

    def _json(self, 것, code=200):
        data = json.dumps(것, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class _한사람씩아닌서버(ThreadingHTTPServer):
    """손님을 **한 사람씩** 받지 않는다.

    크롬은 사진 여러 장을 한꺼번에 받으려고 연결을 여러 개 열고, 쓰지도 않을 연결을
    미리 열어 두기도 한다. 한 사람씩만 받는 서버는 그 빈 연결 하나에 붙잡혀 통째로 멈춘다
    — 촬영이 끝나고 사진이 우르르 걸리는 자리에서 사이트가 먹통이 되던 까닭이다(2026-09-14).
    """
    daemon_threads = True


class _여섯(_한사람씩아닌서버):
    address_family = socket.AF_INET6      # localhost 가 ::1 로 풀리는 경우 대비


def main():
    # 기본은 내 PC에서만. 같은 망의 다른 PC에서도 열려면 QA_CAPTURE_BIND=0.0.0.0 으로 켠다.
    묶을자리 = BIND or "127.0.0.1"
    보일주소 = 묶을자리 if not 공유중 else _내주소()
    print(f"자동 캡쳐 사이트 → http://{보일주소}:{PORT}   (끄려면 Ctrl+C)")
    try:                                   # 127.0.0.1 과 ::1 둘 다 받는다(Figma 플러그인용)
        여섯 = _여섯(("::1", PORT), 손님)
        threading.Thread(target=여섯.serve_forever, daemon=True).start()
    except OSError:
        pass
    _한사람씩아닌서버((묶을자리, PORT), 손님).serve_forever()


def _어디서열리나():
    """아래쪽에 적는 한 줄. 동료 공유를 켰는지에 따라 다르다."""
    if 공유중:
        return f"같은 사무실 네트워크에서 열린다({_내주소()}:{PORT})"
    return f"내 PC에서만 열린다(127.0.0.1:{PORT})"


def _내주소():
    """같은 망의 다른 PC가 칠 주소를 알려 주기만 한다(바깥으로 보내지 않는다)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.0.1", 9))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    main()
