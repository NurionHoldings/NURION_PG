# NURION_PG #19101-#19500 ARKAON 선행 구현 보고

## 결론

append-only supersession의 현재 head를 독립 검토용 snapshot으로 봉인하고, 검토자와 결과 digest를 하나의 비실행 receipt에 결속하는 계약을 구현했다. 이 receipt는 지급·영수증 발급·재시도·승인·실행 권한이 아니다.

## 안전 계약

- snapshot은 exact `(case_id, supersession_id, supersession_digest, version)` 복합 FK에 결속
- INSERT trigger가 snapshot 생성 시점에 source가 current head인지 재검증
- snapshot ID와 receipt ID는 서로 다른 domain-separated 결정적 identity 사용
- snapshot당 receipt 1개만 허용
- 동일 envelope는 같은 1행으로 수렴하고 변경 payload·cross-case·stale head·receipt 변조는 거부
- source·snapshot·receipt UPDATE/DELETE 거부
- operator view INSERT·UPDATE·DELETE 거부
- payment·receipt issuance·retry·approval·execution authority 모두 false
- disposable PostgreSQL schema 이외 쓰기 금지, 정확한 schema만 cleanup

## ARKAON 극복 지침

| 원인 | 권고 방법 | 대안 | 비용·위험·가역성 | 검증 | 중지·재개·rollback |
|---|---|---|---|---|---|
| 검토 도중 head 변경 가능 | 검토 전에 exact current head snapshot 봉인 | 검토를 시작하지 않고 기존 HOLD 유지 | 낮음·낮음·높음 | composite FK와 current-head trigger | stale이면 중지, 새 head snapshot으로 재개, 실패 transaction rollback |
| receipt reviewer/result 충돌 | 원본 receipt 보존 후 새 독립 snapshot에서 재검토 | receipt 없이 HOLD 유지 | 낮음·중간·높음 | deterministic ID와 snapshot당 single receipt | mismatch 시 중지, 신규 review key로 재개, 기존 행 불변 |
| multi-node fixture 부재 | primary/standby 검토 일관성 preflight 유지 | single-node 주장만 유지 | 높음·중간·높음 | 향후 isolated failover fixture | 운영 target이면 중지, 승인 fixture에서 재개, exact fixture만 폐기 |

## 에테르니언 검수 요청

실제 PostgreSQL에서 stale head, changed snapshot, cross-case, receipt tamper, append-only 및 읽기 전용 view 우회가 모두 거부되는지 독립 검수한다. merge·deploy·production write는 별도 승인 전 수행하지 않는다.
