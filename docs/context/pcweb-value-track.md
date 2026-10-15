---
name: pcweb-value-track
description: PC 웹은 값 대조·앱/PC S/W는 그림 대조로 갈래를 나눈 결정과 feat/windows-capture 작업 위치
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-14T01:22:34.292Z
---

**2026-09-14 확정:** 검수 갈래는 둘이다 — **웹(PC·모바일)은 값 대조**(소스를 읽을 수 있으므로), **모바일 앱·PC S/W는 그림 대조**. 플러그인에서 사람이 네 유형 중 하나를 고른다(짐작하지 않음). 웹은 시안 프레임 폭 그대로 찍는다.

작업 자리: 워크트리 `~/dev-screen-qa-windows`, 가지 `feat/windows-capture` (원격에 올림). 다음 조각 설명은 `capture-app/다음조각-값대조.md` 한 장.

**망 사정(2026-09-14 테스트):** 내부망 PC ↔ 외부망 맥북 직접 통신 불가, 내부망 PC는 USB 자료 전송이 정책으로 막힘(폰 촬영 불가). 그래서 코드는 깃허브 공개 저장소를 통해 내부망으로 내려받는다. **공개 저장소이므로 실제 사이트 주소·계정·검수 자료는 올리지 않는다.**

관련: [[capture-site-rules]] · [[app-capture-rules]] · [[policy-layers]]
