# NURION_PG #16301~#16700 에테르니언 독립검수

## 결론

**구조·로컬검증 수락 — PR 생성 가능. 실제 PostgreSQL 최종 수락은 원격 ephemeral CI proof 확인 후 확정한다. 병합·배포 불가.**

아르카온의 `격리형 PostgreSQL fixture·migration·repository proof 계약`을 독립 검수했다. 로컬에는 사전 구성 PostgreSQL이 없어 integration 1건은 정직하게 SKIP됐으며, 원격 CI의 PostgreSQL 16.4 disposable service에서만 실제 migration·introspection·repository concurrency proof를 실행한다.

## 확인 결과

- #16301~#16700의 정확히 400 controls와 17번째 직접 evidence stage를 구성한다.
- 대상 guard는 `nurion_pg_ci` 데이터베이스와 `nurion_pg_ci_` 접두사 schema만 허용하고 운영 host/database와 `public` schema를 거부한다.
- canonical migration up/down은 검증된 disposable schema 하나만 생성·제거하며 `DROP DATABASE`를 포함하지 않는다.
- 28개 column의 순서·타입·nullability, PK·6개 UNIQUE·CHECK, non-deferrable 즉시 제약을 live catalog에서 검증한다.
- repository는 unique violation 후 실패 transaction 전체를 rollback하고 새 transaction에서 winner를 locked read-back하여 payload를 비교한다.
- 20-way Barrier 동시성, changed payload, token/scope/nonce/logical reuse, aborted transaction, commit 후 응답 유실 read-back을 시험한다.
- 운영 DB write·receipt·signature·key·금융·승인·배포는 모두 0이다.

## HOLD와 되는 방향 지침

### Live constraint exactness

- 원인: 최초 runner는 constraint 이름과 UNIQUE 개수만 확인해 동일 이름의 잘못된 컬럼 대상·순서를 놓칠 수 있었다.
- 권장안: `conkey`를 ordinality와 `pg_attribute`로 해석해 이름·종류·ordered columns·deferrable/deferred를 exact 비교하고 CHECK를 단일 state ceiling으로 엄격히 정규화한다.
- 대안: `pg_get_constraintdef` 문자열 전체 비교는 간단하지만 PostgreSQL 버전별 formatting drift 위험이 있어 보조 수단으로만 적합하다.
- wrong target, logical order 역전, unique 누락, nullable drift, 완화된 CHECK를 모두 거부한다.

### PASS 증거의 의미 검증

- 원인: 최초 계약은 status만 맞는 불완전 PASS 딕셔너리도 실제 proof로 승격할 수 있었다.
- 권장안: 쓰기 수·attempt 수·운영 write 0·cleanup·worker/row 수·isolation·8개 conflict classification·비밀 비노출·live parity를 exact 검증한다.
- proof 인수가 없는 로컬 경로만 SKIP을 생성할 수 있고, 외부 주입 SKIP이나 불완전·변조 PASS는 fail-closed한다.
- 두 수정은 disposable test harness에 한정되어 운영 데이터 영향이 없고, exact schema cleanup으로 가역적이다.

## 독립 로컬 재검증

- 전용·인접·registry: 44 PASS
- 전체 회귀: 1,947 PASS
- #9901~#16700 직접 계보 17단계 evidence: PASS
- #7501 historical evidence: PASS
- lesson registry: 33 lessons PASS
- 로컬 PostgreSQL integration: 1 SKIP (`SKIP_NO_PRECONFIGURED_TEST_DATABASE`)
- governance/compileall/diff-check: PASS
- 계약 Evidence SHA-256: `898c89e4c0a1174957c4079ede62f9a6cdd195e1a38c687c0132a927b50b387a`

## 원격 PostgreSQL proof

- 상태: `PENDING_PR_CI`
- 수락조건: PostgreSQL 16.4 service 연결, exact live schema parity, 20-way one-row convergence, 충돌·rollback·read-back, cleanup 및 semantic proof validation이 모두 GREEN이어야 한다.
- 실패하거나 artifact가 없으면 실제 PostgreSQL 수락은 HOLD다.

## 잔여 위험

- ephemeral 단일 CI 인스턴스 증거는 운영 PostgreSQL의 부하·장애조치·복제·장기보존을 증명하지 않는다.
- 실제 receipt 발급·금융처리·운영 migration은 별도 단계와 인간 승인 전까지 금지한다.
