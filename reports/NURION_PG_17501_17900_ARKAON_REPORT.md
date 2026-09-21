# NURION_PG #17501–#17900 ARKAON 선행 구현 보고

## 결론

disposable PostgreSQL에서 `pg_terminate_backend`를 이용한 실제 backend 종료와 commit outcome reconciliation의 경계를 구현했다. 로컬 단위계약은 통과했으며, 실제 PostgreSQL 판정은 CI service 실행 전까지 `SKIP_NO_PRECONFIGURED_TEST_DATABASE`이다.

## 증명 범위

- pre-commit worker 종료: allowlist SQLSTATE, fresh read-only row absence, blind retry 0, `HOLD_NOT_COMMITTED`
- acknowledged commit 후 worker 종료: fresh read-only exact idempotency key·payload digest 조회
- termination 권한 거부, false 반환, 미등록 SQLSTATE, missing/duplicate/changed payload는 fail-closed
- 실제 network partition·failover·COMMIT response loss는 미주장
- 400 controls, 20단계 direct evidence, lesson/registry/manifest chain
- 운영 데이터베이스 쓰기·승인·발급·병합·배포 없음

## HOLD와 되는 방향

| 원인 | 권고 해결 | 대안 | 비용·위험·가역성 | 검증 | 중단·재개·rollback |
|---|---|---|---|---|---|
| pre-commit backend 종료 | 자동 재시도 없이 HOLD 후 새 read-only 연결에서 exact absence 확인 | idempotency key를 첨부해 운영자 검토 | 낮음·낮음·높음 | allowlist SQLSTATE와 0행 | 행 존재/미등록 상태면 중단, fixture 보수 후 전체 재실행, dead connection close와 exact schema drop |
| acknowledged commit 뒤 연결 종료 | 새 read-only 연결에서 key+payload exact match | exact match 불가 시 운영자 HOLD | 낮음·중간·높음 | 단일 행과 digest 일치 | missing/duplicate/changed면 중단, 모호성 해소 후 재개, 보상 write 없이 schema만 drop |
| termination 권한 또는 환경 차이 | 결과를 강제하지 않고 fail-closed | 승인된 disposable PG service role 사용 | 중간·낮음·높음 | 함수 true와 57P01/08006 | denied/false/unknown이면 중단, fixture 권한 복구 후 재실행, 모든 test connection close |

## 정직한 한계

commit은 응답이 확인된 뒤 backend를 종료한다. 따라서 post-commit 결과는 실제 backend termination과 read-back reconciliation 증거이지, COMMIT 응답 자체가 네트워크에서 유실됐다는 증거가 아니다. 기존 response-loss 항목은 `HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS` provenance를 유지한다.
