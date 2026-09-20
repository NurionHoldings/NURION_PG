# NURION_PG #13101~#13500 ARKAON 결과

## 자율 진단과 단계 결정

최종 단계명은 `자동 스냅샷 체인·미확정 원인 진단 프리플라이트`다. 직전 구현은 개별 snapshot은 검증했지만 mapping 전체의 중복·공백·lesson 회귀를 검증하지 않았고, 복구 가이드가 공통 원인에 머물러 대안별 실행 전 검증 가능성과 실질적 차별성을 증명하지 못했다. 최초 구현의 인덱스 순환 원인 분류도 에테르니언 HOLD에 따라 제거했다.

## 수정 방향과 극복안

- 최소 안전안: 전체 stage mapping을 정렬해 연속성·비중복·lesson 단조 증가를 자동 검증하고, 원천 guidance·challenge·snapshot과 probe 상태를 cause evidence에 결속한다.
- 현재 probe는 실행되지 않았으므로 16개 routed 사례 모두 `CAUSE_UNDETERMINED`로 유지한다. 확정 해결안 대신 진단 최소안과 독립 원인 재검증안을 제공한다.
- 구조 개선안: 추후 stage descriptor를 단일 선언 원천으로 생성해 validator·runner·문서의 수동 동기화도 제거한다.
- 각 안은 source/cause, UNVERIFIED 가정, 반증시험, 중단조건, preflight, 검증기준, 잔여위험, 비용·위험·가역성, escalation, rollback·재개조건을 자체 digest에 포함한다.

## 결과

- lesson/remediation: `ARL-13101-001` / `ETH-13101-AUDIT-001`
- 400 controls: 16 workstreams × 25 aspects
- 20 audits: 4 N/A + 16 routed
- 32 diagnostic options, 16 `CAUSE_UNDETERMINED`, 16 append-only human holds
- source/latest/order/concurrency/partial-batch fail-closed와 이전 전체 actor lineage 유지
- 추천·선택·결론·수락·해결·승인·실행 권한 없음
- 실제 외부/PG/금융/원장/credential/deploy 호출 없음

본 문서는 아르카온의 선행 구현 결과이며 에테르니언의 승인 문서가 아니다.
