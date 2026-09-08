# [새 세션용] 검수 정책 규칙화 — 다음 조각

## 0. 먼저 할 일
- 저장소 루트 `/Users/designgroup_02/dev-screen-qa` 의 `CLAUDE.md` 를 읽고 전제로 삼는다.
- 브랜치 `feat/image-qa-bottom-range` · 작업 폴더 `validation-image-qa/repro/`
- `RULE_PROPOSALS.md` 를 읽는다(#1 승인·적용, #2 관찰만, #3·#4 확인 기록).
- 마지막 커밋: `37f427d`

## 1. 여기까지 끝난 것 (2026-09-08)

기본 규칙 4줄이 **전부 실제 화면으로 검증됐다.** 규칙을 하나씩 꺼서 화면 10개를 다시 돌려 쟀다.

| 기본 규칙 | 상태 | 껐을 때 |
|---|---|---|
| 표 **컬럼 제목** 고정 | ✅ 검증됨 | 체류시간 정답 4건이 표 본문에 휩쓸려 사라짐 |
| 표 **본문 값**은 가변 | ✅ 검증됨 | 정답은 그대로인데 볼 것이 화면당 20~37% 늘어남(노선관리 314→498) |
| **메뉴 이름** 고정 | ✅ 유지 승인(river) | 정답 생존엔 영향 없음. 메뉴 글자 8개가 데이터 자리로 뒤집힘 |
| 가짜 브라우저 틀·작업표시줄 제외 | ✅ 검증됨 | (#3) 3화면에서 사람 설정 없이 자동으로 걸림 |
| (추가) 표 **항목 이름** 고정 | ✅ 승인·적용됨 | (#1) |

숫자·재현법은 `RULE_PROPOSALS.md` #4에, 눈으로 보는 자료는 `rule_check_report.html`(커밋 안 함)에 있다.

## 2. 이 조각에서 할 일 (한 줄)
**아직 남은 병목은 "사람이 볼 것 148건"이다.** 이게 무엇들인지 분류해 **다음 규칙 후보를 숫자와 함께** 올린다.

- 체류시간 화면 현재: 후보 239 / 숨김 91 / **볼 것 148**. 목표였던 93건보다 오히려 많다
  (정답 2건을 살리려고 표 컬럼 제목을 올린 결과 — 의도된 것이지만 그만큼 사람 일이 남았다는 뜻).
- 노선관리는 **볼 것 314건**. 실무에서 이 숫자로는 못 쓴다.
- 그러니 다음 규칙은 "무엇을 더 고정으로 볼까"가 아니라 **"이 314·148건이 대체 무엇이냐"**에서 나온다.

**하는 순서**
1. `m_<화면>_base.json` 의 볼 것(status가 `variable`/`excluded`가 아닌 것)을 **종류(kind)·자리·이유별로 세어** 표로 만든다.
2. 가장 큰 덩어리 2~3개를 골라, **그게 진짜 오류인지 사람이 볼 필요 없는 것인지** 캡처를 잘라 눈으로 확인한다.
3. 규칙 후보가 보이면 `RULE_PROPOSALS.md` 양식대로 **효과를 재서**(끄고/켜고, 화면 10개 회귀, 정답 8건 생존) 올린다.
4. **river님 승인 후에만** 원본 `plugin-image-qa/ui.html` 에 반영한다.

## 3. 쓸 수 있는 자료 (이미 폴더에 있음 · 커밋 안 됨)
화면 10개가 바로 돌아간다. 요소 목록·PNG 이름은 `README.md` 참조.
`board`(게시판) · `vehicle`(차량위치) · `dash`(대시보드) · `door`(출입문) ·
`stay`(체류시간) · `findid` · `login` · `table` · `codes` · `route`(노선관리, `FORCE_TY=99` 필요)

**주의:** `elements_route.json` 은 286줄이 빠진 옛 파일이다. **`elements_route_plugin.json`(완전본)을 쓴다.**
체류시간은 `elements_stay_full.json`(752줄)을 쓴다.

10개를 한 번에 돌리는 방법(각 화면 env는 이 파일 4절 표와 같다):
```bash
ELEMENTS_JSON=elements_stay_full.json DESIGN_PNG=design_stay_1920x1080.png \
DEV_PNG=dev_stay_1920x1081.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html m_stay_base
```

## 4. 화면별 실행값 (2026-09-08 기준선)

| 화면 | elements | 디자인 PNG | 개발 PNG | FORCE_TY | 후보/숨김/볼것 |
|---|---|---|---|---|---|
| board | elements_board.json | design_board_1920x1898.png | dev_board_1920x1816.png | – | 138 / 72 / 66 |
| vehicle | elements_vehicle.json | design_vehicle_720x1560.png | dev_vehicle_360x780.png | – | 73 / 11 / 62 |
| dash | elements_dash.json | design_dash_360x1071.png | dev_dash_360x1031.png | – | 39 / 20 / 19 |
| door | elements_door.json | design_door_186x400.png | dev_door_196x436.png | – | 21 / 8 / 13 |
| stay | elements_stay_full.json | design_stay_1920x1080.png | dev_stay_1920x1081.png | – | 239 / 91 / 148 |
| findid | elements.json | design_1920x1080.png | dev_1920x934.png | – | 13 / 0 / 13 |
| login | elements_login.json | design_login_1920x1080.png | dev_login_1920x934.png | – | 6 / 0 / 6 |
| table | elements_table.json | design_table_1200x700.png | dev_table_1200x700.png | – | 12 / 9 / 3 |
| codes | elements_codes.json | design_codes_1200x760.png | dev_codes_1200x760.png | – | 3 / 0 / 3 |
| route | elements_route_plugin.json | design_route_1920x1080.png | dev_route_1920x1080.png | 99 | 533 / 219 / 314 |

## 5. 세는 기준 (이번에 통일함)
- **볼 것** = 후보의 `status`가 `variable`·`excluded`가 **아닌** 것.
- `policy` 문자열에 '가변'이 들어갔다고 다 숨겨지는 게 아니다(글자 내용류 후보만 접힌다).
  예전 기록의 '가변접힘' 숫자와 이 숫자는 다르다 — **`status`로 센다.**
- 규칙 하나의 효과는 **끄고 재는 것**이 제일 정확하다(`ui.html` 사본에서 해당 `test` 첫 줄에 `return null;`).

## 6. 알아둘 것
- 겹치기가 틀어진 화면의 결과는 헛것이다. `*.align.png` 를 **눈으로** 먼저 본다.
- 대시보드는 아래로 갈수록 20~25px 밀린다 → 아래쪽 결과 신뢰도 낮음.
- 출입문은 겹치기 0.77·디자인 3줄↔개발 6줄이라 **근거로 쓰지 않는다.**
- 로컬 AI 읽기는 화면당 7~20분, 한 번에 하나만 돌린다(Ollama가 하나뿐).
  AI의 **띄어쓰기 판독은 못 믿는다**(3건 중 1건). 반드시 캡처를 잘라 눈으로 확인한다.
- 로고 워드마크 누락·탭 10→4는 정책이 아니라 **엔진이 후보를 못 내는 별건**이다.
- 보고는 **① 결과(표·이미지) ② 결정할 것** 두 칸뿐. 비교·검수는 말로 설명하지 말고 이미지나 HTML로 만든다.
- `git add .` 금지. 회사 화면 자료·산출물은 커밋하지 않는다. 커밋 전 멈추고 보고.

## 7. 이 조각이 끝나면 (CLAUDE.md 21번 대기열)
1. `plugin-image-qa/` 1.0 나머지 — 번호 중심 패널 / 캔버스 포인팅 / 디자인 원본값 표시
2. 차수 연동 2차 — 새 차수 추가 + 이전 지적 끌고와 사람이 판단
3. 실제 검수 데이터 더 넣기 → 4. A4 반출 본구현
