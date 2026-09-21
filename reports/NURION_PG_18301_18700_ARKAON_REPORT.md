# NURION_PG #18301–#18700 ARKAON 선행 구현 보고

## 결론

기존 `QUARANTINED_NON_EXECUTABLE_ONLY` 사건을 자동 실행하지 않고, exact case digest와 독립 reviewer에 결속된 append-only `HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE` 처분으로 기록하는 다음 안전 계층을 구현했다. 단일 PostgreSQL CI에서는 실제 network partition·failover를 주장하지 않으며, 향후 격리된 primary/standby fixture가 충족해야 할 preflight 계약만 추가했다.

## 증명 범위

- 400 controls 및 22단계 연속 증거
- quarantine case ID·case digest·disposition key·reviewer·reviewed time·sequence·outcome의 exact 결속
- domain-separated deterministic disposition identity
- 동일 envelope replay 1행 수렴, changed payload·cross-key alias fail-closed
- `(case_id, case_digest)` composite FK로 새 key·새 sequence·wrong digest 공격 fail-closed
- disposition UPDATE/DELETE 거부 및 quarantine 원본 불변
- 집계형 operator view와 INSERT·UPDATE·DELETE 실제 거부
- payment·receipt·retry·approval·execution authority 전부 false
- multi-node preflight contract만 complete; partition·failover·fault injection은 모두 false
- disposable schema exact cleanup, content-addressed artifact, production writes 0

## HOLD와 되는 방향

| 원인 | 권고 해결 | 대안 | 비용·위험·가역성 | 검증 | 중단·재개·rollback |
|---|---|---|---|---|---|
| 인간 처분이 필요하지만 quarantine 원본은 비실행 상태 | exact case digest에 결속된 HOLD 처분만 append | 처분 없이 quarantine 유지 | 낮음·낮음·높음 | fresh read-only exact join | case 누락/digest 불일치 시 중단, 올바른 case로 독립 재검토, transaction rollback |
| 동일 처분 재전송 또는 충돌 | 동일 envelope만 1행 수렴, 변경·교차 key는 fail-closed | 해결된 새 증거로 다음 sequence 검토 | 중간·중간·높음 | unique identity와 exact read-back | 결속 필드 차이 시 중단, 원 envelope 또는 새 독립검토로 재개, 기존 행 무변경 |
| 단일 PostgreSQL service라 실제 failover 불가 | 격리 primary/standby·통제된 fault·role 판별·복구 reconciliation·cleanup을 future preflight로 요구 | 현재 모든 실제 claim false 유지 | 높음·중간·높음 | future fixture의 역할/partition/복구/cleanup 증거 | 단일노드/비통제 target 즉시 중단, 승인된 disposable multi-node에서 재개, exact fixture만 폐기 |
| 신규 단위시험이 outcome을 실제 변조하지 않음 | 비허용 outcome `other`로 변경해 fail-closed 경로를 실제 실행 | 별도 parameterized mutation | 낮음·낮음·높음 | 집중 23 PASS 및 전체 회귀 | 예외 미발생 시 중단, mutation 수정 후 전체 재실행, 시험 patch revert |
| disposition이 case ID만 FK로 참조해 새 key·새 sequence·wrong digest 삽입 가능 | quarantine의 `(case_id, case_digest)` UNIQUE와 disposition composite FK를 DB에서 강제 | insert 전 application lookup은 race와 우회 위험으로 비채택 | 낮음·중간·높음 | 독립 key·sequence의 wrong digest 실제 INSERT 거부와 row count 1 | 삽입 성공 시 HOLD, composite 제약 복구 후 fresh DB 전체 재실행, fixture schema drop |
| 원격 CI에서 동일 case의 cross-key 처분이 성공 | 현재 단계는 `UNIQUE(case_id)`로 case당 처분 1개를 강제하고 재검토는 별도 supersession/versioning 공정으로 분리 | 현 단계에서 복수 처분 허용은 계보가 없어 비채택 | 낮음·중간·높음 | cross-key·새 sequence 실제 INSERT 거부, 처분 row count 1 | 성공 시 HOLD, unique 제약 복구 후 fresh DB 재실행, fixture schema drop |
| 통합 invariant 실패가 단일 일반 오류로만 노출 | 비밀값 없이 실패한 boolean invariant 이름만 정렬 출력 | 각 단계 개별 assert | 낮음·낮음·높음 | 실패 메시지의 `failed=<keys>` | 값·DSN·credential 출력 금지, 원인 수정 후 전체 재실행 |

## 로컬 검증

- focused: 25 PASS
- full regression: 1,987 PASS
- 22단계 direct evidence SHA-256: `94302d567def1c8b5bd4ac39f9bb74e4d833efe2afbf84e147e9b7e5b9677827`
- local actual PostgreSQL: `SKIP_NO_PRECONFIGURED_TEST_DATABASE`
- compileall, diff-check: PASS

실제 PostgreSQL PASS·artifact·cleanup 확인은 원격 disposable CI 전까지 HOLD한다. commit·push·PR·merge·deploy는 수행하지 않았다.
