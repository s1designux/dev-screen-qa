"""포털 문지기 — 디자인그룹원만 들어오고, 들어온 사람 이름이 이력에 남는다.

river 확정 2026-09-28:
- 계정은 **관리자가 직접 만든다.** 가입 신청·승인 절차는 만들지 않는다.
- 들어오고 나간 일은 **지우지 않고 쌓는다**(CLAUDE.md 2번-3) — `account_event` 는 append-only 다.
- 권한은 둘뿐이다: **관리자**(사람 관리까지) · **그룹원**(검수만).

여기서 하는 일:
  ① 로그인 화면 한 장(`/login`) — 시안 `웹_로그인 화면`(SW-UX-GUIDE V3.0, 2601:21357) 그대로.
  ② 문지기 — 로그인하지 않았으면 어느 주소로 와도 로그인 화면으로 보낸다.
  ③ 계정 관리(`/accounts`) — 관리자만. 사람 추가 · 권한 바꾸기 · 사용 중지 · 비밀번호 초기화.
  ④ 내 계정(`/account`) — 누구나 자기 비밀번호를 바꾼다.

**열어 두는 길**은 넷뿐이다: 그림·CSS·JS(`/assets/`), 켜짐 확인(`/__rev`), 기계가 부르는 `/api/`
(피그마 시안 통로·검수 규칙 배선 — 사람이 로그인할 창이 없다), 그리고 로그인 화면 자신.

비밀번호는 **되돌릴 수 없게** 굳혀 둔다(pbkdf2-sha256, 파이썬 표준 내장 · 추가 설치 0).
잊으면 관리자가 임시 비밀번호로 초기화하고, 그 사람이 처음 들어올 때 새로 정한다.
"""
import hashlib
import hmac
import html
import os
import threading
import uuid as uuidmod
from datetime import datetime, timedelta
from urllib.parse import parse_qs, quote, urlparse

import db as dbmod
import s1_tokens

반복 = 210_000                      # pbkdf2 되풀이 횟수
쿠키 = "qa_sid"                     # 들어온 표
아이디쿠키 = "qa_id"                 # '아이디 저장' 체크했을 때만
머문시간 = timedelta(hours=12)       # 마지막 움직임에서 이만큼 지나면 다시 로그인
아이디쿠키수명 = 60 * 60 * 24 * 30   # 30일

관리자 = "admin"
그룹원 = "member"
권한이름 = {관리자: "관리자", 그룹원: "그룹원"}
권한으로 = {관리자: "관리자로", 그룹원: "그룹원으로"}   # 조사까지 붙인 말(관리자'로' · 그룹원'으로')

_자료함 = None                       # portal.py 가 켜질 때 알려 준다
_지금 = threading.local()            # 이 요청에 들어온 사람

열린길 = ("/assets/", "/api/", "/__rev", "/favicon.ico")


def 설정하기(자료함):
    global _자료함
    _자료함 = str(자료함)


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def _uid():
    return str(uuidmod.uuid4())


def _지금시각():
    return datetime.now().isoformat(timespec="seconds")


def _연다():
    conn = dbmod.connect(_자료함)
    표만들기(conn)
    return conn


