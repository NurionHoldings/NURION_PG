# NURION_PG #17901–#18300 ARKAON 선행 구현 보고

## 결론

pre-commit connection loss의 `HOLD_NOT_COMMITTED`를 자동 재실행하지 않고, disposable PostgreSQL의 별도 append-only recovery quarantine case로 안전하게 전환하는 증명 계층을 구현했다. 로컬 계약과 21단계 증거는 통과했으며 실제 PostgreSQL 판정은 CI service 실행 전까지 `SKIP_NO_PRECONFIGURED_TEST_DATABASE`이다.

## 증명 범위

- source event·idempotency key·payload digest·SQLSTATE·provenance·observed time·sequence·state의 exact 결속
- domain-separated deterministic case identity와 exact uniqueness
- 동일 envelope replay는 단일 행 수렴, changed payload·cross-key alias는 rollback/fail-closed
- UPDATE·DELETE trigger 차단으로 append-only 유지
- `QUARANTINED_NON_EXECUTABLE_ONLY`: payment·receipt·retry·approval 권한 없음
- fresh read-only operator packet/reconciliation view
- `GROUP BY` 기반 PostgreSQL inherently non-updatable operator view와 write-capable 연결의 INSERT·UPDATE·DELETE 실제 거부 계약
- 문자열 비교가 아닌 SQL `timestamptz` exact equality의 observed time 결속
- precommit source row 및 retry 0
- exact disposable schema cleanup과 content-addressed artifact
- 실제 network partition·failover·운영처리는 미주장
- 400 controls, 21단계 direct evidence, lesson/registry/manifest chain

## HOLD와 되는 방향

| 원인 | 권고 해결 | 대안 | 비용·위험·가역성 | 검증 | 중단·재개·rollback |
|---|---|---|---|---|---|
| precommit loss로 원천 commit 부재 | 원천 재실행 없이 exact 관찰 envelope를 비실행 quarantine에 append | case 생성 없이 수동 HOLD 유지 | 낮음·낮음·높음 | fresh source absence와 exact case read | source row 존재/unknown SQLSTATE면 중단, 모호성 해소 후 새 sequence로 재개, source 무변경·fixture schema만 drop |
| 동일 case 재제출 | case ID와 모든 결속 필드가 같을 때 기존 1행으로 수렴 | insert 없이 기존 case 조회 | 낮음·낮음·높음 | row count 1과 exact tuple | 필드 하나라도 다르면 중단, 원 envelope로 재개, 기존 행 무변경 |
| changed payload/cross-key 충돌 | transaction rollback 후 original case 보존 | 독립 증거와 인간검토 후 새 source event | 중간·중간·높음 | unique constraint와 exact read-back | conflict 즉시 중단, identity 충돌 해소 후 재개, rollback으로 mutation 0 |
| 실제 PostgreSQL 미구성 | PASS로 강제하지 않고 SKIP 유지 | 승인된 disposable PostgreSQL CI service 사용 | 낮음·낮음·높음 | CI의 `PASS_POSTGRES_RECOVERY_QUARANTINE_PROOF`와 artifact | 연결/cleanup 실패 시 HOLD, fixture 보수 후 전체 재실행, exact schema만 drop |
| 단순 view의 auto-updatable 가능성 | 집계형 view로 구조적 수정불가를 만들고 write-capable 연결에서 세 DML을 실제 거부 | privilege revoke | 낮음·낮음·높음 | INSERT·UPDATE·DELETE exact rejection | 하나라도 성공하면 PASS 중단, view 수정 후 전체 재실행, fixture schema만 drop |
| observed time 문자열 prefix 비교 | PostgreSQL에서 expected instant와 `timestamptz` exact equality | Python aware datetime equality | 낮음·낮음·높음 | SQL boolean exact true | false/null이면 중단, temporal binding 수정 후 재실행, fixture schema만 drop |

## 정직한 한계

이 공정은 실제 disposable PostgreSQL에서 quarantine persistence와 replay/conflict/read-only 조회를 검증한다. network partition, failover, 운영 DB write, 실제 결제·receipt·retry·approval 실행을 증명하거나 허가하지 않는다.

## 로컬 검증 결과

- focused: 7 PASS
- full regression: 1,978 PASS
- 21단계 direct evidence chain: PASS
- lesson registry: 37 PASS
- 계약 evidence SHA-256: `c5f9a973016fb1f6d63e7ce96969c86f04aa6520dfa1676d82607266cb0056cd`
- 로컬 PostgreSQL integration: `SKIP_NO_PRECONFIGURED_TEST_DATABASE`
- compileall, governance, diff-check, credential 정적검사: PASS
- ETHERNIAN HOLD 재검증: 집계형 view 및 DML 3종 exact rejection 계약, SQL temporal equality와 psycopg temporal type-boundary 회귀시험 반영 후 full 1,978·21단계 evidence PASS

### 원격 run `35573236643` HOLD — psycopg temporal type boundary

- 원인: 최초 insert 뒤 replay read-back의 `observed_at`은 psycopg aware `datetime`인데 expected tuple은 ISO 문자열이어서, 동일 instant임에도 Python 객체 타입 차이로 exact tuple 비교가 실패했다.
- 권고·반영: DB SELECT에서 `observed_at = %s::timestamptz`를 계산하고 exact `true`를 나머지 필드 tuple과 함께 비교한다. 최초 insert와 replay 모두 동일한 PostgreSQL temporal equality를 사용한다.
- 대안: Python에서 ISO 문자열을 aware datetime으로 정규화해 비교할 수 있으나 PostgreSQL parsing/timezone semantics와 이중 구현이 생겨 채택하지 않았다. text cast·prefix 비교는 정확성이 약해 금지한다.
- 비용·위험·가역성: read-back SELECT 한 필드의 표현만 바꾸므로 비용과 위험이 낮고, 단일 patch revert로 가역적이다. unique conflict, changed/cross-key rollback, append-only trigger에는 영향이 없다.
- 검증·중단·재개·rollback: SQL equality가 false/null이거나 tuple의 다른 필드가 다르면 PASS를 중단한다. focused/full과 새 disposable CI 전체 실행이 성공할 때만 재개하며, 실패 시 exact fixture schema만 drop한다.

실제 PostgreSQL PASS, cleanup, artifact upload는 원격 disposable CI가 성공하기 전까지 HOLD한다. commit·push·PR·merge·deploy는 수행하지 않았다.
