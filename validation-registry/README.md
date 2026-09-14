# 규정 대조 시험 세트 — 토큰·컴포넌트 규정

`valueqa/rules.py`(회사 토큰·컴포넌트 규정 대조)가 **잡을 것만 잡고 헛것은 안 내는지** 저장소 안에서 재현한다.
`python3 -m valueqa.selftest` 의 9·10번이 이 폴더로 돈다.

| 파일 | 무엇 |
|---|---|
| `dev-ok.html` | 회사 토큰 안의 값만 쓴 화면. 클래스는 일부러 디자인 시스템 것이 아니다(`.primary-button`). **후보 0** 이어야 한다. |
| `dev-off.html` | 같은 화면에 결함 둘 — 뱃지 배경 `#0073CF`(토큰 밖) · 으뜸 버튼 높이 44→41. **이 둘만** 잡아야 한다. |
| `measure.js` | 두 화면을 헤드리스 크롬으로 재서 `measure-ok.json` · `measure-off.json` 을 만든다 (자는 `capture-extension/collect-core.js` 그대로). |
| `make-design.py` | `measure-ok.json` 에서 촬영 준비 플러그인이 보내는 `검수요소` 모양의 **합성 시안** `design.json` 을 만든다. 버튼 둘은 피그마 인스턴스(`component` 칸)로 둔다. |
| `정본-시험용/` | 진짜 정본의 **모양만** 흉내 낸 아주 작은 것. 오프라인 자가검사용. 진짜 정본은 검수할 때마다 받아온다. |

## 다시 만들기

```
node validation-registry/measure.js        # Chrome 필요 (CHROME_PATH 로 경로 지정 가능)
python3 validation-registry/make-design.py
python3 -m valueqa.selftest
```

## 진짜 정본으로 돌려 보기

```
python3 -m valueqa validation-registry/design.json validation-registry/measure-off.json --정본 auto --지시서 수정요청.md --디자이너 시안확인.md
```

2026-09-14 진짜 정본(커밋 4a05856)으로 돌린 결과: 토큰 색 209 · 간격 21 · 크기 18 · 모서리 10 · 글자크기 8 · 컴포넌트 49(규격 있는 것 37) ·
`dev-ok` 후보 0 · `dev-off` 토큰 밖 1(`#0073CF → --color-brand-blue`) · 규격 1(Button PC MD 44, 지금 41, 시안 정체로 알아봄).
