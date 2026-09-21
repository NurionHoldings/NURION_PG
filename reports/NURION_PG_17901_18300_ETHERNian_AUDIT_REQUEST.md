# #17901–#18300 ETHERNIAN 독립검수 요청

- case identity가 source event/idempotency/payload/SQLSTATE/provenance를 domain-separated digest로 exact 결속하는지
- observed_at·sequence·state 및 unique constraints가 실제 live PostgreSQL에서 강제되는지
- same-envelope replay가 1행으로 수렴하고 changed payload/cross-key가 rollback되는지
- UPDATE·DELETE가 실제 차단되고 original case가 보존되는지
- quarantine case와 operator packet에 payment·receipt·retry·approval 권한이 없는지
- fresh read-only 조회이며 precommit source row/retry가 0인지
- operator view가 집계형으로 inherently non-updatable이며 write-capable 연결의 INSERT·UPDATE·DELETE가 모두 실제 거부되는지
- observed_at이 문자열 prefix 없이 SQL `timestamptz` exact equality로 검증되는지
- 실제 network partition·failover·운영처리를 과장하지 않는지
- cleanup, artifact digest, 400 controls, 21단계 chain, lesson registry가 완전한지
- 모든 HOLD에 원인·되는 방향·대안·비용·위험·가역성·검증·중단·재개·rollback이 있는지
