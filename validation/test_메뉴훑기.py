"""메뉴 훑기 — 로그인해서 메뉴를 읽고, 시안과 닮은 화면을 스스로 짚는지 본다.

진짜 브라우저로 진짜(가짜로 띄운) 사이트를 돈다. 바깥 통신은 없다.
"""
import http.server
import os
import socketserver
import sys
import tempfile
import threading
from pathlib import Path

뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(뿌리, "capture-app", "site"))
sys.path.insert(0, os.path.join(뿌리, "capture-app", "lib"))

import 메뉴훑기  # noqa: E402
import webshot  # noqa: E402

잰것 = []


def 같나(무엇, 실제, 바람):
    잰것.append((무엇, 실제 == 바람, f"{실제!r} ≠ {바람!r}"))


def 참인가(무엇, 실제):
    잰것.append((무엇, bool(실제), f"{실제!r}"))


# ── 가짜 사이트 ──────────────────────────────────────────────
쪽들 = {
    "/": """<h1>로그인</h1>
      <form method="get" action="/home">
        <input name="아이디" placeholder="아이디">
        <input name="비밀번호" type="password" placeholder="비밀번호">
        <button type="submit">로그인</button></form>""",
    "/login": """<h1>로그인</h1>
      <form method="get" action="/home">
        <input name="아이디" placeholder="아이디">
        <input name="비밀번호" type="password" placeholder="비밀번호">
        <button type="submit">로그인</button></form>""",
    "/home": """<h1>홈</h1><nav><a href="/home">홈</a> <a href="/notice">공지사항</a>
      <a href="/archive">자료실</a> <a href="/mypage">내 정보</a></nav>
      <div style="height:200px;background:linear-gradient(90deg,#123,#abc)"></div>
      <p>오늘의 안내입니다.</p>""",
    "/notice": """<h1>공지사항</h1><nav><a href="/home">홈</a> <a href="/notice">공지사항</a></nav>
      <table border=1><tr><th>번호</th><th>제목</th></tr>
      <tr><td>1</td><td>점검 안내</td></tr><tr><td>2</td><td>휴무 안내</td></tr></table>""",
    "/archive": """<h1>자료실</h1><nav><a href="/home">홈</a> <a href="/archive">자료실</a></nav>
      <ul><li>사용 설명서</li><li>양식 모음</li></ul>
      <div style="height:120px;background:#eee"></div>""",
    "/mypage": """<h1>내 정보</h1><nav><a href="/home">홈</a></nav>
      <dl><dt>이름</dt><dd>홍길동</dd><dt>부서</dt><dd>디자인</dd></dl>""",
}


class 손님(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        길 = self.path.split("?")[0]
        속 = 쪽들.get(길)
        if 속 is None:
            self.send_response(404)
            self.end_headers()
            return
        시안 = "시안=1" in self.path
        글 = (f"<!doctype html><meta charset=utf-8><title>{길}</title>"
              f"<body style='font-family:sans-serif;margin:24px;"
              f"{'letter-spacing:.5px;' if 시안 else ''}'>{속}</body>").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(글)))
        self.end_headers()
        self.wfile.write(글)

    def log_message(self, *a):
        pass


서버 = socketserver.TCPServer(("127.0.0.1", 0), 손님)
포트 = 서버.server_address[1]
threading.Thread(target=서버.serve_forever, daemon=True).start()
바탕 = f"http://127.0.0.1:{포트}"

임시 = Path(tempfile.mkdtemp())
메뉴훑기.사전파일 = 임시 / "메뉴사전.json"

# ── 시안 그림 만들기 (같은 화면을 조금 다르게 그린 것) ──────────
sync_playwright = webshot.연장가져오기()
시안파일 = {}
with sync_playwright() as 연장:
    브, _ = webshot.브라우저켜기(연장, 보이기=False)
    쪽 = 브.new_context(viewport={"width": 1000, "height": 700}).new_page()
    for 길 in ("/home", "/notice", "/mypage"):
        쪽.goto(f"{바탕}{길}?시안=1", wait_until="load")
        파일 = 임시 / f"시안{길.strip('/')}.png"
        파일.write_bytes(쪽.screenshot(full_page=True))
        시안파일[길] = 파일
    webshot.브라우저끄기(브)

