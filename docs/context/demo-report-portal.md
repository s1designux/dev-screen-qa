---
name: demo-report-portal
description: 보고용 시안(DEMO) 포털 — 실제본과 분리된 데모 서버·캡처 파이프라인 구성
metadata: 
  node_type: memory
  type: project
---

**목적:** 검수 포털의 '보고용 시안'을 실제 검수 데이터와 **완전히 분리**해 만든다. 나중에 실제 검수를 진행해도 데모 데이터와 안 섞이게 하는 게 핵심 요구.

**구성 (mvp0/):**
- 포털 DB/PORT 스위치: `portal.py`가 `MVP0_DB`/`MVP0_PORT` 환경변수를 읽음. 기본은 그대로 `mvp0-real.db`·8765. 실제본이 아니면 모든 페이지 상단에 빨간 **DEMO 배너**.
  - 실제본: `python3 portal.py` (8765, 배너 없음)
  - 데모본: `MVP0_DB=mvp0-demo.db MVP0_PORT=8766 python3 portal.py` (8766, DEMO 배너)
- `seed_demo.py` (신규): `fixtures/demo-report.json`을 읽어 **여러 화면·검수 페이지**를 `mvp0-demo.db`에 주입. 화면>검수페이지(pages[])>이슈 구조. dedup_key에 `DEMO|` 접두사 자동. **실제본 이름이면 시더 거부**(가드).
- `capture_pub.py` (신규): 퍼블리싱 HTML을 **로컬 크롬 headless**로 PNG 캡처 → `uploads/`(우측=개발 이미지). fixture page의 `pub_html`(퍼블리싱 폴더 기준 상대경로)로 지정, `pub_h`로 높이 조절.
- 좌측=디자인은 **피그마 프레임**: `download_assets(fileKey, nodeId, png)` → 임시 URL을 `curl`로 `uploads/`에 저장 → fixture page의 `design_img`.
- `load_fixture.py`·`mvp0-real.db`·`tb-web-001.json`은 **손대지 않음**.

**이번 데모 소스 (관리자 5화면):**
- 피그마 원본: fileKey `〔따로 보관: 피그마파일-1〕` (UVIS 관리자 리뉴얼 UI 사양서), 관리자 페이지 노드 `1569:122293`. 계정/대시보드/차량위치 프레임이 그 안에 있음.
- 퍼블리싱(개발화면 대체): `~/Desktop/s1_uvis_admin_publish-main-pc/pc/` — 정적 HTML, `dist/html/pages/{account,monitoring,...}`, file:// 단독 렌더 OK. 카테고리가 피그마 사양서와 일치.
- 5화면: 아이디찾기(3p)·비밀번호찾기/재설정(3p)·로그인(1p)·모니터링 대시보드(1p)·차량위치(1p).

**주의/미완:** 핀 좌표는 데모용 근사치(실제 검수 아님). 커밋은 사용자 확인 후. 관련: [[dev-screen-qa-validation]].
