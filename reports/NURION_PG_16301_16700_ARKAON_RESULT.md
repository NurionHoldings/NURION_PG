# NURION_PG #16301~#16700 ARKAON 선행 구현 결과

## 결론

격리형 PostgreSQL fixture·migration·repository proof 계약을 구현했다. 400개 통제와 17번째 직접 증거계보를 추가했으며, 일반 로컬 환경은 `SKIP_NO_PRECONFIGURED_TEST_DATABASE`, 전용 CI PostgreSQL service는 `PASS_EPHEMERAL_POSTGRESQL` 또는 명시적 FAIL만 허용한다.

## 구현 범위

- `nurion_pg_ci` 데이터베이스와 `nurion_pg_ci_` 접두사 schema만 허용하는 운영 대상 거부 guard
- canonical DDL 기반 migration up과 정확한 disposable schema만 제거하는 down
- 28개 column 순서·타입·nullability, PK, 6개 UNIQUE, state CHECK의 live introspection
- unique violation 발생 시 전체 rollback 후 새 transaction의 locked read-back 및 exact payload 비교
- sleep 없이 barrier를 사용한 동일 key·payload 20-way 동시성 수렴
- changed payload와 cross-key token reuse 충돌
- aborted transaction 재사용 금지 및 rollback/new transaction 검증
- commit 후 response-loss read-back 수렴과 cleanup 검증

## 권한 및 데이터 경계

- 실제 receipt·signature·key·credential·PG·금융·승인·배포: 0
- 운영 데이터베이스 쓰기: 0
- 통합실증의 DB 쓰기: CI 전용 disposable schema에만 한정
- DSN·credential: evidence 및 로그에 기록하지 않음

## 복구 지침

권장안은 전용 CI PostgreSQL을 복구하고 exact migration/introspection부터 재실행하는 것이다. 비용·위험은 낮고 schema 단위 cleanup으로 가역성이 높다. target guard 또는 schema parity 실패 시 즉시 중단하며 수정 후 새 disposable schema에서 재개한다.

대안은 repository·동시성 경로를 HOLD하고 rollback/new transaction/read-back 구현을 먼저 교정하는 것이다. 비용·위험은 중간, 가역성은 높다. commit 결과가 모호하거나 payload가 다르면 중단하고 전체 proof를 새 schema에서 재실행한다. committed append-only winner는 삭제하지 않는다.

## 아르카온 판정

## 에테르니언 HOLD 반영

### HOLD 1 — live constraint exact 검증

- 원인: constraint 이름 집합·UNIQUE 개수·CHECK 문자열 포함만 확인해 실제 ordered target drift를 잡지 못했다.
- 권장안·반영: `conkey`를 ordinality와 `pg_attribute`로 풀어 PK/UNIQUE ordered columns, kind, deferrable/deferred를 exact 비교하고 CHECK를 단일 `state = ceiling` 표현으로 정규화·검증했다.
- 대안: `pg_get_constraintdef` 전체 문자열 비교. 구현비용은 낮지만 PostgreSQL 버전별 formatting drift 위험이 있어 채택하지 않았다.
- 비용·위험·가역성: 권장안 비용 중간, 위험 낮음, 가역성 높음. 검증은 wrong target/reversed order/missing unique/nullable drift/relaxed CHECK 음성시험이다.
- 중단·재개·rollback: live parity 불일치 시 즉시 중단하고 migration을 교정한 뒤 새 disposable schema에서 재개한다. rollback은 검증된 해당 schema만 제거한다.

### HOLD 2 — 불완전 PASS 승격

- 원인: status 문자열만 맞으면 누락되거나 변조된 proof도 PASS로 주장할 수 있었다.
- 권장안·반영: writes=2, attempts=27, production=0, cleanup, workers=20, rows=1, READ COMMITTED, 8개 분류 exact/order, 비밀 비노출, live parity를 완전 일치시키는 semantic validator를 추가했다. SKIP은 proof 인수가 없는 로컬 경로에서만 생성된다.
- 대안: artifact checksum만 결속. 의미 검증이 없어 단독 사용하지 않았다.
- 비용·위험·가역성: 비용 낮음, 위험 낮음, 가역성 높음. 누락·추가·순서·수치·격리수준·운영쓰기·비밀노출 변조시험으로 검증한다.
- 중단·재개·rollback: 한 필드라도 불일치하면 PASS 주장을 중단한다. 새 disposable schema에서 전체 실증을 재수행한 완전 proof로만 재개하며 불완전 artifact는 승인 근거로 사용하지 않는다.

검증 결과:

- focused/adjacent/registry: 44 PASS
- full regression: 1,947 PASS
- 17단계 direct evidence chain: PASS
- #7501 historical snapshot: PASS
- 로컬 PostgreSQL integration: 1 SKIP (`SKIP_NO_PRECONFIGURED_TEST_DATABASE`)
- 계약 evidence SHA-256: `898c89e4c0a1174957c4079ede62f9a6cdd195e1a38c687c0132a927b50b387a`
- compileall, governance/lesson registry, diff-check: PASS

에테르니언 독립검수 요청. commit·push·PR·merge·deploy는 수행하지 않았다.
