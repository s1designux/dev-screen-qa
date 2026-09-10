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
| `table_mock.html` → `design_table_1200x700.png` / `dev_table_1200x700.png` / `elements_table.json` / `elements_table_noname.json` | **표 화면 목업**(`node make_table_case.js`로 생성). 개발 캡처는 표 데이터·요약 숫자(전체 9,999→9)·상태 칩이 다르고, 진짜 오류 3개(버튼 문구 조회→상세 조회하기 · 컬럼 제목 연락처→담당자 휴대전화번호 · 요약 글자색 파랑→빨강)가 섞여 있다. 요소 목록은 부모 이름 사슬(`chain`)·글자 속성 이름(`propRef`)을 포함하며, `_noname`은 이름 없는 피그마(맨 프레임)를 흉내 낸 것 |

## 실행

```bash
cd validation-image-qa/repro
DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html findid
DEV_PNG=dev2_findId_1920x934.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html findid-latest
ELEMENTS_JSON=elements_login.json DESIGN_PNG=design_login_1920x1080.png DEV_PNG=dev_login_1920x934.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html login
node make_table_case.js   # 표 목업 PNG·요소 목록 생성(최초 1회)
ELEMENTS_JSON=elements_table.json DESIGN_PNG=design_table_1200x700.png DEV_PNG=dev_table_1200x700.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html table
ELEMENTS_JSON=elements_table_noname.json DESIGN_PNG=design_table_1200x700.png DEV_PNG=dev_table_1200x700.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html table-noname
```

`SCREEN_TYPE=common|data`로 화면 종류를 정할 수 있습니다(없으면 프레임 이름으로 추정). 출력의 `(가변 글자 묶음)`은 가변 판정으로 접힌 후보, `{source:가변|고정}`은 판정 근거입니다.
`DESIGN_MAX`는 code.js의 디자인 export 배율 규칙(최대 4096)을 흉내 냅니다. 결과 JSON에는 디버그용으로
구역별 밀림(`sections`), 요소별 비교값(`units`), 기준 요소 표(`anchorVotes`)가 함께 들어 있습니다.
생성물(`*.json`, `*.overlay.png`, `*.align.png`, `*.harness.html`)은 커밋하지 않습니다.

## 로컬 AI(비전 모델) 걸러내기 실험 (2026-09-04)

룰 엔진 대신·옆에 로컬 비전 모델(Qwen2.5-VL 7B, Ollama, 무료·오프라인)을 쓰면 어디까지 되는지 본 실험.
결론: **AI에게 "같냐"를 묻지 않고 "보이는 글자를 읽어라"만 시키고, 같고 다름은 코드가 판정**하면 쓸 만하다.
색은 코드가 픽셀로 재고, 룰 엔진의 '가변' 표시를 그대로 이어받는다. 아이콘 판독은 못 믿는다.

준비: `brew install ollama && ollama serve && ollama pull qwen2.5vl:7b`

| 스크립트 | 하는 일 |
|---|---|
| `vlm_triage.py` | v1 — 후보 조각을 좌우로 붙여 "같냐" 물음 (놓침 많음, 참고용) |
| `vlm_triage2.py` | v2 — 디자인·개발 조각을 **따로** 읽힘 (`python3 vlm_triage2.py findid design_1920x1080.png dev_1920x934.png`) |
| `vlm_judge2.py` | v2.1 — 위 결과에 코드 색 비교 + 룰의 가변 표시를 합쳐 최종 판정 (AI 재호출 없음) |
| `vlm_scan.py` | 후보가 아니라 **모든 글자 요소**를 읽힘 — 룰이 후보를 못 낸 오류도 잡히는지 확인 |
| `vlm_region.py` | **구역 단위**로 양쪽 글자를 전부 읽혀 목록을 맞춤 — 밀림이 구역마다 다른 실제 화면용 |
| `codes_mock.html` / `make_codes_case.js` | 표처럼 생겼지만 값이 고정인 '코드 관리' 목업 (룰 엔진이 진짜 오류 2개를 후보로도 못 내는 사례) |

결과 요약(화면 5개·진짜 오류 27건 전부 잡음, 헛경보는 정렬이 틀어진 로그인 화면에만): 자세한 수치·한계는 메모리 `local-vlm-triage` 참고.
실제 회사 화면 PNG·보고서·조각 이미지는 커밋하지 않는다(.gitignore).
| `vlm_region3.py` + `elements_stay_texts.json` | **환각 안전장치.** 디자인 쪽은 AI로 읽지 않고 피그마 글자를 진실값으로, 개발 쪽은 넓은 읽기∪좁은 조각 읽기, 디자인에 없는 글자는 좁은 조각에서도 나와야 인정. 실제 화면(체류시간 관리) 사용자 확정 8/8·환각 0. 안 됐던 시도: 틀 바꿔 두 번 읽기(`vlm_region.py` consensus — 같은 자리 환각은 두 번 다 나옴), 좌표 대게 하기(Ollama 경유 좌표가 못 믿을 수준) |

