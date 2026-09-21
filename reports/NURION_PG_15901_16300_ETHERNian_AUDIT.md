# NURION_PG #15901~#16300 에테르니언 독립검수

## 결론

**조건부 수락 — 구조화 PostgreSQL 계약과 PR 생성은 가능, 실제 PostgreSQL proof·병합·배포는 불가.**

아르카온의 `PostgreSQL 비발급 예약원장 스키마·트랜잭션 증명 계약`을 독립 검수했다. 실제 DB 접속 없이 정규화 schema AST, 결정적 quoted DDL, 40개 append-only row plan과 transaction/crash recovery 계약을 구성한다. 검수 중 transaction 및 final docket의 사후 exact 검증 공백을 발견해 `HOLD`했고, 공용 exact validator와 완전 재해시 음성시험을 적용한 뒤 재검증했다.

## 확인 결과

- #15901~#16300의 정확히 400 controls를 등록한다.
- schema AST·DDL·transaction plan 각 1개와 row plan 40개를 구성한다.
- reservation ID, idempotency key, token, `(flow, kind, intent_kind)`, reservation scope, nonce에 정확한 unique target/order를 정의한다.
- source reservation·packet·result candidate·seal input·policy v1·시간창·sequence·predecessor·정규화 actor를 row payload에 직접 결속한다.
- unique violation 뒤 실패 transaction 전체 rollback, 새 transaction 시작, winner locked read-back, canonical payload 비교를 강제한다.
- commit 전 crash는 rollback/retry, commit 후 응답 유실은 idempotency key read-back으로 분리한다.
- DB URL·credential·connection·write·commit·receipt·PG·금융·승인·배포는 모두 0이다.

## HOLD와 되는 방향 지침

### Transaction exact 검증

- 원인: 최초 `_integrity`는 transaction digest와 authority 문구만 검사해 rollback·lock·payload compare를 삭제한 뒤 재해시할 수 있었다.
- 권장안: `expected_transaction_payload()`와 `transaction_valid()`를 단일 기준으로 사용해 모든 필드와 순서를 정확히 비교한다.
- 비권장 대안: 필수 문자열 포함검사는 순서 변경과 부분 문자열 우회를 놓칠 수 있다.
- 검증: whole-transaction rollback 삭제, same transaction 재사용, lock/payload compare 삭제, conflict target 누락·역순, crash 의미 교환 후 tx와 docket을 완전 재해시해도 무결성은 false다.

### Final docket 사후 검증

- 원인: finalize에서 검사한 namespace와 역할 독립성을 사후 `_integrity`가 반복 검증하지 않았다.
- 권장안: `_docket_valid()`가 namespace, 전체 owner/validator와 final roles의 정규화 유일성, snapshot/schema/DDL/rows/transaction 및 final invariant를 exact 재검증한다.
- snapshot registry/manifest digest 형식도 anchor와 사후 검증의 parity를 맞췄다.
- 두 수정은 plan-only 객체에 한정되어 비용·위험이 낮고 가역적이다. 변조 발견 시 plan/docket만 폐기하고 source reservation은 보존한다.

## 독립 재검증

- 전용·인접·registry: 51 PASS
- 전체 회귀: 1,937 PASS
- #9901~#16300 직접 계보 16단계 evidence: PASS
- #7501 historical evidence: PASS
- lesson registry: 32 lessons PASS
- governance/compileall/diff-check: PASS
- Evidence SHA-256: `2840aaa54024d13bcf2fab36170c1de4965e2592fbd55bf20cfac8333addfdd9`

## PostgreSQL 실증 경계와 다음 방향

- 실제 PostgreSQL proof는 `SKIP_NO_PRECONFIGURED_TEST_DATABASE`이다. SQLite를 PostgreSQL 동시성 증거로 사용하지 않았다.
- 따라서 실제 unique arbitration, transaction isolation, process 간 lock, crash recovery, migration round-trip은 아직 증명되지 않았다.
- 다음 단계는 운영 자격증명이 아닌 격리된 임시 PostgreSQL test fixture와 migration/repository proof를 준비하는 것이다. 안전한 테스트 DB가 없으면 계속 SKIP해야 한다.
- 병합과 배포는 별도 인간 승인 전까지 금지한다.
