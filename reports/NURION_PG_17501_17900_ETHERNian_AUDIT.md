# NURION_PG #17501~#17900 에테르니언 독립검수

## 결론

**구조·로컬·원격 PostgreSQL backend termination 및 reconciliation 증명을 수락한다. PR #411은 OPEN 상태로 유지하며 병합·배포는 별도 인간 승인 전까지 금지한다.**

## 수락 범위

- 정확히 400 controls와 #9901~#17900 직접 evidence 20단계를 확인했다.
- disposable PostgreSQL worker를 별도 admin 연결의 `pg_terminate_backend`로 실제 종료했다.
- pre-commit과 acknowledged-commit 이후 종료에서 실제 SQLSTATE `57P01`을 관측했다.
- pre-commit 종료는 fresh read-only 연결에서 행 부재를 확인하고 blind retry 0회와 `HOLD_NOT_COMMITTED`를 유지한다.
- acknowledged commit 이후 종료는 fresh read-only 연결의 exact idempotency key·payload digest 단일 행으로만 `COMMITTED_CONFIRMED_BY_FRESH_EXACT_READ`를 판정한다.
- post-commit 경로는 commit 응답을 이미 확인한 뒤 종료한 것이며 lost COMMIT response라고 주장하지 않는다.
- 실제 network partition과 failover는 증명했다고 주장하지 않는다.
- 운영 DB write·receipt·signature·key·금융·승인·활성화·배포는 모두 0이다.

## HOLD와 극복 지침

### Pre-commit 연결 종료

- 원인: backend 종료 시 transaction이 commit됐는지 확인하기 전에 자동 재시도하면 중복 또는 의미 변경 위험이 생긴다.
- 권고안·반영: 허용 SQLSTATE와 exact row absence를 fresh read-only 연결에서 확인하되 blind retry는 0회로 유지하고 운영자 판단 HOLD로 남긴다.
- 대안: absence만 보고 즉시 재시도하는 방식은 읽기 지연·잘못된 대상 조회 가능성을 배제하지 못해 채택하지 않았다.
- 비용·위험·가역성: 추가 read 비용은 낮고 위험은 낮으며 정책 제거로 가역적이다.
- 검증·중단·재개·rollback: 행 존재, 미등록 SQLSTATE, 종료 권한 거부 시 PASS를 중단한다. fixture 권한·드라이버 관측을 보수한 새 disposable schema에서 재개하고 죽은 연결과 해당 schema만 정리한다.

### Acknowledged commit 이후 reconciliation

- 원인: commit 확인 이후 backend 종료와 commit 응답 유실을 혼동하면 증거 범위를 과장한다.
- 권고안·반영: `ACTUAL_BACKEND_TERMINATION_AFTER_ACKNOWLEDGED_COMMIT_NOT_COMMIT_RESPONSE_LOSS` provenance를 exact 결속하고 fresh read-only exact key/payload 조회만 수락한다.
- 대안: 이를 commit-unknown 실증으로 재사용하는 방식은 실제 장애 시점과 다르므로 채택하지 않았다.
- 비용·위험·가역성: 읽기 한 번의 비용으로 오판 위험을 낮추며 필드 제거로 가역적이다.
- 검증·중단·재개·rollback: missing·duplicate·changed payload 또는 provenance 변조 시 중단하고 운영자 조정 후 전체 proof로 재개한다. 보상 write는 수행하지 않고 test schema만 제거한다.

### Registry 고정 기준 동기화

- 원인: 신규 lesson과 stage 추가 후 고정 기대값이 각각 35→36, 13→14로 갱신되지 않았다.
- 권고안·반영: 선언과 독립 cardinality anchor를 같은 변경 단위로 갱신했다.
- 대안: 기대수를 자동 파생하면 독립 anchor가 약해져 채택하지 않았다.
- 비용·위험·가역성: 비용·위험이 낮고 stage 선언 제거로 가역적이다.
- 검증·중단·재개·rollback: 불연속·중복·lesson regression 시 중단하고 선언·시험 동기화 후 full regression으로 재개한다.

## 검증 결과

- focused/registry: 23 PASS
- 전체 회귀: 1,970 PASS
- 직접 evidence chain: 20단계 PASS
- lesson registry: 36 PASS
- compile·governance·diff-check·credential 정적검색: PASS
- 계약 Evidence SHA-256: `8dd07291f0d4002c9dfffe93d314206b4111a17b4725b5fff9f84c8aa1bff0e3`

## 원격 PostgreSQL 증거

- CI run: #1824, workflow run `35569137585`, head `b0e3908343b123f2150cd6588a01be9bffddd1fc`
- 상태: `PASS_POSTGRES_CONNECTION_LOSS_PROOF`
- 실증 Evidence SHA-256: `3a7004ecef3a2a0d106f1ea69e01d538577db752645f7c22ddaa3b9dafd5b1f9`
- artifact: `postgres-ephemeral-repository-proof`, ID `10625386700`, 3,518 bytes
- artifact ZIP SHA-256: `76eb5005a68bbc295a263acdcc6d9285883da16abf70b8d0f54544f730b9c50a`
- 실제 종료 권한, `57P01`, pre-commit absence, acknowledged-commit exact read-back, cleanup, artifact upload, ARKAON bootstrap이 모두 SUCCESS다.

## 잔여 위험

- `pg_terminate_backend`는 실제 backend 종료 증거지만 실제 network partition, failover, 복제 지연을 대신하지 않는다.
- 실제 lost COMMIT response의 네트워크 수준 재현은 후속 격리 환경이 필요하다.
- 운영 재시도 정책 적용, migration, receipt 발급, 금융 처리, 병합과 배포는 별도 승인 전까지 금지한다.
