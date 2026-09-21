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

### 원격 CI FAIL — constraint 행 순서와 비밀번호 노출

- 원인 1: PostgreSQL의 constraint OID 반환순서를 계약 순서로 잘못 가정했다. 제약 내부 컬럼 ordinality는 의미가 있지만 제약 행 사이의 OID 순서는 의미가 없다.
- 극복: exact name set과 duplicate/unknown 여부를 먼저 확인하고, name→record mapping을 canonical expected-name 순서로 재조립한다. 각 제약의 종류·내부 ordered columns·immediate 속성·CHECK ceiling exact 검증은 유지한다. 임의 순열은 통과하고 내부 역순은 거부하는 회귀시험을 추가했다.
- 원인 2: test-only password와 command DSN이 GitHub service/log metadata에 나타나 비노출 주장과 충돌했다.
- 극복: runner-local PostgreSQL service를 `POSTGRES_HOST_AUTH_METHOD=trust`로 제한하고 `POSTGRES_PASSWORD`, `PGPASSWORD`, URL DSN을 모두 제거했다. client는 exact PGHOST/PGPORT/PGDATABASE/PGUSER만 사용하며 별도 password credential은 구성하지 않는다.
- 대안: SQL `ORDER BY CASE`는 계약 중복·드리프트 위험, GitHub secret/masking은 service metadata 노출 가능성이 있어 채택하지 않았다.
- 비용·위험·가역성: 비용 낮음, 격리 CI runner 내부에만 trust를 허용하므로 운영 위험은 낮고 job 삭제로 완전 가역적이다.
- 검증·중단·재개·rollback: workflow 정적검사에서 password 변수·URL 0건을 강제한다. 원격 integration이 PASS, artifact upload, cleanup을 모두 증명하기 전까지 실환경 PostgreSQL proof는 HOLD한다. 실패 시 disposable schema만 cleanup하고 수정된 새 CI run으로 재개한다.

### 추가 HOLD — 우회 가능한 passwordless 주장

- 원인: DSN 경로에 password가 포함되거나 `PGPASSFILE`이 설정되어도 proof가 비밀번호 미구성으로 고정될 수 있었다.
- 권장안·반영: URL password가 존재하는 DSN을 거부하고 환경 경로에서 `PGPASSWORD`, `POSTGRES_PASSWORD`, `PGPASSFILE`을 모두 거부한다. PASS evidence 값은 exact 검증을 마친 integration proof의 필드에서 파생한다.
- 대안: password 사용 후 masking하는 방식은 service metadata와 외부 파일 경로를 별도로 신뢰해야 하므로 채택하지 않았다.
- 비용·위험·가역성: 비용 낮음, 위험 낮음, 가역성 높음. password DSN·PGPASSFILE 거부와 passwordless DSN 허용, workflow 정적 0건을 회귀검증한다.
- 중단·재개·rollback: password source가 하나라도 탐지되면 연결 전에 중단한다. runner-local trust와 exact target guard가 확인된 새 job에서만 재개하고 disposable schema만 rollback한다.

### 원격 run #1770 FAIL — response-loss fixture 논리키 충돌

- 원인: response-loss fixture가 winner와 동일한 `(flow, kind, intent_kind)`를 사용해 `uq_logical_intent`와 충돌했으며 두 번째 유효 write가 되지 못했다.
- 권장안·반영: fixture 생성기에 명시적 `kind` 입력을 추가하고 response-loss에 `case-response-loss`를 부여했다. idempotency read-back 의미와 writes=2, attempts=27 계약은 유지한다.
- 대안: 기존 logical unique 제약을 완화하거나 충돌을 무시하는 방식은 운영 의미를 훼손하므로 채택하지 않았다.
- 비용·위험·가역성: fixture 한 필드 수정으로 비용·위험이 낮고 완전 가역적이다.
- 검증·중단·재개·rollback: winner와 response-loss의 logical tuple 및 나머지 6개 unique identity가 모두 독립인지 단위검증한다. 새 원격 run에서 두 번째 commit·read-back·cleanup이 확인될 때 재개하며 실패 시 해당 disposable schema만 rollback한다.

검증 결과:

- focused/adjacent/registry: 46 PASS
- full regression: 1,949 PASS
- 17단계 direct evidence chain: PASS
- #7501 historical snapshot: PASS
- 로컬 PostgreSQL integration: 1 SKIP (`SKIP_NO_PRECONFIGURED_TEST_DATABASE`)
- 계약 evidence SHA-256: `f04278246d12a23f489e4c4e571eabf31c6b79e5f34ffbb47375073d43ffd004`
- compileall, governance/lesson registry, diff-check: PASS

에테르니언 독립검수 요청. commit·push·PR·merge·deploy는 수행하지 않았다.
