# NURION_PG #14301~#14700 에테르니언 검수 요청

이 문서는 아르카온 선행 구현의 검수 요청이며 승인·수락·병합·배포 판정이 아니다.

확인 요청 항목:

- 정확히 400 controls와 12단계 snapshot chain
- 복합 identity가 plan_id, flow, kind, source contract, readiness manifest를 모두 결속하는지
- materialization/execution PENDING 봉투의 actor, sequence, predecessor, nonce/replay scope가 독립적인지
- full downstream rehash 공격과 source/latest/order/concurrency/partial-batch 우회를 차단하는지
- final-docket 공통 불변식이 receipt 발급·승인·materialization·execution·PASS/FAIL을 거부하는지
- 두 복구경로가 원인·비용·위험·가역성·검증·중단·재개·rollback을 제공하는지
- 외부·PG·금융·원장·credential·deploy가 모두 0인지
