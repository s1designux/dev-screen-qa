---
name: rule-verdict-log
description: 판정↔규칙 잇기 — 후보마다 규칙 이름표, 사람 판정마다 agree/overturn 한 행, 규칙 성적표
metadata:
  type: project
---

검수 정책 규칙화 ③ 조각(2026-09-14 완료). 검수기가 후보마다 어느 규칙이 그 자리에 뒀는지 이름표(`policy.source`)를 붙이고,
포털은 사람이 제외·가변·되돌림·지적 등록을 누를 때마다 `rule_verdict`에 한 행씩 쌓는다(`mvp0/rule_log.py`, append-only).
엔진이 둔 자리와 같으면 agree, 다르면 overturn. `/policy`와 `/policy/screen/<uuid>` 맨 아래 '규칙 성적' 표에서 규칙별 숫자를 본다.

이름표가 새로 붙은 것: 제외표(designChrome·tabStrip·manual), 가려서 안 보임(occluded), 선택된 탭(tabSelected),
표 본문 값(rowValueMissing). 예전에는 이것들이 전부 이름 없이 사유 문장만 남아 어느 규칙이 틀렸는지 셀 수 없었다.

검증: 자체검사 209 통과, 화면 10개 회귀에서 후보 목록이 이전 엔진과 **글자 하나까지 동일**(합계 316, 체류시간 정답 7/7).
이름표 덮인 후보 580개 중 '규칙 없음'은 133개만 남았다. 기준 파일 `base_*.json`은 낡아 316이 아니라 331을 가리키니
회귀 비교는 HEAD 엔진으로 새로 재서 견주는 편이 맞다.

**Why:** ④(규칙 발굴)·⑤(제안+검증 숫자)가 이 기록을 재료로 쓴다.
**How to apply:** 규칙을 고칠 후보는 '뒤집음'이 많은 줄. 단 여기서 자동으로 고치지 않는다 — [[policy-layers]], [[image-qa-policy-rules]].
