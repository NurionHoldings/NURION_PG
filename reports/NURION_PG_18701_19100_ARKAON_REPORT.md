# NURION_PG #18701-#19100 ARKAON 선행 구현 보고

## 결론

기존 `HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE` 처분을 수정·삭제하지 않고 재검토 결과를 append-only successor로 연결하는 PostgreSQL 계보를 구현했다. 실제 network partition, failover, fault injection, 운영 DB 쓰기는 수행하거나 주장하지 않는다.

## 안전 계약

- base disposition 및 successor UPDATE/DELETE trigger 거부
- 최초 successor는 exact `(case_id, disposition_id, disposition_digest)` 복합 FK 결속
- 이후 successor는 exact `(case_id, supersession_id, supersession_digest, version)` 자기참조 복합 FK 결속
- DB CHECK로 `version = predecessor_version + 1`
- case별 version·lineage sequence unique
- 단일 chain의 연속성은 DB CHECK `lineage_sequence = version`으로 강제
- partial unique index로 case당 genesis 1개, predecessor당 successor 1개
- 변경 payload, cross-key, predecessor fork, stale-head, alias digest, version gap, sequence reuse 거부
- sequence 재사용과 실제 gap(`version=3`, `lineage_sequence=99`)을 별도 부정 경로로 거부
- aggregate operator view INSERT/UPDATE/DELETE 거부
- 결제·영수증·재시도·승인·실행 권한 모두 false

## ARKAON 극복 지침

| 원인 | 권고 방법 | 대안 | 비용·위험·가역성 | 검증 | 중지·재개·롤백 |
|---|---|---|---|---|---|
| 처분 재검토 필요 | 현재 head digest에 새 successor 추가 | 기존 HOLD 유지 | 낮음·낮음·높음 | exact predecessor FK와 head 1개 | mismatch 시 중지, current head 재검토 후 재개, 트랜잭션 rollback |
| fork/stale 제출 | DB에서 거부 후 current head reload | 기존 계보 보존 | 중간·중간·높음 | unique successor와 단조 version | 동시 successor 발견 시 중지, 새 key/payload로 재개, 기존 행 무변경 |
| multi-node fixture 부재 | isolated primary/standby preflight 유지 | single-node claim false 유지 | 높음·중간·높음 | 향후 partition/failover/role/cleanup 실제 증명 | 통제되지 않은 target 중지, 승인 fixture에서 재개, 정확한 fixture만 폐기 |

## ETHERNIAN 검수 요청

DB 제약이 application-only 검사 없이 race·alias·fork·stale head를 실제 차단하는지, disposable PostgreSQL CI에서 두 행 계보와 current head 1개가 증명되는지 독립 검수한다.

## ETHERNIAN HOLD-001 반영

- 원인: 최초 구현의 `lineage_sequence > 0` + UNIQUE는 재사용만 막고 `2→99` gap을 막지 못했다.
- 권고 수락: 단일 case·단일 chain 모델에 맞춰 `CHECK(lineage_sequence=version)`을 적용했다.
- 대안: predecessor lineage sequence를 복합 FK에 포함하고 `+1` CHECK를 적용할 수 있으나 현재 구조에는 불필요한 열과 복잡도가 늘어난다.
- 비용·위험·가역성: 낮음·낮음·높음. disposable schema에만 적용되며 되돌릴 수 있다.
- 검증: sequence 재사용과 실제 99 gap을 서로 다른 probe/증거 필드로 확인한다.
- 중지·재개·롤백: 어느 probe라도 성공하면 HOLD, 제약 복구 후 fresh fixture 재실행, 실패 트랜잭션 rollback 및 exact schema cleanup.

## ETHERNIAN HOLD-002 반영 — 기존 serializable retry CI flake

- 관측: audit-head CI run `35583496417`에서 기존 retry proof 참가자가 실제 `40001` 이후 3회 모두 충돌해 `RetryExhausted`가 발생했다. 직전 run 1881은 같은 코드로 성공해 timing-dependent flake로 판정했다.
- 원인: 첫 시도의 실제 충돌은 barrier로 의도했지만, loser의 다음 fresh transaction이 winner의 최초 commit 완료 전에 즉시 재진입할 수 있었다. 빠른 재진입은 동일 경쟁 cycle을 반복해 3회 한도를 소진할 수 있다.
- 권고·적용: `max_attempts=3`과 실제 첫 `40001`은 유지하고, 최초 attempt winner가 commit한 뒤 `Event`를 설정하게 했다. retry attempt는 최대 5초 동안 해당 정확한 cycle의 완료만 기다린 뒤 fresh connection으로 진행한다.
- 대안: 고정 sleep/backoff는 머신 부하에 따라 불안정하고 불필요하게 느리므로 비채택했다. max attempts 확대와 예외 무시는 안전 의미를 약화하므로 금지했다.
- 비용·위험·가역성: 낮음·낮음·높음. disposable proof harness 동기화만 바꾸며 운영 로직은 바꾸지 않는다.
- 검증: 실제 PostgreSQL에서 첫 attempt의 exact 40001 1건, loser의 attempt 2 성공, fresh backend PID, 전체 proof PASS를 확인한다. 정적 회귀는 Event wait/set 및 bounded retry 유지 여부를 검사한다.
- 중지·재개·rollback: winner가 5초 내 commit하지 않거나 retry가 실패하면 HOLD한다. 원인 수정 후 새 disposable schema에서 전체 proof를 재개하며, 실패 transaction rollback·connection close·정확한 schema cleanup을 유지한다.
