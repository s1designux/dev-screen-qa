---
name: image-qa-repro-findid
description: plugin-image-qa 오탐 재현 세트(아이디 찾기·로그인)와 2026-09-02 엔진 개편 결과·남은 한계
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-02T06:46:01.734Z
---

**재현 세트 (레포에 복사됨: `validation-image-qa/repro/`, README에 실행법):**
- 디자인: Figma `〔따로 보관: 피그마파일-1〕` → 프레임 `8177:264186` "웹_ 아이디 찾기(휴대전화번호) 화면", `8177:263051` "웹_로그인 화면" (둘 다 1920×1080, **가짜 크롬 탭바 157px 포함**, 푸터 y=960 고정).
- 개발 캡처: 7월 캡처(플레이스홀더·유틸·대표이사·WA마크 차이) + 퍼블리싱 `findId.html`/`login.html` 헤드리스 캡처(글꼴 폴백이라 글자 후보가 늘어남).
- 요소 목록은 `use_figma`로 code.js collectDesign과 같은 규칙으로 뽑아 JSON으로 저장. 하네스는 ui.html의 마지막 dispatcher 줄을 치환해 Chrome `--headless=new --dump-dom`으로 실행.

**2026-09-02 개편(ui.html 엔진 전면 교체, code.js export 배율 1200→4096):**
구역별 정렬(섹션+구역 밖 root 각각 오프셋 추정, 표 묶기 ±4→±16 확대) → 디자인 전용 장식(위·아래 끝 가로 80%+, 짝 없음) 제외+안내 → 요소 우선 비교(글자/아이콘/도형, 이동 인정은 글자 score≥.85·mismatch≤.28·NCC≥.6·exact≤.42, 도형 score≥.7) → 빈자리만 픽셀 diff → 글자 후보 독립+디자인 원문 detail.
글자 같음 판정 실측: 흐림 NCC 같은 글자 ≥.7, 다른 글자 ≤.62 → 문턱 .6 + exact≤.42. 긴 줄은 토막 NCC(흐름 직선 보정)+오프셋 튐으로 국소화.

**한계(확인됨):** 10px 글자의 3글자 치환(정해린↔남궁범)은 NCC로 못 가름(토막 .78~.83) → "글자 수·띄어쓰기 다름"으로만 잡힘. 헤더 좌우 묶음이 반대 방향으로 밀리면(로그인 dev) 한쪽 누락 오탐. 해상도만 올리면 후보 폭증(21개)해 구조 개편이 필요했음. 관련: [[dev-screen-qa-validation]]
