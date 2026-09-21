# NURION_PG #17101~#17500 에테르니언 독립검수

## 결론

**구조·로컬·원격 PostgreSQL actual deadlock 및 lock-contention 증명을 수락한다. PR #410은 OPEN 상태로 유지하며 병합·배포는 별도 인간 승인 전까지 금지한다.**

## 수락 범위

- 정확히 400 controls와 #9901~#17500 직접 evidence 19단계를 확인했다.
- disposable PostgreSQL의 두 backend가 두 행을 반대 순서로 잠가 실제 SQLSTATE `40P01` 피해자 1명과 승자 1명을 만들었다.
- 피해 transaction을 rollback하고 backend를 close한 뒤 다른 backend PID의 attempt 2가 성공했다.
- 별도 blocked-row 시험에서 실제 SQLSTATE `55P03`을 1회 확인하고 blind retry하지 않았다.
- `deadlock_timeout` session preflight, barrier 5초 제한, 예상 외 SQLSTATE, cleanup 실패는 모두 fail-closed한다.
- 실제 network partition과 failover는 증명했다고 주장하지 않는다.
- 운영 DB write·receipt·signature·key·금융·승인·활성화·배포는 모두 0이다.

## HOLD와 극복 이력

### Actual provenance 혼합 방지

- 원인: 초기 자체점검에서 실제 deadlock 이후 회복을 unit-injected `40P01`과 연결하면 실제 DB 증거와 주입 증거가 섞일 수 있었다.
- 권고안·반영: 실제 피해 transaction 종료 후 fresh backend에서 attempt 2를 직접 실행하고, unit exhaustion과 harness response-loss는 별도 provenance 필드로 유지한다.
- 대안: 모든 오류를 동일 mock sequence로 검증하는 방식은 재현은 쉽지만 실제 PostgreSQL 증명이 아니므로 채택하지 않았다.
- 비용·위험·가역성: disposable CI 연결 하나의 추가 비용으로 위험이 낮고 runner 제거로 완전 가역적이다.
- 검증·중단·재개·rollback: actual provenance, exactly-one victim/winner, fresh backend가 다르면 PASS를 중단한다. 원인을 수정한 새 disposable schema에서 전체 실증으로 재개하며 해당 schema만 rollback한다.

### Barrier 무기한 대기 방지

- 원인: participant 한쪽이 preflight에서 먼저 실패하면 다른 쪽이 barrier에서 무기한 대기할 수 있었다.
- 권고안·반영: barrier에 5초 timeout을 적용하고 timeout·broken barrier를 명시적 실패로 처리한다.
- 대안: CI job 전체 timeout만 사용하는 방식은 원인 식별과 빠른 cleanup이 어려워 채택하지 않았다.
- 비용·위험·가역성: 비용이 매우 낮고, 재현 속도가 5초를 초과하는 환경에서는 명시적 HOLD가 발생한다. timeout 값 변경으로 가역적이다.
- 검증·중단·재개·rollback: barrier 실패 시 artifact PASS 생성을 중단하고 두 연결을 닫은 뒤 schema cleanup한다. 환경 정상화 후 전체 job으로 재개한다.

### Registry 고정 기준 동기화

- 원인: 신규 lesson과 stage 추가 후 고정 기대값이 각각 34→35, 12→13으로 갱신되지 않았다.
- 권고안·반영: registry/stage 선언과 독립 cardinality anchor를 같은 변경 단위로 갱신했다.
- 대안: 기대수를 manifest에서 자동 파생할 수 있으나 독립 고정 anchor가 약해져 채택하지 않았다.
- 비용·위험·가역성: 비용·위험이 낮고 stage 선언 제거로 가역적이다.
- 검증·중단·재개·rollback: 불연속·중복·lesson regression 발견 시 중단하고 선언과 시험을 동기화한 뒤 full regression을 재실행한다.

## 검증 결과

- focused/registry: 22 PASS
- 전체 회귀: 1,963 PASS
- 직접 evidence chain: 19단계 PASS
- lesson registry: 35 PASS
- historical snapshot·prior-stage digest: PASS
- compileall·governance·diff-check·credential 정적검색: PASS
- 계약 Evidence SHA-256: `9cba697ef47c8bec80ecb5e8e894bfde04d29df3e3283ea9602826a2ff256af6`

## 원격 PostgreSQL 증거

- CI run: #1808, workflow run `35562697080`, head `ed312761639431778af1d9c5c438a7575c589c5a`
- 상태: `PASS_POSTGRES_DEADLOCK_PROOF`
- 실증 Evidence SHA-256: `b85434376856d2573b1d4fe26bcae6186e24189a293930c244d75b7453ad0864`
- artifact: `postgres-ephemeral-repository-proof`, ID `10622712428`, 2,585 bytes
- artifact ZIP SHA-256: `0d876698694876f0d5bb891942bbf8b47235910f0cf91bc13dc8d787766aabf9`
- PostgreSQL 실증, artifact upload, schema/container cleanup, ARKAON bootstrap이 모두 SUCCESS다.

## 잔여 위험

- 단일 CI PostgreSQL 인스턴스는 운영 failover, network partition, 복제 지연, 장기 부하를 증명하지 않는다.
- 운영 재시도 정책 적용, migration, receipt 발급, 금융 처리, 병합과 배포는 별도 승인 전까지 금지한다.