## 읽기 층 — `vlm_read.py` (2026-09-07)

로컬 AI 활용방안의 **"AI가 읽고, 검수기가 재고, 규칙이 거른다"** 중 **읽는 층**을 화면에 상관없이 도는 도구로 만든 것.
`vlm_region3.py`가 체류시간 화면 전용이었던 이유(읽을 구역 좌표와 개발 쪽 밀림을 손으로 박아둠)를 없앴다.

| 바뀐 것 | 어떻게 |
|---|---|
| 읽을 구역을 손으로 안 적는다 | 디자인 글자 목록에서 세로로 겹치는 글자끼리 묶어 **가로 띠를 자동 생성**. 같은 칸 수·같은 간격으로 되풀이되는 줄(표 본문)은 **첫 줄만** 읽고 나머지는 이유를 남긴다 |
| 개발 쪽 밀림을 손으로 안 넣는다 | 검수기(`run.js`) 결과 JSON의 겹치기 값(`model.tx/ty/s`, `range.captureTop`)을 그대로 써서 디자인 좌표 → 개발 좌표로 옮긴다 |
| 다시 읽지 않는다 | 조각 그림+물음을 해시로 `vlm_read_cache/`에 저장. 코드를 고쳐 다시 돌려도 이미 읽은 조각은 0초 |
| 결과 모양이 같다 | 화면과 무관하게 `only_design / only_dev / spacing / need_check / dropped` + 좌표 |
| 헛일을 안 한다 | `--skip-above 0.95` 로 겹치기가 잘 맞은 화면은 AI를 아예 부르지 않는다. 점수 0.85 미만이면 결과에 '정렬 확인 필요'를 남긴다 |

읽는 방식 자체는 검증된 v3 그대로다 — 디자인 쪽은 AI로 읽지 않고 **피그마 글자를 진실값**으로,
개발 쪽은 **넓은 읽기 ∪ 좁은 조각 읽기**, 디자인에 없는 개발 글자는 **좁은 조각에서도 나와야** 인정(환각 버림).
후처리: 다른 글자의 토막은 버리고, 한 글자·디자인 글자와 한 글자 차이는 '확인 필요'로 뺀다.

```bash
# 무엇을 몇 분에 읽을지 먼저 보기(AI 안 부름)
python3 vlm_read.py --elements elements_stay_full.json --dev dev_stay_1920x1081.png \
                    --align stay-policy.json --out vlm_read_stay.json --dry-run
# 실제 읽기
python3 vlm_read.py --elements elements_stay_full.json --dev dev_stay_1920x1081.png \
                    --align stay-policy.json --out vlm_read_stay.json
# 채점 — 사람이 확정한 정답이 다 남았는지 (만든 사람이 스스로 정하지 않는다)
python3 vlm_read_score.py vlm_read_stay.json answers_stay.json
```

`answers_stay.json`은 river님이 2026-09-04에 직접 확인한 **진짜 오류 8건 + 오류 아닌 것 2건**이다(채점 기준).
산출물(`vlm_read_*.json`, `vlm_read_cache/`, `*.log`)은 커밋하지 않는다.

## 새 화면 한 장을 통째로 돌리기 — `run_screen.sh` (2026-09-08)

```bash
# elements_<이름>.json + 디자인/개발 PNG 를 먼저 준비한 뒤
./run_screen.sh route design_route_1920x1080.png dev_route_1920x1080.png 99
```

① 검수기(겹치기·자 재기) → ② 읽을 구역·예상 시간 확인 → ③ 로컬 AI 읽기(백그라운드) → ④ 어긋난 것 세기.
네 번째 인자 `FORCE_TY`는 **자동 겹치기가 실패하는 화면의 계측용**이다(운영 방식 아님).

피그마에서 요소 목록을 조각으로 받아왔다면 `extract/assemble.py <접두사> elements_<이름>.json` 으로 먼저 합친다.
규칙 제안·승인 기록은 `RULE_PROPOSALS.md` 에 남긴다.

## 포털 엔진 동일성 재기 (portal_parity.js)

포털이 내보내는 엔진(`/engine/ui.html` = 플러그인 ui.html + 포털 손잡이)이 플러그인 재현과 같은 후보를 내는지 잰다.

```
ELEMENTS_JSON=… DESIGN_PNG=… DEV_PNG=… DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html base_x
ELEMENTS_JSON=… DESIGN_PNG=… DEV_PNG=… node portal_parity.js base_x.json portal_x
node answers_check.js portal_x.json   # 체류시간 정답 생존
```
후보 번호·종류·상태·사유·상자·디자인 노드가 모두 같아야 `PARITY OK`.
