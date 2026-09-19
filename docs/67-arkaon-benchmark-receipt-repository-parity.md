# 기능 #067 — ARKAON Benchmark 영수증 Repository Contract Parity

Pattern Foundry의 apf.public.repository-contract-parity 불변조건을 역할분리 benchmark
영수증에 clean-room analog로 적용한다. 동일한 합성 계약을 memory adapter와
in-memory SQLite adapter에 실행하며 최초 저장, 동일 재시도, key-payload 충돌 거부가
같은 결과를 내야 한다.

SQLite는 파일을 만들지 않는 :memory: 연결만 사용한다. PostgreSQL, 운영 DB, 외부
네트워크, 실제 결제자료는 사용하지 않는다. PASS는 repository 계약의 합성 일치만
의미하며 release·운영·배포 승인이 아니다.

Foundry 기준 commit은 24ae4a601ee449649e40804119fa37667f731076이며 후보 상태
ETHERNIAN_REVIEW_REQUIRED를 유지한다. 최대 상태는
SYNTHETIC_PG_BENCHMARK_RECEIPT_REPOSITORY_CONTRACT_PARITY_VERIFIED이다.
