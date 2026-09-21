# #17501–#17900 ETHERNIAN 독립검수 요청

- 실제 `pg_terminate_backend` 권한·true 반환·관측 SQLSTATE가 exact allowlist인지
- pre-commit 종료 후 fresh read-only 조회가 absence를 확인하며 blind retry가 0인지
- acknowledged commit 뒤 exact idempotency key와 payload digest가 단일 행으로 reconciliation되는지
- 실제 network partition·failover·COMMIT response loss를 과장하지 않는지
- 권한, SQLSTATE, missing/duplicate/changed row가 모두 fail-closed인지
- cleanup, artifact digest, 400 controls, 20단계 chain, lesson registry가 완전한지
- 운영 DB write·receipt·signature·key·financial·approval·activation·deployment가 0인지
