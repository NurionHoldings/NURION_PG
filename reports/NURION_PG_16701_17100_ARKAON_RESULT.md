# NURION_PG #16701~#17100 ARKAON 선행 구현 결과

## 결론

PostgreSQL bounded retry·commit-unknown recovery proof 계약을 구현했다. 정확히 400개 통제와 18번째 직접 증거계보를 추가했다. 일반 로컬 환경은 `SKIP_NO_PRECONFIGURED_TEST_DATABASE`, 전용 CI PostgreSQL은 실제 `SERIALIZABLE` write-skew의 SQLSTATE `40001`과 제한 재시도 성공을 증명해야만 `PASS_POSTGRES_RETRY_RESILIENCE`를 생성한다.

## 구현 범위와 정직한 주장 경계

- `40001` serialization failure와 `40P01` deadlock만 blind retry 허용
- 최대 3회, 실패 transaction rollback·connection close 후 fresh connection으로 재시도
- 세 번째 실패는 `RetryExhausted`로 fail-closed
- `57014` timeout과 `23505` unique violation은 재시도하지 않고 즉시 상위 조정으로 전달
- `08003`, `08006`, `57P01`은 commit 결과 불명으로 분류해 blind retry 금지
- 실제 PostgreSQL write-skew에서 정확히 한 번의 `40001`, attempt 2 성공, 두 참여자의 최종 성공, 실패/성공 backend PID 분리를 확인
- 실제 statement timeout `57014`을 정확히 한 번 발생시켜 비재시도 분류 확인
- 실제 commit 직후 테스트 하네스가 response loss를 주입하고 fresh connection exact idempotency read-back으로 수렴
- 실제 network partition과 deadlock을 수행했다고 주장하지 않음 (`claimed=false`)
- 3회 연속 retry exhaustion은 실제 DB 장애가 아니라 `UNIT_INJECTED_SQLSTATE_SEQUENCE` 단위시험이며 `actual_retry_exhaustion_claimed=false`
- 운영 DB 쓰기·receipt·signature·key·credential·금융·승인·배포 0

## HOLD와 되는 방향의 복구 지침

### HOLD 1 — serialization/deadlock 재시도 소진

- 원인: 충돌 범위가 지속되거나 transaction이 너무 넓어 3회 안에 직렬화되지 않는다.
- 권고안: 실패 transaction을 rollback하고 연결을 닫은 뒤, 동일 멱등 payload를 fresh connection에서 최대 3회까지만 재시도한다. transaction 범위와 잠금 순서를 줄여 새 disposable schema에서 전체 실증을 재개한다.
- 대안: PostgreSQL advisory lock으로 직렬화한다. 충돌은 줄지만 처리량·운영 복잡도가 증가하므로 별도 설계 승인이 필요하다.
- 비용·위험·가역성: 권고안 비용 낮음, 위험 낮음, 가역성 높음. 대안은 비용·운영 위험 중간, lock 제거로 가역 가능하다.
- 검증법: 실제 `40001`, 실패/성공 backend PID 차이, 최대 attempt=3, exhaustion 예외를 확인한다.
- 중단·재개·rollback: 3회 실패 또는 SQLSTATE 변경 즉시 중단한다. contention scope 수정 후 새 schema에서 재개하며 실패 transaction은 rollback, 검증된 disposable schema만 제거한다.

### HOLD 2 — commit 결과 불명·timeout·payload 불일치

- 원인: 연결 손실은 commit 전후를 구분할 수 없고, timeout/unique 오류를 무조건 재시도하면 중복 또는 의미 충돌이 발생할 수 있다.
- 권고안: blind retry하지 말고 fresh connection에서 exact idempotency key를 조회해 상태가 `EXISTING_SAME_PAYLOAD`이고 payload digest도 일치할 때만 기존 commit으로 수렴한다. `INSERTED`·기타 상태·부재·불일치는 모두 HOLD한다.
- 대안: 운영자 reconciliation queue에 격리해 DB·외부 시스템 증거를 함께 확인한다. 비용·지연은 증가하지만 불명 상태의 자동 승격을 막는다.
- 비용·위험·가역성: 권고안 비용 중간, 위험 중간, 가역성 높음. 조회만 수행하므로 기존 commit을 변경하지 않는다.
- 검증법: harness-injected post-commit response loss 후 exact read-back PASS, absent/mismatch/unknown status 음성시험, 실제 `57014` 비재시도를 확인한다.
- 중단·재개·rollback: absent/mismatch/timeout/unclassified failure면 중단한다. 운영자 조정 또는 원인 교정 후 전체 proof로 재개한다. possible committed winner는 삭제하지 않고 test schema만 cleanup한다.

### 에테르니언 HOLD — 실제·주입 증거 provenance 분리

- 원인: `retry_exhaustion_fail_closed=true`만으로는 실제 PostgreSQL이 3회 연속 abort했다고 오해할 수 있었고, read-back이 fresh 조회인데도 `INSERTED` 상태를 허용했다.
- 권고안·반영: exhaustion에 `retry_exhaustion_mode=UNIT_INJECTED_SQLSTATE_SEQUENCE`, `actual_retry_exhaustion_claimed=false`를 exact 결속했다. 실제 원격 증명은 `40001` 1회와 attempt 2 성공, `57014` 1회로 제한했다. fresh read-back은 `EXISTING_SAME_PAYLOAD`와 exact digest만 수락한다.
- 대안: 실제 DB에서 3연속 serialization abort를 강제할 수 있으나 scheduler 의존성과 재현성 저하 때문에 채택하지 않았다.
- 비용·위험·가역성: 필드·검증·음성시험 보강으로 비용과 위험이 낮고 완전 가역적이다.
- 검증법: provenance/mode/actual-claim/timeout 횟수 변조 및 `INSERTED`·OTHER·absence·digest mismatch 거부시험을 수행한다.
- 중단·재개·rollback: 실제·주입 provenance가 불명확하거나 expected exact field가 다르면 PASS를 중단한다. 필드를 교정하고 새 disposable schema의 전체 원격 proof로 재개하며 schema만 rollback한다.

| 증거 | provenance | PASS 주장 |
|---|---|---|
| `40001` 1회 → attempt 2 성공 | 실제 PostgreSQL | 예 |
| `57014` 1회, 재시도 0회 | 실제 PostgreSQL | 예 |
| 3회 retry exhaustion | unit-injected SQLSTATE sequence | 실제 DB 주장 아님 |
| commit 후 response loss | harness-injected after actual commit | 실제 network partition 주장 아님 |
| deadlock·network partition | 미실행 | 아니오 |

## 아르카온 판정

로컬 PostgreSQL 미구성 환경에서는 실증 PASS를 주장하지 않고 SKIP으로 유지한다.

- focused/adjacent: 20 PASS
- full regression: 1,957 PASS
- #9901~#17100 직접 evidence chain 18단계: PASS
- #7501 historical snapshot 보존: PASS
- lesson registry: 34 lessons PASS
- compileall·diff-check: PASS
- 계약 evidence SHA-256: `abe651b1b143a2c4d6719eb1185329bc3a87a167270e738ae579329e3a9795d6`
- 로컬 PostgreSQL integration: `SKIP_NO_PRECONFIGURED_TEST_DATABASE`

commit·push·PR·merge·deploy는 수행하지 않았다. 실제 PostgreSQL 실증은 원격 전용 service CI artifact 확인 전까지 HOLD이며, 에테르니언 독립검수를 요청한다.
