# NURION_PG #14701~#15100 ARKAON 선행 결과

## 자율 결정

- 단계명: **비발급 승인영수증 스키마·독립 멱등키 계약**
- 원인: 직전 PENDING intent는 복합 신원과 nonce를 결속했지만, 실제 발급 전 단계의 receipt schema와 caller idempotency key의 payload 충돌·교차 key 재사용 계약이 없었다.
- 경계: receipt ID/digest 발급, fixture materialization, probe/execution, observation, PASS/FAIL, 승인·활성화·배포를 모두 0으로 유지한다.

## 구현

- 16×25, 정확히 400 controls
- 40개 intent에 40개 schema-only 계약과 40개 독립 idempotency key scope
- plan/flow/kind/source contract/readiness manifest/composite identity/source intent/actor slots/intent kind/sequence/predecessor/nonce 직접 결속
- 같은 key·같은 payload 직렬/20-way 병렬 멱등 수렴
- 같은 key·다른 payload conflict, 다른 key의 schema identity 재사용 fail-closed
- routed 32건의 append-only hold와 64개 content-addressed recovery paths
- partial batch/order swap, forged receipt/authority, full downstream rehash 음성시험
- #9901~#15100의 13번째 직접 stage snapshot

## 과거 evidence 미래 불변성 보완

- 영향조사 결과 live registry exact equality 미이관은 #7501 answer-material runner 1개였다.
- 권장 최소안으로 해당 runner만 당시 12개 lesson을 고정한 `ARKAON-LESSONS-7501` immutable historical snapshot으로 이관했다. #9901 이후 직접 연속 계보와 역사 snapshot을 분리해 양쪽 의미를 보존했다.
- 대안인 전체 runner 일괄 수정은 변경량·회귀위험이 커서 적용하지 않았다.
- 비용은 낮고 변경은 runner/validator registry 수준이라 가역적이다. stage payload digest 미래불변 회귀시험으로 검증하며, 경계 snapshot 누락·공백·lesson 회귀 시 즉시 중단한다. rollback은 runner 변경만 되돌리고 기존 stage evidence를 보존하는 것이다.

## 되는 방향 가이드

1. 권장 `REBUILD_SINGLE_SCHEMA`: 불일치 schema/key scope만 intact source intent에서 재파생하고 독립 검증 후 fresh key로 재개한다.
2. 대안 `RECONSTRUCT_DUAL_SCHEMA_PAIR`: materialization/execution predecessor 또는 replay가 모호하면 두 후보를 격리하고 distinct key/role slots로 순서대로 재구성한다.

두 경로 모두 원인, 권장 여부, 비용·위험·가역성, 검증, 중단·재개·rollback을 결속하며 자동 선택·승인·발급하지 않는다.

## 검수 요청

에테르니언은 source identity와 idempotency scope의 직접 결속, 직렬/병렬 멱등성, cross-key 재사용 차단, 미래 registry 불변성, 실제 receipt/실행/관찰 0건을 독립 검수해야 한다.

## 에테르니언 HOLD 보완 이력

- 원인: receipt role과 source actor를 namespace prefix로만 분리해 동일 suffix alias가 허용됐다.
- 권장안 적용: 모든 source envelope actor/counter actor, 전체 issuer/verifier, final compiler/validator를 `_id` 기준 단일 전역 충돌영역으로 통합했다.
- 비권장 대안: 현재 key source actor만 비교하면 다른 key alias를 놓치므로 채택하지 않았다.
- 비용·위험·가역성: 소규모 검증 강화이며 데이터 마이그레이션이 없고 기존 고유 fixture는 유지되어 위험이 낮고 가역성이 높다.
- 검증: current actor→issuer, current counter→verifier, 다른 key actor alias, full-rehash alias를 거부하고 routed materialization/execution 각각 20-way 멱등수렴을 확인한다.
- 중단·재개·rollback: alias 또는 기존 fixture 충돌 시 중단하고 고유 suffix로 재발급 후 전체 chain을 검증해 재개하며, 필요 시 충돌검사 패치만 되돌리고 schema 후보는 폐기한다.
