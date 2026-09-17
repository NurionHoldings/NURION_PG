# 기능 #066 — ARKAON 역할분리 Release Benchmark

Pattern Foundry의 apf.public.role-separated-benchmark 후보를 PG release evidence manifest
초안에 clean-room analog로 적용한다. 생산자, 공격자, 판정자, 승인자는 서로 다른 합성
actor여야 하며 공격 발견사항은 판정자에게 같은 digest로 전달되어야 한다.

어느 역할이든 critical failure를 기록하면 점수 합산과 무관하게 결과는 HOLD다. PASS도
release 승인이나 배포 승인이 아니며 합성 benchmark 결과 기록일 뿐이다.

Foundry 기준 commit은 24ae4a601ee449649e40804119fa37667f731076, package hash는
4bd1359b51ea2a958833ad52e91ab49b20b9f8777c6bb3d3f653504ac2f1eca7이다.
후보 상태 ETHERNIAN_REVIEW_REQUIRED를 유지한다.

최대 상태는 SYNTHETIC_PG_ROLE_SEPARATED_RELEASE_BENCHMARK_RECORDED이다. 외부서명,
패턴승격, release 승인, 병합, 배포, 외부 API 또는 실결제 권한은 없다.
