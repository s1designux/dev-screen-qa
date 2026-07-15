# 검수 시스템 — 프로젝트 컨텍스트 (CLAUDE.md)

이 문서는 "디자인 시안 대 개발화면 검수 시스템"의 **확정된 설계 결정**이다.
코딩 에이전트는 이 결정들을 재논의하지 말고 전제로 삼는다.
특히 4번 "하지 말 것"을 반드시 지킨다. 지시가 모호하면 여기 원칙에 맞춰 판단하고, 그래도 애매하면 멈추고 물어본다.

---

## 1. 프로젝트 목적

- 디자인 시안과 실제 개발화면이 동일하게 구현됐는지 검수한다.
- 검수 결과·수정 이력을 **데이터로 축적·관리**한다. (검색·통계·차수 연결이 목적)
- 단순 이미지 비교 도구가 아니라 프로젝트별 검수 데이터 관리 시스템이다.
- 대상: PC 웹 / 모바일 웹 / Android / iOS.

---

## 2. 절대 원칙 (North Star) — 절대 어기지 않는다

1. **데이터가 원본이다.** 검수 결과는 구조화된 데이터(DB)에 저장하고, HTML·Figma·PDF는 그 데이터를 렌더링한 출력물일 뿐이다. Figma 파일이나 PDF를 원본으로 삼지 않는다.
2. **자동 검수는 오류를 "확정"하지 않는다.** "후보"만 생성하고, 최종 확정은 항상 사람(디자이너)이 한다. 신뢰도 점수를 함께 제공한다.
3. **이력은 삭제하지 않는다.** 해결된 오류도 지우지 않고 상태만 바꾼다. 화면에서 숨길 수는 있으나 데이터는 남긴다.

---

## 3. 확정된 아키텍처 결정

- **중심은 HTML 포털.** 운영·데이터 관리·커뮤니케이션의 허브. Figma는 얇은 보조, PDF는 특정 시점 스냅샷(공식 결과서).
- **순서: 검수 데이터화가 자동 검수보다 먼저.** 데이터/이력 기반이 없으면 자동 검수 결과가 갈 곳이 없다.
- **웹과 앱: 데이터·이슈 포맷은 통일, 수집·비교 엔진은 분리.** 하나의 엔진으로 억지로 합치지 않는다.
- **앱 검수는 완전 자동이 아니라 "OCR 보조 + 디자이너 확정".** 한국어 UI이므로 OCR은 PaddleOCR 사용.
- **화면 ID는 2단계.** 디자인 기준 ID ↔ 개발 실행 키를 포털에서 1회 매핑. 개발자가 코드에 디자인 ID를 넣게 하지 않는다.
- **검수 정책은 3계층 상속.** 시스템 기본값 → 화면별 예외 → 요소별 예외. 디자이너가 평소 거의 설정하지 않게 한다.
- **UI 사양서 시스템과 검수 시스템은 공통 화면 ID로 느슨하게 연결.** 처음부터 한 스키마로 합치지 않는다.
- **Figma 연동: 읽기는 REST/링크 붙여넣기, 쓰기(검수보드 역생성)는 플러그인(나중).**

---

## 4. 하지 말 것 (범위 가드레일) — 명시적 지시가 있어도 현재 단계에선 만들지 않는다

- ❌ Figma 플러그인 (지금 만들지 않음. "포털 이슈 → Figma 보드 역생성"은 나중 단계 전용 기능)
- ❌ 웹 자동 수집·비교 엔진 (Playwright 자동화는 PoC 통과 후)
- ❌ 앱 구조 추출 (ADB/UI Automator/접근성 트리는 별도 검증 스파이크. 기본은 스크린샷+OCR)
- ❌ UI 사양서 + 검수결과서를 하나의 거대 스키마로 통합
- ❌ 오류를 자동으로 "확정" 처리
- ❌ Figma 파일에 검수 데이터·대용량 이미지 저장
- ❌ 모든 요소에 강제 ID 부여
- ❌ 여러 화면·여러 해상도 동시 지원 (MVP0은 단일 화면 흐름으로 검증)

