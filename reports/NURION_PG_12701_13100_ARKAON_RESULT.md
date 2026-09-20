# NURION_PG #12701~#13100 ARKAON 결과

## 아르카온 선행 결론

단계명은 `단계별 교훈 스냅샷·가이드형 복구경로 감사`로 정했다. 직전 계층은 선택지별 방법론을 강하게 결속했지만, 새 lesson이 전역 exact tuple에 추가될 때 과거 evidence chain이 함께 깨지는 구조와 `HOLD`가 통과 가능한 경로를 기계적으로 보장하지 못하는 한계가 있었다.

## 선택한 수정 방향

- 최소 안전안: live registry 전체 검증과 단계별 required lesson subset을 분리하고, 과거 `#9901~#12700`은 `ARKAON-LESSONS-12301`로 동결한다. `ARL-12701-001`을 과거 진입점에 전파하지 않는다.
- 구조 개선안: 명시적 stage mapping을 content-address하고 새 계층은 `ARKAON-LESSONS-12701`과 단계 범위·선행 registry snapshot·manifest·원천 docket으로 재구성 가능한 predecessor snapshot을 고정한다.
- 가이드 강화: routed 사례마다 실패 원인, 비구속 안전후보, 정확히 2개 극복경로와 가정·반증시험·중단조건·검증기준·잔여위험·비용/위험/가역성·escalation·rollback/재개조건을 content-addressed로 결속한다.

## 극복안

1. `MINIMAL_SAFE_BINDING`: 비용 LOW, 가역성 HIGH. 기존 계보를 최소 변경으로 복구하지만 lesson 전파 drift가 잔여위험이다.
2. `STAGE_VERSIONED_SNAPSHOT`: 비용 MEDIUM, 가역성 HIGH. 단계별 독립성을 높이지만 전체 과거 runner migration 복잡성이 잔여위험이다.

에테르니언 HOLD에 따라 권장안인 단계별 snapshot 분리를 적용했다. 가상의 `ARL-FUTURE-001` validated superset을 추가해도 과거 stage lesson tuple·snapshot digest·evidence payload/checksum이 불변임을 검증했고, 명시적 mapping 갱신 없이 신규 lesson을 현 단계에 적용했다고 주장하는 경우 fail-closed로 거부한다.

두 안 모두 가정은 미검증으로 표시하고 원천 재구성 비교를 반증시험으로 삼는다. digest/semantic 불일치 시 중단하고 인간 검토로 escalation하며, 실행 없이 이전 docket을 보존한다. 모든 검증기준 통과와 인간 gate 전에는 재개하지 않는다. 안전후보 표시는 비구속이며 추천·선택 권한이 아니다.

## 자기감사

- lesson: `ARL-12701-001`
- remediation: `ETH-12701-AUDIT-001`
- 400 controls: 16 workstreams × 25 aspects
- 20 guidance: 4 N/A + 16 routed
- 32 recovery alternatives, 16 append-only holds
- 실제 PG·외부·금융·원장·credential·deploy 및 판단 권한: 0

## 검증 결과

- 전용·인접·lesson 검증: 74 PASS
- 전체 회귀: 1,756 PASS
- governance·lesson registry·compileall·diff-check: PASS
- #9901~#13100 연속 8단계 evidence: PASS
- 최종 evidence SHA-256: `a48177b78a0dc942bc029202affe552858a29376f095ddc237ca38f43b5a53dd`

최종 수락·승인·커밋·푸시·PR·병합·배포는 수행하지 않았으며 에테르니언 독립검수 대상으로 넘긴다.