작업 = {
    "앱이름": "시험사이트", "유형": "web", "기본주소": 바탕, "찍을폭": 1000,
    "로그인": "필요", "시험아이디": "tester", "시험비밀번호": "pw1234",
    "초안": [
        {"이름": "홈", "디자인이름": "웹_홈_기본", "디자인그림": str(시안파일["/home"])},
        {"이름": "공지사항", "디자인이름": "웹_공지사항_기본", "디자인그림": str(시안파일["/notice"])},
        {"이름": "내 정보", "디자인이름": "웹_내정보_기본", "디자인그림": str(시안파일["/mypage"])},
    ],
}

된다, 까닭 = 메뉴훑기.돌만한가(작업)
같나("계정·주소가 차 있으면 돈다", (된다, 까닭), (True, ""))
같나("계정이 비면 돌지 않는다",
   메뉴훑기.돌만한가(dict(작업, 시험아이디="", 시험비밀번호=""))[0], False)
같나("웹이 아니면 돌지 않는다", 메뉴훑기.돌만한가(dict(작업, 유형="android"))[0], False)

메뉴들 = 메뉴훑기.한바퀴(작업)
이름들 = [m["이름"] for m in 메뉴들]
참인가("메뉴를 읽어 온다", len(메뉴들) >= 4)
참인가("공지사항 메뉴를 찾았다", any("공지" in n for n in 이름들))
참인가("로그아웃 같은 것은 읽지 않는다", not any("로그아웃" in n for n in 이름들))

짝 = 메뉴훑기.상태()["짝"]

같나("시안 3장을 다 짚었다", len(짝), 3)
같나("홈 시안 → 홈 주소", 짝.get("0", {}).get("주소"), "/home")
같나("공지 시안 → 공지 주소", 짝.get("1", {}).get("주소"), "/notice")
같나("내 정보 시안 → 내 정보 주소", 짝.get("2", {}).get("주소"), "/mypage")
바른것 = {"0": "/home", "1": "/notice", "2": "/mypage"}
참인가("확정으로 짚은 것은 하나 이상이다", any(하나.get("확정") for 하나 in 짝.values()))
참인가("확정으로 짚은 것은 틀리지 않는다",
    all(하나["주소"] == 바른것[i] for i, 하나 in 짝.items() if 하나.get("확정")))
참인가("애매한 것은 확정하지 않는다(사람이 본다)",
    all(하나.get("확정") or 하나.get("닮음", 0) < 72 for 하나 in 짝.values()))

기억 = 메뉴훑기.기억읽기("시험사이트")
참인가("다음을 위해 기억해 둔다", len(기억.get("메뉴") or []) >= 4)

# ── 애매하면 짚지 않는다 ────────────────────────────────────
가짜메뉴 = [{"이름": "가", "주소길": "/가", "지문": [0.5] * 256},
        {"이름": "나", "주소길": "/나", "지문": [0.5] * 256}]
같나("닮음이 없으면 비워 둔다",
   메뉴훑기._짝맞추기([(0, "무엇", [((i * 37) % 11) / 10 for i in range(256)])], 가짜메뉴)
   .get("0", {}).get("확정"), False)

서버.shutdown()

틀린것 = [(무엇, 말) for 무엇, 됐나, 말 in 잰것 if not 됐나]
for 무엇, 됐나, 말 in 잰것:
    print(("  ✓ " if 됐나 else "  ✗ ") + 무엇 + ("" if 됐나 else f" — {말}"))
print(f"\n{len(잰것) - len(틀린것)}/{len(잰것)} 통과")
sys.exit(1 if 틀린것 else 0)
