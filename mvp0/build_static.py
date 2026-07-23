"""
정적 보기 전용 미러 생성기 (GitHub Pages 배포용).

portal.py의 render_list/render_screen/render_page를 그대로 재사용해
mvp0-real.db → docs/ 아래 정적 HTML(+이미지)로 구워낸다. portal.py는 건드리지 않는다
(로컬 라이브 포털 동작 그대로 유지).

정적 사이트라 쓰기 기능(업로드·통과 처리)과 차수 전환은 안 되므로, 렌더링된 HTML에서
그 부분만 후처리로 제거/대체하고, 링크는 GitHub Pages 하위 경로(BASE_PATH)에 맞게 고친다.

실행: python3 build_static.py  →  docs/ 생성
"""
import re
import shutil
from pathlib import Path

import db as dbmod
import portal
import queries

BASE = Path(__file__).resolve().parent
OUT = BASE.parent / "docs"  # GitHub Pages는 저장소 최상위 /docs만 배포 소스로 허용
BASE_PATH = "/dev-screen-qa"

_FORM_UPL_RE = re.compile(r'<form class="upl".*?</form>', re.S)
_FORM_PASS_RE = re.compile(r'<form class="passform".*?</form>', re.S)
_BTN_A4_RE = re.compile(r'<a class="btn" href="/report/[^"]*"[^>]*>화면 전체 A4</a>')
_RCHIP_RE = re.compile(r'<a class="rchip([^"]*)" href="[^"]*">(\d+차)</a>')
_SCREEN_HREF_RE = re.compile(r'href="(/screen/[^"?]+)"')
_SCREEN_JS_RE = re.compile(r"location\.href='(/screen/[^']+)'")


def transform(html: str) -> str:
    """render_* 출력 HTML을 정적 배포용으로 후처리."""
    html = _FORM_UPL_RE.sub("", html)
    html = _FORM_PASS_RE.sub(
        '<div class="passed">정적 보기 전용 — 처리는 로컬 포털에서</div>', html
    )
    html = _BTN_A4_RE.sub("", html)
    html = _RCHIP_RE.sub(r'<span class="rchip\1">\2</span>', html)
    html = html.replace('href="/?unresolved=1"', 'href="/unresolved/"')
    html = _SCREEN_HREF_RE.sub(lambda m: f'href="{m.group(1)}/"', html)
    # 행 클릭(JS location.href)도 href처럼 BASE_PATH 접두어를 붙인다(안 붙이면 루트로 가 404).
    html = _SCREEN_JS_RE.sub(lambda m: f"location.href='{BASE_PATH}{m.group(1)}/'", html)
    html = html.replace('href="/', f'href="{BASE_PATH}/')
    html = html.replace('src="/uploads/', f'src="{BASE_PATH}/uploads/')
    html = html.replace(
        "이 화면은 렌더링 뷰</footer>",
        "이 화면은 렌더링 뷰 · 정적 보기 전용(GitHub Pages 미러)</footer>",
    )
    html = html.replace(
        "FAIL · 원본 = SQLite(DB)</footer>",
        "FAIL · 원본 = SQLite(DB) · 정적 보기 전용(GitHub Pages 미러)</footer>",
    )
    return html


def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(transform(html), encoding="utf-8")


def build() -> None:
    if not portal.REAL_DB.exists():
        raise SystemExit(f"{portal.REAL_DB} 없음 — 실제 DB가 있어야 정적 사이트를 만들 수 있어요.")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT / ".nojekyll").write_text("")

    conn = dbmod.connect(portal.REAL_DB)
    screens = queries.list_screens(conn)
    conn.close()

    write(OUT / "index.html", portal.render_list(False, None))
    write(OUT / "unresolved" / "index.html", portal.render_list(True, None))

    for s in screens:
        key = s["human_key"]
        write(OUT / "screen" / key / "index.html", portal.render_screen(key))

        conn = dbmod.connect(portal.REAL_DB)
        scr = queries.get_screen(conn, key)
        pages = queries.pages_of_screen(conn, scr["row"]["uuid"])
        conn.close()

        for p in pages:
            html = portal.render_page(p["uuid"])
            if html is not None:
                write(OUT / "screen" / key / "page" / p["uuid"] / "index.html", html)

    if portal.UPLOADS.exists():
        shutil.copytree(portal.UPLOADS, OUT / "uploads", dirs_exist_ok=True)

    print(f"정적 사이트 생성 완료 → {OUT}")


if __name__ == "__main__":
    build()
