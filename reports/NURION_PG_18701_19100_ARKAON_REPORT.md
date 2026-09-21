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