새 기능을 만들고 싶으면 먼저 멈추고, 현재 단계 범위인지 확인받는다.

---

## 5. 빌드 순서 (현재 단계: **MVP0**)

- **MVP0 (현재):** 데이터 모델 + 수동 기반 검수 데이터화. 자동화 없음.
- MVP1: 검수 정책 3계층 + 동적/제외 영역.
- MVP2: Figma 플러그인 (얇게, 검수보드 역생성 중심). *디자이너가 원할 때만.*
- MVP3: 웹 자동 수집·비교 (Playwright). *PoC 통과 후.*
- MVP4: 개발 커뮤니케이션 확장 (댓글·수정완료·재검수·빌드 연결).
- MVP5a: 앱 OCR 트리아지 / MVP5b: 앱 구조 추출 (스파이크, 미확정).
- MVP6: 사양서 연동·토큰/컴포넌트 준수·반복오류 분석.

---

## 6. 데이터 모델 (MVP0 대상)

MVP0 핵심 엔티티. (Capture / DesignVersion / DevelopmentBuild 등은 필드만 남기고 최소화, 나중 확장)

- **Project**: `uuid, name`
- **Screen**: `uuid, project_id, human_key(예: CV-WEB-012), name, platform, dev_keys[], states[], variants[]`
- **ElementMapping**: `screen_uuid, design_node_id, dev_element_key` (디자인 노드 ↔ 개발 요소, 1회 매핑)
- **InspectionRun**: `uuid, screen_id, round(1/2/3), inspector, created_at, pass_fail`
- **InspectionIssue**: `uuid, screen_id, run_id, logical_element_key, box{x,y,w,h}, category, expected, actual, description, severity, status, found_round, resolved_round, dedup_key`
- **IssueHistory**: `uuid, issue_id, from_status, to_status, actor, at, note` (append-only, 삭제 금지)
- **ComparisonPolicy**: `scope(system/screen/element), target, mode` (MVP0에선 스텁, MVP1에서 확장)

**오류 상태값**: 발견 / 개발확인 / 수정예정 / 수정완료 / 재검수필요 / 검수완료 / 보류 / 오류아님 / 재발

**dedup_key (차수 간 동일 오류 연결의 핵심)**: `{화면}|{요소식별자}|{규칙}|{속성}`
재검수 시 새 오류를 만들지 않고 이 키로 기존 오류를 찾아 상태만 갱신한다.

```json
{
  "uuid": "8f1c...",
  "screen_id": "CV-WEB-012",
  "run_id": "run-2",
  "logical_element_key": "CV-WEB-012/header/title#0",
  "box": { "x": 120, "y": 340, "w": 88, "h": 24 },
  "category": "typography-font-size",
  "expected": "14px / 500",
  "actual": "16px / 500",
  "description": "타이틀 폰트 크기 불일치",
  "severity": "major",
  "status": "재검수필요",
  "found_round": 1,
  "resolved_round": null,
  "dedup_key": "CV-WEB-012|header/title|typography-difference|font-size"
}
```

---

## 7. 화면·요소 ID 규칙

- **사람이 읽는 키와 내부 UUID를 분리한다.** 사람키는 라벨·조회용(바뀔 수 있음), 참조 무결성은 UUID가 담당.
- 화면 사람키: `{SERVICE}-{PLATFORM}-{NNN}` (예: `CV-WEB-012`).
- 화면 상태는 접미사: `CV-WEB-012@empty`. 디바이스/해상도는 화면 ID에 넣지 말고 **변형(variant)** 으로 분리.
- 개발 실행 키: 코드에 이미 있는 값 그대로 사용 (웹 route `/monitoring/live`, Android `LiveMonitoringActivity`, iOS `LiveMonitoringViewController`). 화면 UUID에 매핑.
- 요소 논리키: `{화면}+{역할/컴포넌트}+{텍스트해시}+{순번}`. 명시적 QA/접근성 id가 있으면 그것이 최우선.

