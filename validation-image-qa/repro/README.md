# 실제 화면 재현 세트 (plugin-image-qa 엔진)

플러그인 UI(`plugin-image-qa/ui.html`)의 비교 엔진을 헤드리스 Chrome에서 실제 자료로 돌려
후보 목록(`*.json`)과 번호 오버레이(`*.overlay.png`), 정렬 확인용 겹침(`*.align.png`)을 만듭니다.
Figma 없이도 엔진 변경이 실제 화면에서 어떤 후보를 내는지 바로 볼 수 있습니다.

## 자료

| 파일 | 내용 |
|---|---|
| `design_1920x1080.png` | Figma `P8YvnCdGkQLDNVQhW74ZZW` 프레임 `8177:264186` "웹_ 아이디 찾기(휴대전화번호) 화면" export (가짜 브라우저 탭바 157px 포함) |
| `elements.json` | 위 프레임의 요소 목록 (code.js의 collectDesign과 같은 규칙, `use_figma`로 추출) |
| `dev_1920x934.png` | 2026-07-10 개발 캡처 (플레이스홀더·유틸리티·대표이사·WA마크 차이 있음) |
| `dev2_findId_1920x934.png` | 퍼블리싱 `findId.html`을 헤드리스 Chrome 1920×934로 찍은 최신 빌드 (글꼴은 폴백) |
| `design_login_1920x1080.png` / `elements_login.json` | 프레임 `8177:263051` "웹_로그인 화면" |
| `dev_login_1920x934.png` | 퍼블리싱 `login.html` 헤드리스 캡처 |
| `dev_login_chrome_1920x1054.png` | 위 캡처 위에 브라우저 탭·주소창·북마크 띠(120px)를 얹은 합성본 (`make_chrome_capture.html`로 생성). 실제 검수 때 크롬 탭이 찍힌 캡처를 재현 |

## 실행

```bash
cd validation-image-qa/repro
DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html findid
DEV_PNG=dev2_findId_1920x934.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html findid-latest
ELEMENTS_JSON=elements_login.json DESIGN_PNG=design_login_1920x1080.png DEV_PNG=dev_login_1920x934.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html login
```

`DESIGN_MAX`는 code.js의 디자인 export 배율 규칙(최대 4096)을 흉내 냅니다. 결과 JSON에는 디버그용으로
구역별 밀림(`sections`), 요소별 비교값(`units`), 기준 요소 표(`anchorVotes`)가 함께 들어 있습니다.
생성물(`*.json`, `*.overlay.png`, `*.align.png`, `*.harness.html`)은 커밋하지 않습니다.
