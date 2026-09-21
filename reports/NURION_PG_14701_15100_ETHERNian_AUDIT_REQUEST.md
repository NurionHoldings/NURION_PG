# NURION_PG #14701~#15100 에테르니언 검수 요청

- 정확히 400 controls와 40개 비발급 receipt schema/idempotency 계약인지
- source plan identity, intent digest, actor slots, kind, sequence, predecessor, nonce/key scope가 직접 결속됐는지
- 같은 key·payload 직렬/병렬 수렴과 변경 payload/cross-key identity 재사용 거부가 fail-closed인지
- forged receipt/authority, partial batch/order swap, full downstream rehash를 거부하는지
- #7501 과거 evidence와 공용 stage-bound snapshot이 미래 registry 추가에도 payload/checksum을 보존하는지
- receipt/materialization/execution/observation/PASS/FAIL/승인·활성화·배포가 0인지
- 두 복구경로에 원인·권장안·대안·비용·위험·가역성·검증·중단·재개·rollback이 포함됐는지
