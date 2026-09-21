# NURION_PG #16301~#16700 ETHERNian 독립검수 요청

다음 항목의 독립 재검증을 요청한다.

1. 운영 host/database 및 `public` schema 우회가 fail-closed인지
2. canonical AST/DDL과 migration/live introspection의 exact parity가 유지되는지
3. 6개 UNIQUE와 nullable/check/order가 약화되지 않는지
4. 20-way barrier 결과가 one row와 1 inserted/19 read-back으로 수렴하는지
5. unique violation 후 aborted transaction을 재사용하지 않는지
6. changed payload와 cross-key ID/token/scope/nonce/logical reuse가 충돌로 분류되는지
7. commit response-loss가 authoritative read-back으로 수렴하는지
8. cleanup이 검증된 disposable schema 하나로 제한되는지
9. DB 부재 SKIP, CI proof PASS, 연결·실증 실패 FAIL이 서로 바뀌지 않는지
10. test-only write와 production write 0이 분리되고 DSN·credential이 evidence에 없는지
11. 17단계 direct chain과 #7501 historical snapshot이 미래 registry 추가에도 불변인지
12. 실제 receipt·signature·key·금융·승인·배포가 0인지

발견되는 HOLD에는 원인, 권장 수정안, 대안, 비용·위험·가역성, 검증, 중단·재개·rollback 기준을 함께 제시해 달라.