# ────────────────────────────────────────────────────── 표
def 표만들기(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS account (
        uuid          TEXT PRIMARY KEY,
        login_id      TEXT NOT NULL UNIQUE,
        name          TEXT NOT NULL,
        person_uuid   TEXT,
        role          TEXT NOT NULL DEFAULT 'member',
        salt          TEXT NOT NULL,
        hash          TEXT NOT NULL,
        iterations    INTEGER NOT NULL,
        must_change   INTEGER NOT NULL DEFAULT 0,
        active        INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT NOT NULL,
        created_by    TEXT NOT NULL DEFAULT '',
        last_login_at TEXT
    );
    -- 드나든 기록. 지우지 않는다(CLAUDE.md 2번-3).
    CREATE TABLE IF NOT EXISTS account_event (
        uuid         TEXT PRIMARY KEY,
        account_uuid TEXT,
        login_id     TEXT NOT NULL DEFAULT '',
        action       TEXT NOT NULL,
        actor        TEXT NOT NULL DEFAULT '',
        at           TEXT NOT NULL,
        ip           TEXT NOT NULL DEFAULT '',
        note         TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS login_session (
        token        TEXT PRIMARY KEY,
        account_uuid TEXT NOT NULL,
        at           TEXT NOT NULL,
        seen_at      TEXT NOT NULL,
        ip           TEXT NOT NULL DEFAULT ''
    );
    """)
    conn.commit()


def 적는다(conn, action, account=None, login_id="", actor="", ip="", note=""):
    conn.execute("INSERT INTO account_event VALUES (?,?,?,?,?,?,?,?)",
                 (_uid(), account, login_id, action, actor, _지금시각(), ip, note))


# ────────────────────────────────────────────────────── 비밀번호
def 굳히기(비밀번호, salt=None, 되풀이=반복):
    salt = salt or os.urandom(16).hex()
    got = hashlib.pbkdf2_hmac("sha256", 비밀번호.encode("utf-8"),
                              bytes.fromhex(salt), 되풀이)
    return salt, got.hex(), 되풀이


def 맞나(row, 비밀번호):
    _, got, _ = 굳히기(비밀번호, row["salt"], row["iterations"])
    return hmac.compare_digest(got, row["hash"])


def 비밀번호규칙(값):
    """너무 쉬운 비밀번호만 막는다. 폐쇄망 안이라 길이만 본다."""
    if len(값 or "") < 8:
        return "비밀번호는 8자 이상으로 정해 주세요."
    return ""


# ────────────────────────────────────────────────────── 계정
def 사람수(conn):
    return conn.execute("SELECT COUNT(*) c FROM account").fetchone()["c"]


def 계정(conn, uuid):
    return conn.execute("SELECT * FROM account WHERE uuid=?", (uuid,)).fetchone()


def 계정목록(conn):
    return conn.execute("SELECT * FROM account ORDER BY active DESC, name").fetchall()


def _담당자로도(conn, 이름):
    """검수 이력에 남는 담당자 명단(person)에도 같은 이름을 둔다 — 이름이 두 벌이 되지 않게."""
    row = conn.execute("SELECT uuid FROM person WHERE name=?", (이름,)).fetchone()
    if row:
        conn.execute("UPDATE person SET active=1 WHERE uuid=?", (row["uuid"],))
        return row["uuid"]
    pid = _uid()
    conn.execute("INSERT INTO person(uuid,name,affiliation,active) VALUES (?,?,?,1)",
                 (pid, 이름, "디자인그룹"))
    return pid


def 만들기(conn, login_id, 이름, 비밀번호, role=그룹원, actor="", 바꾸게=True):
    """계정 한 개. 막힌 까닭을 돌려준다(빈 글이면 됐다)."""
    login_id = (login_id or "").strip()
    이름 = (이름 or "").strip()
    if not login_id or not 이름:
        return "아이디와 이름을 적어 주세요."
    if role not in (관리자, 그룹원):
        return "권한은 관리자나 그룹원 중에서 골라 주세요."
    막힘 = 비밀번호규칙(비밀번호)
    if 막힘:
        return 막힘
    if conn.execute("SELECT 1 FROM account WHERE login_id=?", (login_id,)).fetchone():
        return f"'{login_id}' 는 이미 쓰고 있는 아이디입니다."
    salt, got, 되풀이 = 굳히기(비밀번호)
    uid = _uid()
    conn.execute("INSERT INTO account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (uid, login_id, 이름, _담당자로도(conn, 이름), role, salt, got, 되풀이,
                  1 if 바꾸게 else 0, 1, _지금시각(), actor, None))
    적는다(conn, "created", uid, login_id, actor, note=f"{권한으로[role]} 만듦")
    conn.commit()
    return ""


def 권한바꾸기(conn, uuid, role, actor=""):
    row = 계정(conn, uuid)
    if row is None or role not in (관리자, 그룹원):
        return "바꾸지 못했습니다."
    if row["role"] == 관리자 and role != 관리자 and 관리자수(conn) <= 1:
        return "관리자가 한 명뿐이라 권한을 내릴 수 없습니다."
    conn.execute("UPDATE account SET role=? WHERE uuid=?", (role, uuid))
    적는다(conn, "role-changed", uuid, row["login_id"], actor,
          note=f"{권한이름[row['role']]} → {권한이름[role]}")
    conn.commit()
    return ""


def 관리자수(conn):
    return conn.execute(
        "SELECT COUNT(*) c FROM account WHERE role=? AND active=1", (관리자,)).fetchone()["c"]


def 켜고끄기(conn, uuid, 켤까, actor=""):
    row = 계정(conn, uuid)
    if row is None:
        return "그런 계정이 없습니다."
    if not 켤까 and row["role"] == 관리자 and 관리자수(conn) <= 1:
        return "관리자가 한 명뿐이라 사용 중지할 수 없습니다."
    conn.execute("UPDATE account SET active=? WHERE uuid=?", (1 if 켤까 else 0, uuid))
    if not 켤까:
        conn.execute("DELETE FROM login_session WHERE account_uuid=?", (uuid,))
        conn.execute("UPDATE person SET active=0 WHERE uuid=?", (row["person_uuid"],))
    else:
        conn.execute("UPDATE person SET active=1 WHERE uuid=?", (row["person_uuid"],))
    적는다(conn, "enabled" if 켤까 else "disabled", uuid, row["login_id"], actor)
    conn.commit()
    return ""


def 비밀번호초기화(conn, uuid, 임시, actor=""):
    row = 계정(conn, uuid)
    if row is None:
        return "그런 계정이 없습니다."
    막힘 = 비밀번호규칙(임시)
    if 막힘:
        return 막힘
    salt, got, 되풀이 = 굳히기(임시)
    conn.execute("UPDATE account SET salt=?,hash=?,iterations=?,must_change=1 WHERE uuid=?",
                 (salt, got, 되풀이, uuid))
    conn.execute("DELETE FROM login_session WHERE account_uuid=?", (uuid,))
    적는다(conn, "password-reset", uuid, row["login_id"], actor, note="임시 비밀번호로 초기화")
    conn.commit()
    return ""


def 비밀번호바꾸기(conn, uuid, 지금것, 새것, 또, actor=""):
    row = 계정(conn, uuid)
    if row is None:
        return "그런 계정이 없습니다."
    if not 맞나(row, 지금것 or ""):
        return "지금 비밀번호가 맞지 않습니다."
    if (새것 or "") != (또 or ""):
        return "새 비밀번호를 두 칸에 같게 적어 주세요."
    막힘 = 비밀번호규칙(새것)
    if 막힘:
        return 막힘
    if 맞나(row, 새것):
        return "지금 쓰던 것과 다른 비밀번호로 정해 주세요."
    salt, got, 되풀이 = 굳히기(새것)
    conn.execute("UPDATE account SET salt=?,hash=?,iterations=?,must_change=0 WHERE uuid=?",
                 (salt, got, 되풀이, uuid))
    적는다(conn, "password-changed", uuid, row["login_id"], actor or row["name"])
    conn.commit()
    return ""


# ────────────────────────────────────────────────────── 들어온 표(세션)
def 문열기(conn, account_uuid, ip=""):
    token = uuidmod.uuid4().hex + uuidmod.uuid4().hex
    conn.execute("INSERT INTO login_session VALUES (?,?,?,?,?)",
                 (token, account_uuid, _지금시각(), _지금시각(), ip))
    conn.execute("UPDATE account SET last_login_at=? WHERE uuid=?", (_지금시각(), account_uuid))
    conn.commit()
    return token


def 문닫기(conn, token):
    conn.execute("DELETE FROM login_session WHERE token=?", (token,))
    conn.commit()


def _표로찾기(conn, token):
    if not token:
        return None
    row = conn.execute(
        """SELECT a.*, s.token FROM login_session s JOIN account a ON a.uuid=s.account_uuid
           WHERE s.token=? AND a.active=1""", (token,)).fetchone()
    if row is None:
        return None
    s = conn.execute("SELECT seen_at FROM login_session WHERE token=?", (token,)).fetchone()
    try:
        마지막 = datetime.fromisoformat(s["seen_at"])
    except (TypeError, ValueError):
        마지막 = datetime.now()
    if datetime.now() - 마지막 > 머문시간:
        conn.execute("DELETE FROM login_session WHERE token=?", (token,))
        적는다(conn, "expired", row["uuid"], row["login_id"], note="오래 머물러 표가 닫힘")
        conn.commit()
        return None
    conn.execute("UPDATE login_session SET seen_at=? WHERE token=?", (_지금시각(), token))
    conn.commit()
    return row


# ────────────────────────────────────────────────────── 이 요청에 들어온 사람
def 지금사람():
    return getattr(_지금, "사람", None)


def 지금이름():
    사람 = 지금사람()
    return 사람["name"] if 사람 else ""


def 나의옵션():
    """이력에 남길 담당자 고르는 칸 — 로그인한 사람 하나뿐이다(고를 것이 없다)."""
    이름 = 지금이름()
    return f'<option value="{_esc(이름)}" selected>{_esc(이름)}</option>' if 이름 else ""


def 나의숨김칸(이름칸="actor"):
    """이력에 남길 담당자 — 고르는 것이 아니라 **로그인한 사람**이다(CLAUDE.md 포털 로그인).

    고를 것이 하나뿐이라 고르개를 두지 않고 숨은 칸 하나로 보낸다.
    """
    return f'<input type="hidden" name="{_esc(이름칸)}" value="{_esc(지금이름())}">'


def 관리자인가():
    사람 = 지금사람()
    return bool(사람) and 사람["role"] == 관리자


# ────────────────────────────────────────────────────── 화면
def _쿠키(handler, 이름):
    묶음 = handler.headers.get("Cookie", "")
    for 조각 in 묶음.split(";"):
        키, _, 값 = 조각.strip().partition("=")
        if 키 == 이름:
            return 값
    return ""


def _아이피(handler):
    try:
        return handler.client_address[0]
    except Exception:
        return ""


def _보낸다(handler, 글, code=200, 쿠키줄=()):
    data = 글.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Referrer-Policy", "same-origin")
    for 줄 in 쿠키줄:
        handler.send_header("Set-Cookie", 줄)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _간다(handler, 주소, 쿠키줄=()):
    # 주소 줄(Location)은 latin-1 로만 나간다 — 한글이 섞일 수 있는 값은 부르는 쪽에서 quote() 한다.
    handler.send_response(303)
    handler.send_header("Location", 주소)
    for 줄 in 쿠키줄:
        handler.send_header("Set-Cookie", 줄)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def _몸(handler):
    length = int(handler.headers.get("Content-Length", 0) or 0)
    return {키: 값[0] for 키, 값 in parse_qs(handler.rfile.read(length).decode("utf-8")).items()}


CSS = """
/* 로그인 화면 — 시안 `웹_로그인 화면`(SW-UX-GUIDE V3.0 · 2601:21357) 의 자리 그대로.
   생김새는 정본 부품(s1-ui.css)이 맡는다 — 여기 있는 것은 **놓는 자리**뿐이고 값은 전부 토큰이다. */
body.login{margin:0;background:var(--color-bg-level-0);min-height:100vh;display:flex;flex-direction:column}
/* CI 위 간격 123 — river 지시 2026-09-28. 토큰에 없는 값이라 그대로 적는다(시안은 120). */
.login .판{flex:1;display:flex;align-items:flex-start;justify-content:center;
  padding:123px var(--spacing-16) var(--spacing-64)}
/* 칸과 단추 너비 300 — river 지시 2026-09-28(시안 460 에서 좁혔다).
   상자 하나로 정한다: 칸·단추·아이디 저장·아래 글이 모두 같은 선에 서야 한다. */
.login .상자{width:300px;max-width:100%}
/* 시안: CI 아래 50 띄우고 칸이 온다(spacing-48 이 가장 가깝다). */
.login .씨아이{display:flex;justify-content:center;margin:0 0 var(--spacing-48)}
.login .씨아이 img{display:block}
/* 정본 Input 은 제 너비 200 을 스스로 갖는다("더 넓게 쓰려면 쓰는 쪽에서 width 를 준다") —
   여기서는 상자(300)를 꽉 채워야 단추·아이디 저장과 같은 선에 선다. */
.login .칸{display:flex;flex-direction:column;gap:var(--spacing-8);width:100%}
.login .칸 + .칸{margin-top:var(--spacing-8)}
.login .기억{display:flex;margin:var(--spacing-8) 0 var(--spacing-24)}
/* 시안의 로그인 단추는 칸과 같은 너비로 눕는다 — 자리만 정하고 생김새는 부품이 맡는다. */
.login .단추자리{display:block}
.login .단추자리 [data-s1-component="button"]{width:100%}
.login .가름{width:var(--border-width-default);height:var(--spacing-12);
  background:var(--color-icon-gray-light);display:inline-block}
.login .막힘{margin:0 0 var(--spacing-16);padding:var(--spacing-12) var(--spacing-16);
  border-radius:var(--radius-4);background:var(--color-surface-raised);
  border:var(--border-width-1) solid var(--color-form-control-border-error);
  color:var(--color-text-state-error);font-size:var(--font-size-14)}
.login .안내{margin:0 0 var(--spacing-16);font-size:var(--font-size-14);
  color:var(--color-text-body-tertiary);text-align:center}
/* 맨 아래 띠 — 시안 login_Footer(h120 · 위아래 여백 · 좌우 넓은 여백 · 윗줄 1px).
   정본에 Footer 부품 CSS 가 아직 없어 자리만 잡는다(DESIGN_SYSTEM_GAP). */
/* 좌우 여백은 맨 위 줄과 같은 정본 값이다 — 왼 24 · 오른 20(registry gnb.json).
   시안은 양 끝 320 안쪽이지만 그것은 그 화면의 자리 잡기이지 부품 규정이 아니다
   (river 확정 2026-09-28 — 정본대로 간다). */
.login footer{display:flex;align-items:flex-start;justify-content:space-between;
  gap:var(--spacing-24);
  padding:var(--spacing-32) var(--spacing-20) var(--spacing-32) var(--spacing-24);
  background:var(--color-navigation-bg);
  border-top:var(--border-width-default) solid var(--color-line-gray-subtle)}
/* 글 크기·행간·자간은 가이드 타이포 body-10r 그대로다(10 · 140% · wide). */
.login footer .글{display:flex;flex-direction:column;gap:var(--spacing-10);
  font-size:var(--font-size-10);color:var(--color-text-body-tertiary);
  line-height:var(--line-height-140);letter-spacing:var(--letter-spacing-wide)}
.login footer .줄{display:flex;align-items:center;gap:var(--spacing-4)}
.login footer .줄 .가름{height:var(--spacing-8)}
.login footer img{display:block;flex:none}
.판넓게{max-width:1180px;margin:0 auto;padding:var(--spacing-40) var(--spacing-16)}
.판넓게 h1{font-size:var(--font-size-24);font-weight:var(--font-weight-bold);margin:0 0 var(--spacing-8)}
.판넓게 .풀이{margin:0 0 var(--spacing-24);font-size:var(--font-size-14);color:var(--color-text-body-tertiary)}
.판넓게 .묶음{margin-bottom:var(--spacing-40)}
.판넓게 h2{font-size:var(--font-size-18);font-weight:var(--font-weight-bold);margin:0 0 var(--spacing-12)}
.판넓게 .막힘{margin:0 0 var(--spacing-16);padding:var(--spacing-12) var(--spacing-16);
  border-radius:var(--radius-4);background:var(--color-surface-raised);
  border:var(--border-width-1) solid var(--color-form-control-border-error);
  color:var(--color-text-state-error);font-size:var(--font-size-14)}
.판넓게 .안내{margin:0 0 var(--spacing-16);font-size:var(--font-size-14);color:var(--color-text-body-tertiary)}
.줄폼{display:flex;flex-wrap:wrap;gap:var(--spacing-8);align-items:flex-end}
.줄폼 .칸{width:200px}
.칸작게{display:inline-flex;width:160px;vertical-align:middle}
.잔글{font-size:var(--font-size-12);color:var(--color-text-body-tertiary)}
.끔{color:var(--color-text-body-tertiary)}
"""


def _머리(제목, 몸클래스="", 덧CSS=""):
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_esc(제목)}</title>{s1_tokens.부품()}'
            f'<style>{CSS}{덧CSS}</style></head><body data-s1-break="pc" class="{몸클래스}">')


def _로그인줄():
    """시안의 login_GNB — 왼쪽에 서비스 이름, 오른쪽에 쓰는 말.
    정본에 LoginGNB 부품 CSS 가 아직 없어 같은 치수(h56)인 GNB 부품을 쓴다.
    서비스 이름 글줄은 `gnb.로고()` 한 곳에서 온다 — 두 벌로 적지 않는다."""
    import gnb as gnb_bar
    return ('<link rel=stylesheet href=\'/assets/css/s1-gnb.css\'>' + gnb_bar.바CSS
            + '<nav data-s1-component="gnb" data-size="md" aria-label="서비스">'
            + gnb_bar.로고("/login") +
            '<ul data-s1-part="menus"></ul>'
            '<span data-s1-part="util">'
            '<span data-s1-part="lang">'
            '<span data-s1-part="lang-icon" aria-hidden="true"></span>한국어</span>'
            '</span></nav>')


def _씨아이():
    """시안의 CI(에스원, Blue). 시안에서 내려받은 그림을 그대로 쓴다 — 다시 그리지 않는다."""
    return ('<div class="씨아이">'
            '<img src="/assets/img/ci-s1-blue.svg" alt="에스원" width="79" height="30">'
            '</div>')


def _꼬리():
    """시안의 login_Footer 그대로 — 글줄도 마크도 시안에서 가져온 것이다."""
    return ('<footer><span class="글">'
            '<span class="줄">개인정보 처리방침'
            '<span class="가름" aria-hidden="true"></span>'
            '위치기반 서비스 이용약관</span>'
            '<span>(주)에스원   사업자등록번호 208-81-13302    대표이사 정해린    '
            '04511 서울특별시 중구 세종대로 7길 25 에스원 빌딩</span>'
            '<span>© S-1 Corp. All Rights Reserved.</span>'
            '</span>'
            '<img src="/assets/img/logo-s1-gray.svg" alt="에스원" width="42" height="16">'
            '</footer>')


def _입력(이름, 라벨, 값="", 종류="text", 안내="", 자리글="", 라벨보이기=True):
    칸id = f"f-{이름}"
    비번 = ('<button type="button" data-s1-part="action" data-action="password"'
            ' aria-pressed="false" aria-label="비밀번호 보기">'
            '<span data-s1-part="action-icon" aria-hidden="true"></span></button>'
            ) if 종류 == "password" else ""
    도움 = f'<p data-s1-part="message">{_esc(안내)}</p>' if 안내 else ""
    라벨칸 = (f'<label data-s1-part="label" for="{칸id}">{_esc(라벨)}</label>'
            if 라벨보이기 else "")
    자리 = f' placeholder="{_esc(자리글)}"' if 자리글 else ""
    이름표 = "" if 라벨보이기 else f' aria-label="{_esc(라벨)}"'
    return (f'<div class="칸" data-s1-component="input" data-size="md" data-break="pc">'
            f'{라벨칸}'
            f'<div data-s1-part="field">'
            f'<input data-s1-part="control" type="{종류}" id="{칸id}" name="{이름}"'
            f' value="{_esc(값)}"{자리}{이름표} autocomplete="off">{비번}'
            f'<button type="button" data-s1-part="action" data-action="clear"'
            f' aria-label="입력 내용 지우기" hidden>'
            f'<span data-s1-part="action-icon" aria-hidden="true"></span></button>'
            f'</div>{도움}</div>')


def _단추(글, variant="primary", size="md", 종류="submit", 꺼둠=False):
    끔 = " disabled" if 꺼둠 else ""       # 가이드 Button 계약 — 끄는 것은 native disabled 로만
    return (f'<button type="{종류}" data-s1-component="button" data-variant="{variant}"'
            f' data-size="{size}"{끔}><span data-s1-part="label">{_esc(글)}</span></button>')


_입력JS = s1_tokens.동작()   # 입력칸 지우기·고르개 여닫기는 정본 동작이 한다


def _권한고르기(고른=그룹원, 앞머리="role"):
    """권한 Select Box 한 개. 고른 값은 같은 상자 안 hidden 에 담긴다(assets/js/s1-form.js)."""
    줄 = ""
    for 값 in (그룹원, 관리자):
        고름 = "true" if 값 == 고른 else "false"
        줄 += (f'<div data-s1-part="option" role="option" aria-selected="{고름}"'
               f' tabindex="{"0" if 값 == 고른 else "-1"}" data-value="{값}">'
               f'<span data-s1-part="option-label">{권한이름[값]}</span></div>')
    return ('<div data-s1-component="select" data-size="md" data-break="pc">'
            f'<label data-s1-part="label" for="{앞머리}-trigger">권한</label>'
            f'<button type="button" data-s1-part="trigger" id="{앞머리}-trigger"'
            ' aria-haspopup="listbox" aria-expanded="false" data-filled="true">'
            f'<span data-s1-part="value">{권한이름[고른]}</span>'
            '<span data-s1-part="icon" aria-hidden="true"></span></button>'
            '<div data-s1-part="panel" hidden>'
            '<div data-s1-component="dropdown" data-type="text" data-size="md" role="listbox"'
            f' aria-labelledby="{앞머리}-trigger">{줄}</div></div>'
            f'<input type="hidden" name="role" value="{고른}">'
            '</div>')


def 로그인화면(막힘="", 아이디="", 다음="/"):
    """시안 `웹_로그인 화면`(2601:21357) 그대로 — 위 줄 · 가운데 상자 · 아래 띠.

    여기서 하는 일은 **들어오는 것 하나**다. 계정을 만드는 길은 이 화면에 없다
    (관리자 계정은 자료함에만 둔다 — river 확정 2026-09-28).
    시안에 있는 '아이디 찾기 · 비밀번호 찾기' 는 두지 않는다 — 포털은 그 길을 주지 않는다
    (잊으면 관리자가 임시 비밀번호로 초기화한다 — river 확정 2026-09-28).
    부품은 정본에 있는 것만 쓴다(Input · Checkbox · Button · GNB).
    시안의 web tab bar 는 그림으로 그린 브라우저 창틀이라 화면에 넣지 않는다.
    """
    말썽 = f'<p class="막힘">{_esc(막힘)}</p>' if 막힘 else ""
    속 = (_씨아이() + 말썽
          + '<form method="post" action="/login" id="login-form">'
          + f'<input type="hidden" name="next" value="{_esc(다음)}">'
          + _입력("login_id", "아이디", 아이디, 자리글="아이디를 입력해 주세요.", 라벨보이기=False)
          + _입력("password", "비밀번호", 종류="password",
                 자리글="비밀번호를 입력해 주세요.", 라벨보이기=False)
          + '<div class="기억" data-s1-component="checkbox">'
          + '<input type="checkbox" id="remember" name="remember" data-s1-part="control"'
          + (" checked" if 아이디 else "") + '>'
          + '<label data-s1-part="label" for="remember">아이디 저장</label></div>'
          + f'<div class="단추자리">{_단추("로그인", 꺼둠=True)}</div>'
          + '</form>')
    return (_머리("로그인 · 검수 포털", "login") + _로그인줄()
            + f'<div class="판"><div class="상자">{속}</div></div>' + _꼬리()
            + _입력JS + f"<script>{로그인JS}</script></body></html>")


# 시안의 로그인 단추는 두 칸이 다 차야 눌린다(빈 채로 보내지 않는다).
# 꺼고 켜는 것은 가이드 Button 계약대로 native disabled 로만 한다.
로그인JS = """
(function(){
  var 폼=document.getElementById('login-form'); if(!폼) return;
  var 단추=폼.querySelector('[data-s1-component="button"]');
  var 칸들=[polyfill('login_id'),polyfill('password')];
  function polyfill(이름){ return 폼.querySelector('[name="'+이름+'"]'); }
  function 살핀다(){ 단추.disabled=칸들.some(function(칸){return !칸||!칸.value.trim();}); }
  칸들.forEach(function(칸){ if(칸){ ['input','change'].forEach(function(일){ 칸.addEventListener(일,살핀다); }); } });
  살핀다();
})();
"""


def 내계정화면(사람, 막힘="", 알림=""):
    import gnb as gnb_bar
    말썽 = f'<p class="막힘">{_esc(막힘)}</p>' if 막힘 else ""
    알 = f'<p class="안내">{_esc(알림)}</p>' if 알림 else ""
    처음 = ('<p class="안내">임시 비밀번호로 들어오셨습니다. 새 비밀번호를 정해야 검수 화면으로 갑니다.</p>'
            if 사람["must_change"] else "")
    속 = (f'<h1>내 계정</h1>'
          f'<p class="풀이">{_esc(사람["name"])} · {_esc(사람["login_id"])} · '
          f'{_esc(권한이름.get(사람["role"], 사람["role"]))}</p>{처음}{말썽}{알}'
          f'<form method="post" action="/account/password" style="max-width:460px">'
          f'{_입력("now", "지금 비밀번호", 종류="password")}'
          f'{_입력("new", "새 비밀번호", 종류="password", 안내="8자 이상으로 정해 주세요.")}'
          f'{_입력("again", "새 비밀번호 다시", 종류="password")}'
          f'<div style="margin-top:var(--spacing-24)">{_단추("비밀번호 바꾸기")}</div></form>')
    return (_머리("내 계정 · 검수 포털") + gnb_bar.바("")
            + f'<div class="판넓게">{속}</div>' + _입력JS + "</body></html>")


def 계정관리화면(conn, 막힘="", 알림=""):
    import gnb as gnb_bar
    말썽 = f'<p class="막힘">{_esc(막힘)}</p>' if 막힘 else ""
    알 = f'<p class="안내">{_esc(알림)}</p>' if 알림 else ""
    줄 = ""
    for a in 계정목록(conn):
        끔 = "" if a["active"] else ' class="끔"'
        바꿀것 = 그룹원 if a["role"] == 관리자 else 관리자
        권한칸 = (f'{_esc(권한이름.get(a["role"], a["role"]))} '
                f'<form method="post" action="/accounts/role" style="display:inline">'
                f'<input type="hidden" name="uuid" value="{_esc(a["uuid"])}">'
                f'<input type="hidden" name="role" value="{바꿀것}">'
                + _단추(권한으로[바꿀것], "secondary", "xsm") + '</form>')
        켜끄 = (f'<form method="post" action="/accounts/active" style="display:inline">'
              f'<input type="hidden" name="uuid" value="{_esc(a["uuid"])}">'
              f'<input type="hidden" name="on" value="{0 if a["active"] else 1}">'
              + _단추("다시 쓰기" if not a["active"] else "사용 중지", "secondary", "xsm") + '</form>')
        초기화 = (f'<form method="post" action="/accounts/reset" style="display:inline"'
               f' onsubmit="return confirm(\'임시 비밀번호로 초기화합니다. 그 사람은 다음에 들어올 때 새로 정합니다.\')">'
               f'<input type="hidden" name="uuid" value="{_esc(a["uuid"])}">'
               '<span class="칸작게" data-s1-component="input" data-size="xsm" data-break="pc">'
               '<span data-s1-part="field">'
               '<input data-s1-part="control" name="password" type="text" required minlength="8"'
               ' aria-label="임시 비밀번호" placeholder="임시 비밀번호" autocomplete="off">'
               '<button type="button" data-s1-part="action" data-action="clear"'
               ' aria-label="입력 내용 지우기" hidden>'
               '<span data-s1-part="action-icon" aria-hidden="true"></span></button>'
               '</span></span>'
               + _단추("초기화", "secondary", "xsm") + '</form>')
        줄 += (f'<tr data-s1-part="row"{끔}>'
               f'<td data-s1-part="cell">{_esc(a["login_id"])}</td>'
               f'<td data-s1-part="cell">{_esc(a["name"])}</td>'
               f'<td data-s1-part="cell">{권한칸}</td>'
               f'<td data-s1-part="cell">{"쓰는 중" if a["active"] else "사용 중지"}</td>'
               f'<td data-s1-part="cell">{_esc((a["last_login_at"] or "—").replace("T", " ")[:16])}</td>'
               f'<td data-s1-part="cell">{켜끄} {초기화}</td></tr>')
    표 = ('<div data-s1-component="table" data-size="sm"><table data-s1-part="table"><thead><tr>'
          '<th data-s1-part="header-cell" scope="col">아이디</th>'
          '<th data-s1-part="header-cell" scope="col">이름</th>'
          '<th data-s1-part="header-cell" scope="col">권한</th>'
          '<th data-s1-part="header-cell" scope="col">상태</th>'
          '<th data-s1-part="header-cell" scope="col">마지막 로그인</th>'
          '<th data-s1-part="header-cell" scope="col">하는 일</th>'
          f'</tr></thead><tbody>{줄}</tbody></table></div>')

    더하기 = (f'<form class="줄폼" method="post" action="/accounts/new">'
           f'{_입력("login_id", "아이디")}{_입력("name", "이름")}'
           f'{_입력("password", "임시 비밀번호", 종류="password")}'
           f'<div class="칸">{_권한고르기()}</div>'
           f'{_단추("사람 추가")}</form>'
           '<p class="잔글">임시 비밀번호는 본인에게 알려 주세요. 처음 들어올 때 본인이 새로 정합니다.</p>')

    기록 = ""
    for e in conn.execute("SELECT * FROM account_event ORDER BY at DESC LIMIT 100"):
        기록 += (f'<tr data-s1-part="row">'
               f'<td data-s1-part="cell">{_esc((e["at"] or "").replace("T", " ")[:19])}</td>'
               f'<td data-s1-part="cell">{_esc(e["login_id"])}</td>'
               f'<td data-s1-part="cell">{_esc(일이름.get(e["action"], e["action"]))}</td>'
               f'<td data-s1-part="cell">{_esc(e["actor"])}</td>'
               f'<td data-s1-part="cell">{_esc(e["ip"])}</td>'
               f'<td data-s1-part="cell">{_esc(e["note"])}</td></tr>')
    기록표 = ('<div data-s1-component="table" data-size="xsm"><table data-s1-part="table"><thead><tr>'
           '<th data-s1-part="header-cell" scope="col">언제</th>'
           '<th data-s1-part="header-cell" scope="col">아이디</th>'
           '<th data-s1-part="header-cell" scope="col">한 일</th>'
           '<th data-s1-part="header-cell" scope="col">누가</th>'
           '<th data-s1-part="header-cell" scope="col">어디서</th>'
           '<th data-s1-part="header-cell" scope="col">메모</th>'
           f'</tr></thead><tbody>{기록}</tbody></table></div>')

    속 = (f'<h1>계정 관리</h1><p class="풀이">디자인그룹원만 들어올 수 있습니다. '
          f'계정은 여기서 직접 만듭니다.</p>{말썽}{알}'
          f'<div class="묶음"><h2>사람 추가</h2>{더하기}</div>'
          f'<div class="묶음"><h2>사람 목록</h2>{표}'
          '<p class="잔글">사용 중지한 사람도 목록과 이력에 남습니다 — 지우지 않습니다.</p></div>'
          f'<div class="묶음"><h2>드나든 기록 · 최근 100줄</h2>{기록표}</div>')
    return (_머리("계정 관리 · 검수 포털") + gnb_bar.바("")
            + f'<div class="판넓게">{속}</div>' + _입력JS + "</body></html>")


일이름 = {
    "created": "계정 만듦", "login": "로그인", "login-failed": "로그인 실패",
    "logout": "로그아웃", "password-reset": "비밀번호 초기화", "password-changed": "비밀번호 바꿈",
    "role-changed": "권한 바꿈", "disabled": "사용 중지", "enabled": "다시 씀",
    "expired": "표 만료",
}


# ────────────────────────────────────────────────────── 문지기
def _열린길인가(path):
    return any(path.startswith(x) if x.endswith("/") else path == x for x in 열린길)


def 문(handler, method="GET"):
    """들어온 사람을 알아보고, 필요하면 여기서 답을 다 보낸다.

    돌려주는 값이 True 면 포털은 더 하지 않는다(이미 답을 보냈다).
    """
    path = urlparse(handler.path).path
    _지금.사람 = None
    if _열린길인가(path):
        return False

    conn = _연다()
    try:
        사람 = _표로찾기(conn, _쿠키(handler, 쿠키))
        _지금.사람 = 사람

        if path.startswith("/login"):
            return _로그인길(handler, conn, method, path, 사람)
        if path == "/logout":
            if 사람:
                문닫기(conn, _쿠키(handler, 쿠키))
                적는다(conn, "logout", 사람["uuid"], 사람["login_id"], 사람["name"], _아이피(handler))
                conn.commit()
            _간다(handler, "/login", [f"{쿠키}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"])
            return True

        if 사람 is None:
            다음 = handler.path if method == "GET" else "/"
            _간다(handler, "/login?next=" + quote(다음))
            return True

        # 임시 비밀번호로 들어왔으면 새로 정하기 전에는 다른 데로 못 간다
        if 사람["must_change"] and not path.startswith("/account"):
            _간다(handler, "/account")
            return True

        if path.startswith("/account") and not path.startswith("/accounts"):
            return _내계정길(handler, conn, method, path, 사람)
        if path.startswith("/accounts"):
            return _계정관리길(handler, conn, method, path, 사람)
        return False
    finally:
        conn.close()


def _로그인길(handler, conn, method, path, 사람):
    if method == "GET":
        if 사람:
            _간다(handler, "/")
            return True
        q = parse_qs(urlparse(handler.path).query)
        _보낸다(handler, 로그인화면(아이디=_쿠키(handler, 아이디쿠키),
                              다음=q.get("next", ["/"])[0]))
        return True

    if path != "/login":        # 계정을 만드는 길은 화면에 두지 않는다 — 자료함에서만 만든다
        _간다(handler, "/login")
        return True
    form = _몸(handler)
    아이디 = (form.get("login_id") or "").strip()
    다음 = form.get("next") or "/"
    row = conn.execute("SELECT * FROM account WHERE login_id=?", (아이디,)).fetchone()
    쿠키줄 = [f"{아이디쿠키}={quote(아이디)}; Path=/; Max-Age={아이디쿠키수명}; SameSite=Lax"
           if form.get("remember") else f"{아이디쿠키}=; Path=/; Max-Age=0; SameSite=Lax"]
    if row is None or not row["active"] or not 맞나(row, form.get("password") or ""):
        적는다(conn, "login-failed", row["uuid"] if row else None, 아이디, "", _아이피(handler),
              "사용 중지된 계정" if row is not None and not row["active"] else "")
        conn.commit()
        말 = ("사용이 중지된 계정입니다. 관리자에게 문의해 주세요."
             if row is not None and not row["active"] else "아이디나 비밀번호가 맞지 않습니다.")
        _보낸다(handler, 로그인화면(말, 아이디, 다음), 401, 쿠키줄)
        return True
    token = 문열기(conn, row["uuid"], _아이피(handler))
    적는다(conn, "login", row["uuid"], row["login_id"], row["name"], _아이피(handler))
    conn.commit()
    쿠키줄.append(f"{쿠키}={token}; Path=/; HttpOnly; SameSite=Lax")
    if not 다음.startswith("/") or 다음.startswith("//"):
        다음 = "/"
    _간다(handler, "/account" if row["must_change"] else 다음, 쿠키줄)
    return True


def _내계정길(handler, conn, method, path, 사람):
    if method == "GET":
        q = parse_qs(urlparse(handler.path).query)
        _보낸다(handler, 내계정화면(사람, 알림=q.get("notice", [""])[0]))
        return True
    if path != "/account/password":
        _간다(handler, "/account")
        return True
    form = _몸(handler)
    막힘 = 비밀번호바꾸기(conn, 사람["uuid"], form.get("now"), form.get("new"),
                     form.get("again"), 사람["name"])
    if 막힘:
        _보낸다(handler, 내계정화면(사람, 막힘))
        return True
    _간다(handler, "/account?notice=" + quote("비밀번호를 바꿨습니다."))
    return True


def _계정관리길(handler, conn, method, path, 사람):
    if 사람["role"] != 관리자:
        _보낸다(handler, _머리("권한 없음") + '<div class="판넓게"><h1>계정 관리는 관리자만 볼 수 있습니다.</h1>'
              '<p class="풀이"><a href="/">← 검수 포털로</a></p></div></body></html>', 403)
        return True
    if method == "GET":
        q = parse_qs(urlparse(handler.path).query)
        _보낸다(handler, 계정관리화면(conn, q.get("warn", [""])[0], q.get("notice", [""])[0]))
        return True

    form = _몸(handler)
    막힘, 알림 = "", ""
    if path == "/accounts/new":
        막힘 = 만들기(conn, form.get("login_id", ""), form.get("name", ""),
                   form.get("password", ""), form.get("role", 그룹원), 사람["name"])
        알림 = "" if 막힘 else f"{form.get('name', '')} 님을 더했습니다."
    elif path == "/accounts/role":
        막힘 = 권한바꾸기(conn, form.get("uuid", ""), form.get("role", ""), 사람["name"])
        알림 = "" if 막힘 else "권한을 바꿨습니다."
    elif path == "/accounts/active":
        켤까 = form.get("on") == "1"
        막힘 = 켜고끄기(conn, form.get("uuid", ""), 켤까, 사람["name"])
        알림 = "" if 막힘 else ("다시 쓰게 했습니다." if 켤까 else "사용을 중지했습니다.")
    elif path == "/accounts/reset":
        막힘 = 비밀번호초기화(conn, form.get("uuid", ""), form.get("password", ""), 사람["name"])
        알림 = "" if 막힘 else "임시 비밀번호로 초기화했습니다."
    else:
        _간다(handler, "/accounts")
        return True
    _간다(handler, "/accounts?" + ("warn=" + quote(막힘) if 막힘 else "notice=" + quote(알림)))
    return True
