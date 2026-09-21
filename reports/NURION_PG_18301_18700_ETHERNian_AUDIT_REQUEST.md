# NURION_PG #18301–#18700 ETHERNIAN 독립 감사 요청

ARKAON은 구현과 로컬 검증을 완료했으며 다음 항목의 독립 판정을 요청한다.

1. disposition identity가 exact quarantine case digest·key·reviewer·outcome을 빠짐없이 결속하는가.
2. 동일 replay만 1행 수렴하고 changed/cross-key 충돌이 기존 quarantine/disposition을 바꾸지 않는가.
3. 새 disposition key·새 decision sequence·wrong case digest 공격이 `(case_id, case_digest)` composite FK로 실제 거부되는가.
4. disposition과 quarantine의 UPDATE/DELETE, operator view의 INSERT/UPDATE/DELETE가 실제 PostgreSQL에서 모두 거부되는가.
5. payment·receipt·retry·approval·execution authority가 모두 false인가.
6. multi-node preflight가 계약일 뿐이며 network partition·failover·fault injection을 실제 수행했다고 주장하지 않는가.
7. 원격 artifact SHA와 JSON, exact schema cleanup, production writes 0을 직접 대조할 수 있는가.

원격 actual PostgreSQL proof가 없거나 위 항목 하나라도 불충족이면 HOLD하고, 원인·권고 해결·대안·비용·위험·가역성·검증·중단·재개·rollback을 함께 제시한다.
