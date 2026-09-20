# NURION_PG #14301~#14700 ARKAON 선행 결과

## 자율 결정

- 단계명: **복합계획 신원·이중 승인인텐트 봉투 게이트**
- 원인: 직전 receipt schema가 plan identity를 직접 포함하지 않았고, materialization/execution 승인 게이트가 독립 actor·순서·nonce·재생영역을 구조적으로 결속하지 않았다.
- 경계: 승인 receipt 발급, fixture bytes, materialization, probe, observation, PASS/FAIL, 결론·추천·선택·수락·해결 권한을 모두 금지했다.

## 구현

- 16×25, 정확히 400 controls
- 20 materialization + 20 execution PENDING intent envelopes
- routed 16건에 대해 32 append-only human holds와 64 recovery paths
- `plan_id + flow + kind + source_contract_digest + readiness_manifest_digest` 복합 identity
- approval kind별 독립 actor, counter actor, sequence precondition, predecessor, nonce/replay scope
- 공통 final-docket invariant interface 및 전체 lineage
- source/latest/order/concurrency/partial batch fail-closed와 full downstream rehash 차단
- 12단계 stage snapshot chain, 과거 stage snapshot 불변

## 되는 방향 가이드

1. 최소 봉투 보수: 불일치 identity/sequence만 원천 plan에서 재구성하고 독립 schema 검증 후 새 nonce scope로 재개한다.
2. 이중 인텐트 전면 재구성: 교차 actor/replay 모호성이 있으면 두 후보를 격리하고 새 독립 actor·sequence로 함께 재구성한다.

각 경로는 원인, 비용, 위험, 가역성, 검증, 중단, 재개, rollback을 content-address한다. 어느 경로도 선택·추천·승인을 자동화하지 않는다.

## 검수 요청

에테르니언은 복합 identity의 직접 결속, 두 intent의 독립성, replay 차단, final docket 불변식, 실제 receipt/실행 0건을 독립 검수해야 한다.

## HOLD 보완 이력

- 원인: routed 동일 봉투 재시도 시 현재 key의 actor까지 occupied 집합에 포함해 정상 idempotent retry를 충돌로 오인했다.
- 적용: 현재 key를 actor·ID·nonce 충돌 집합에서 제외하고 동일 후보는 같은 객체로 반환하며, 같은 key의 envelope ID 또는 actor 변경은 명시적 conflict로 거부한다.
- 검증: routed materialization/execution 병렬 동일 요청 수렴, 같은 key 변경 충돌, 다른 key ID 재사용 API 거부, nonce full-rehash 재사용 거부를 추가했다.
- 후속 구조개선: 별도 idempotency-key schema 도입은 실제 receipt 단계 이전의 독립 설계 과제로 유지한다.
- 재검수 원인: 과거 #13901 evidence runner가 전역 snapshot 개수와 마지막 stage를 고정해 미래 #14301 snapshot 추가 시 실패했다.
- 적용: 공용 `validated_stage_chain_through(max_end)`가 각 runner의 불변 stage 경계까지만 선택·검증하며, 과거 runner의 전역 latest 가정을 제거했다.
