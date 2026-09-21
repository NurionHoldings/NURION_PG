# NURION_PG #17101~#17500 ARKAON 선행 구현 결과

## 결론

실제 PostgreSQL deadlock·lock contention proof 계약을 구현했다. 정확히 400개 통제와 19번째 직접 증거계보를 추가했다. 일반 로컬 환경은 `SKIP_NO_PRECONFIGURED_TEST_DATABASE`, 전용 disposable PostgreSQL만 실제 `40P01`과 `55P03`을 만들고 exact evidence가 일치할 때 `PASS_POSTGRES_DEADLOCK_PROOF`를 생성한다.

## 구현·주장 경계

- 두 backend가 두 행을 반대 순서로 잠가 실제 `40P01` 피해자 정확히 1개와 commit 승자 1개를 요구한다.
- 피해 transaction rollback 및 backend close 뒤 다른 backend PID에서 attempt 2 성공을 요구한다.
- 별도 holder/contender가 실제 blocked row를 만들고 `lock_timeout`의 `55P03` 정확히 1회를 비재시도로 분류한다.
- `deadlock_timeout` session 설정이 거부되면 환경 차이를 숨기지 않고 proof 전체를 실패시킨다.
- 실제 DB, 단위 주입, 하네스 주입 provenance를 exact 문자열로 분리한다.
- 실제 network partition·failover는 주장하지 않는다.
- 운영 DB 쓰기·receipt·signature·key·credential·금융·승인·배포는 0이다.

## HOLD와 되는 방향의 복구 지침

### HOLD 1 — 실제 deadlock 또는 fresh-backend 회복 불충족

- 원인: 두 transaction의 lock 획득 순서가 겹치지 않았거나, 실패 transaction/connection이 재사용되었거나, 충돌이 제한 횟수 내 해소되지 않았다.
- 권고안: barrier로 첫 행 잠금을 확인한 뒤 반대 행을 요청하고, 실제 `40P01` 피해자는 rollback·close한다. 동일 논리 작업은 fresh backend에서 최대 3회 범위로 재개한다.
- 대안: 애플리케이션의 모든 다중 행 쓰기에 canonical lock order를 적용해 deadlock 자체를 예방한다.
- 비용·위험·가역성: 권고안 비용·위험 낮음, 가역성 높음. 대안은 변경 범위와 회귀비용 중간이나 lock-order 변경을 되돌릴 수 있다.
- 검증: `40P01=1`, winner=1, 실패 PID와 재시도 PID 불일치, attempt 2 commit을 대조한다.
- 중단·재개·rollback: SQLSTATE 변경·피해자 수 불일치·3회 실패 시 중단한다. fixture scheduling/lock scope를 교정하고 전체 proof를 재개하며 실패 transaction과 exact disposable schema만 rollback한다.

### HOLD 2 — timeout 설정 권한 또는 실제 `55P03` 미발생

- 원인: test role이 session timeout을 설정할 수 없거나, holder lock이 contender 실행 전 해제되었거나, 운영 대상 방어가 fixture를 거부했다.
- 권고안: test-only disposable PostgreSQL role과 schema guard를 유지하고 holder가 row lock을 보유한 상태에서 contender에 짧은 `lock_timeout`을 적용한다. `55P03`은 blind retry하지 않는다.
- 대안: 권한을 넓히지 않고 관리되는 CI PostgreSQL service에서 동일 proof를 실행한다.
- 비용·위험·가역성: 권고안 비용 낮음·위험 낮음·가역성 높음, 대안 비용 중간·격리 위험 낮음·runner 제거로 가역 가능하다.
- 검증: timeout setting 성공, actual `55P03` 1회, contender attempt 1회, `NON_RETRYABLE_FAIL_CLOSED`, 두 connection close를 확인한다.
- 중단·재개·rollback: 설정 거부·timeout 미발생·target guard 실패 시 PASS를 중단한다. fixture 권한/격리를 교정한 후 새 schema에서 재개하고 두 transaction rollback 후 해당 schema만 삭제한다.

### HOLD 3 — actual/unit/harness provenance 혼합

- 원인: 이전 단계에는 actual `40001`, unit exhaustion, harness response loss가 함께 있어 필드가 약하면 실제 DB 실증 범위를 과장할 수 있다.
- 권고안: `40P01`·`55P03`만 actual PostgreSQL로, 3회 exhaustion은 `UNIT_INJECTED_SQLSTATE_SEQUENCE`, commit unknown은 `HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS`로 exact 결속한다.
- 대안: 증거 파일을 provenance별 artifact로 완전히 분리한다. 명확성은 높지만 CI·보관 복잡도가 증가한다.
- 비용·위험·가역성: exact 필드 방식은 비용·위험 낮음, 가역성 높음. 분리 artifact는 비용 중간, 위험 낮음, 가역 가능하다.
- 검증: provenance·actual claim·횟수·cleanup 필드를 각각 변조한 음성시험이 PASS 수락을 차단해야 한다.
- 중단·재개·rollback: 출처가 모호하거나 network/failover claim이 true이면 중단한다. 출처를 교정하고 전체 evidence를 다시 생성하며 잘못된 artifact는 운영 근거로 사용하지 않는다.

## 아르카온 판정

- focused/registry: 22 PASS
- full regression: 1,963 PASS
- #9901~#17500 직접 evidence chain 19단계: PASS
- compileall·diff-check: PASS
- 계약 evidence SHA-256: `9cba697ef47c8bec80ecb5e8e894bfde04d29df3e3283ea9602826a2ff256af6`
- 로컬 PostgreSQL integration: `SKIP_NO_PRECONFIGURED_TEST_DATABASE`
- lesson registry: 35 lessons PASS
- governance manifests·prior-stage digest·historical snapshot: PASS

commit·push·PR·merge·deploy는 수행하지 않았다. 실제 PostgreSQL 실증은 원격 전용 service CI artifact 전까지 HOLD이며 에테르니언 독립검수를 요청한다.