---

## 8. 검수 정책 3계층 (MVP1에서 본격 구현, MVP0은 개념만 반영)

`시스템 기본값 → 화면별 예외 → 요소별 예외` 순으로 덮어쓴다.
모드: `Exact / Text Exact / Style Only / Layout Only / Structure / Dynamic / Ignore`.
기본값 예: 지도 타일=Ignore, 지도 컨테이너=Layout Only, 사용자명=Style Only, 날짜=Dynamic, 버튼·아이콘=Exact, 영상 썸네일=콘텐츠 Ignore+Layout.

---

## 9. 웹/앱 검수 분리 원칙 (지금은 구현 안 함, 설계만 고정)

- 웹(나중): DOM/CSS 구조 비교 우선(픽셀 아님) → 후보 생성.
- 앱(나중): 스크린샷 + PaddleOCR + 색상·영역·레이아웃 비교 → 후보 생성 → 디자이너 확정.
  - Android는 협조 없이도 ADB `uiautomator dump`로 구조 일부 추출 가능성 있음(검증 대상).
  - iOS는 개발 협조 없이는 구조 추출 어려움. 이미지+OCR 기본.
- **웹·Android·iOS를 하나의 정확도 목표로 잡지 않는다.**

---

## 10. Figma 연동 경계

- **읽기(Figma → 포털):** REST API 또는 프레임 링크 붙여넣기(링크에서 file_key·node_id 추출, node-id 하이픈→콜론 변환)로 이미지·노드값을 당겨온다. 플러그인 불필요.
- **쓰기(포털 → Figma 검수보드 역생성):** 플러그인만 가능. 나중 단계 전용.
- 확인 필요(포털 구현 시): **디자이너 PC가 아니라 포털 서버가 Figma에 직접 닿는지**. 안 닿으면 링크 붙여넣기/플러그인 경유로 우회.

---

## 11. 기술 제약

- 폐쇄망(인트라넷), 오프라인 로컬 실행. **유료 외부 API 사용 금지.**
- OCR: PaddleOCR (한국어). / 웹 캡처(나중): Playwright.
- MVP0 저장소: 가벼운 로컬(SQLite 또는 JSON 파일) 권장. 확정 스택은 첫 작업 착수 시 제안·확인.
- 모든 라이브러리는 오프라인 설치 가능 여부를 먼저 확인.

---

## 12. 작업 규율

- `git add .` 금지. **선택 스테이징만.**
- 커밋 전 **멈추고 보고(stop-and-report)**, 자체 판단으로 커밋하지 않는다.
- **만든 것을 스스로 검증하지 않는다 (maker ≠ verifier).** 검증은 분리된 주체가 한다.
- 자동 검수 결과를 스스로 "확정"으로 승격하지 않는다.

---

## 13. 지금 할 일 (즉시 작업)

**과거 검수 1건을 6번 스키마로 변환한다.** (스키마가 실제로 서는지 검증하는 첫 단추)
- 입력: 실제 과거 검수 보드(디자인·개발 이미지, 1·2차 오류, 해결/미해결, 스토리보드 ID).
- 산출: 위 데이터 모델을 따른 실제 데이터(JSON 또는 SQLite) + 이를 다루는 최소 스크립트.

---

## 14. 완료 기준 (MVP0 Definition of Done)

과거 검수 1건을 데이터로 넣었을 때 아래가 모두 된다:
1. 1차 오류와 2차 오류가 `dedup_key`로 연결된다.
2. 해결된 오류를 삭제하지 않고 숨길 수 있다(상태 유지).
3. "현재 미해결 오류만" 추출된다.
4. 그 데이터로 가로 A4 형태의 검수결과서를 다시 생성할 수 있다.
