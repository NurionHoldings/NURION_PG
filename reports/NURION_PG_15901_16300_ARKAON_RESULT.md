# NURION_PG #15901~#16300 ARKAON 결과보고

## 결론

`PostgreSQL 비발급 예약원장 스키마·트랜잭션 증명 계약`을 계획 전용 계층으로 구현했다. 40개 reservation에 append-only row 계획을 부여했지만 DB 연결·쓰기·commit·receipt 발급은 수행하지 않았다.

## 통제와 해결 지침

- 400 controls, 정규화 schema AST 1개, 결정적 quoted DDL 1개, row plan 40개
- reservation/key/token/logical tuple/scope/nonce의 정확한 unique target과 순서
- source reservation·packet·result·seal·policy v1·시간창·sequence/predecessor·정규화 actor 직접 결속
- 동일 key·동일 payload 단일 row 수렴, changed payload/cross-key reuse fail-closed
- 권장안: unique violation 뒤 실패 statement를 rollback하고 유효 transaction에서 winner를 잠금 read-back하여 canonical payload를 비교한다. 비용·위험은 낮고 가역성은 높다.
- 대안: commit 전 crash는 rollback 후 같은 key/payload로 재시도하고, commit 후 응답 유실은 같은 key로 read-back한다. commit 결과를 증명할 수 없으면 중단하고, 확인 뒤 재개한다. append-only committed row 삭제는 rollback 수단으로 쓰지 않는다.

## PostgreSQL 증거 경계

사전 구성된 안전한 테스트 PostgreSQL이 없으므로 실제 DB proof는 `SKIP_NO_PRECONFIGURED_TEST_DATABASE`이다. SQLite를 PostgreSQL 동시성 증거로 사용하지 않았다. in-memory contract concurrency와 structured schema/transaction semantics만 PASS로 주장한다.

## 비권한 경계와 잔여 위험

최대 상태는 `PERSISTENCE_PLAN_ONLY_NOT_WRITTEN`이다. 실제 PostgreSQL unique arbitration, process 간 lock, crash recovery, migration round-trip은 아직 검증되지 않았다. database URL·credential 조회, DB/ledger write, commit, receipt, PG·금융 호출, 승인·배포는 모두 0이다.

## 자체검증 결과

- focused/adjacent/registry: 51 PASS
- 전체 회귀: 1,937 PASS
- #9901~#16300 16단계 직접 evidence: PASS
- #7501 historical evidence: PASS
- governance registry: 32 lessons PASS
- compileall / `git diff --check`: PASS
- 실제 PostgreSQL proof: SKIP
- Evidence SHA-256: `2840aaa54024d13bcf2fab36170c1de4965e2592fbd55bf20cfac8333addfdd9`

## 에테르니언 감사 요청

schema AST의 exact target/order/nullability, transaction abort semantics, payload compare, crash 전후 convergence, full downstream rehash, 역할 alias, 정책 downgrade, 미래 snapshot 불변성을 독립 검수해 달라.

## 에테르니언 HOLD 보완

### TransactionPlan 사후 exact 검증

- 원인: 최초 `_integrity`는 transaction digest와 authority boundary만 확인해, 공격자가 rollback·lock·payload compare·conflict target을 완화하고 downstream digest를 다시 계산할 여지가 있었다.
- 권장안: `expected_transaction_payload()`를 단일 기준으로 두고 생성과 사후 `_transaction_valid()`가 모든 필드와 순서를 정확히 비교한다.
- 대안: 필수 문자열 포함검사는 구현비가 낮지만 부분문자열 우회와 순서 drift를 막지 못해 채택하지 않았다.
- 비용·위험·가역성: 코드비용 낮음, 호환위험 낮음, 완전 가역적이다.
- 검증: whole-transaction rollback 삭제/same transaction 재사용, lock·payload compare 삭제, conflict target 누락·역순, crash 의미 교환 뒤 tx와 docket을 완전 재해시해도 거부한다.
- 중단·재개·rollback: expected contract 불일치 시 계획 확정을 중단하고 원본 기준으로 transaction plan을 재생성한 뒤 재검증한다. 비실행 계획 객체만 폐기한다.

### Docket·snapshot 사후 parity

- 원인: finalize의 namespace·역할 유일성 및 anchor의 registry/manifest SHA 검증이 사후 `_integrity`에서 반복되지 않았다.
- 권장안: `_docket_valid()`에서 namespace, 전체 owner/validator와 최종 역할의 정규화 전역 유일성, 모든 digest 결속과 final invariant를 exact 검증하고 snapshot SHA도 사후 재검증한다.
- 대안: docket 생성 시 검사만 유지할 수 있으나 저장 후 변조와 완전 재해시 공격을 방어하지 못해 채택하지 않았다.
- 비용·위험·가역성: 비용 낮음, 기존 정상 산출물 위험 없음, 완전 가역적이다.
- 검증: docket/compiler/validator namespace 변조, 기존 actor alias, compiler-validator 동일 suffix, registry/manifest 비SHA를 downstream까지 재해시해도 거부한다.
- 중단·재개·rollback: 역할·snapshot 계보 불일치 시 중단하고 intact source에서 독립 역할과 원본 SHA로 docket을 다시 만든다. 손상된 plan docket만 폐기한다.
