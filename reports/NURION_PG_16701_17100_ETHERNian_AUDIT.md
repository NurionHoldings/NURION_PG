# NURION_PG #16701~#17100 에테르니언 독립검수

## 결론

**구조·로컬·원격 PostgreSQL retry resilience 증명을 수락한다. PR #409는 OPEN 상태로 유지하며 병합·배포는 별도 인간 승인 전까지 금지한다.**

## 수락 범위

- 정확히 400 controls와 #9901~#17100 직접 evidence 18단계를 확인했다.
- 실제 disposable PostgreSQL `SERIALIZABLE` write-skew에서 SQLSTATE `40001`이 정확히 1회 발생하고, 실패 연결을 rollback·close한 뒤 다른 backend PID의 두 번째 시도가 성공했다.
- 실제 SQLSTATE `57014` timeout은 1회만 시도하고 blind retry하지 않았다.
- retry 최대치는 3회이며, 3회 소진 fail-closed는 실제 DB 연속 장애가 아니라 `UNIT_INJECTED_SQLSTATE_SEQUENCE` 단위시험이다.
- commit-unknown은 실제 network partition이 아니라 commit 직후 `HARNESS_INJECTED_POST_COMMIT_RESPONSE_LOSS`이다. 새 연결 read-back은 `EXISTING_SAME_PAYLOAD`와 exact digest만 수락한다.
- 실제 deadlock, network partition, retry exhaustion은 증명했다고 주장하지 않는다.
- 운영 DB write·receipt·signature·key·금융·승인·활성화·배포는 모두 0이다.

## HOLD와 극복 지침

### Read-back 상태 엄격성

- 원인: 최초 계약은 순수 fresh read-back에서 `INSERTED` 상태까지 수락할 수 있었다.
- 권고안·반영: `EXISTING_SAME_PAYLOAD`와 exact digest만 수락하고 `INSERTED`·OTHER·absence·mismatch를 모두 HOLD한다.
- 대안: read-back에서 insert-or-read를 다시 호출하는 방식은 중복 쓰기와 결과 혼동 위험이 있어 채택하지 않았다.
- 비용·위험·가역성: 비용과 변경 위험이 낮고 단일 validator rollback으로 완전 가역적이다.
- 검증·중단·재개: 네 가지 음성 경로를 단위시험한다. 하나라도 수락되면 PASS를 중단하고 read-only 조회 경계를 복구한 뒤 전체 proof를 재실행한다.

### 실제 증거와 주입 증거 분리

- 원인: `retry_exhaustion_fail_closed=true`만으로는 실제 PostgreSQL에서 3회 연속 abort를 재현했다고 오해할 수 있었다.
- 권고안·반영: 실제 `40001` 1회→attempt 2 성공과 실제 `57014` 1회만 PostgreSQL 증거로 결속한다. exhaustion은 unit-injected, response loss는 harness-injected, deadlock/network partition은 미주장으로 명시한다.
- 대안: 실제 3연속 serialization abort나 network partition을 강제하는 방식은 CI 재현성과 장애 경계가 불안정해 이번 단계에서는 채택하지 않았다.
- 비용·위험·가역성: 증거 필드 추가 비용은 낮고 과장 수락 위험을 크게 낮춘다. 필드는 계약 버전 내에서 제거 가능하다.
- 검증·중단·재개·rollback: provenance·attempt·actual-claim 필드 변조를 거부한다. 실제값과 계약값이 다르면 disposable schema만 cleanup하고 원인을 수정한 새 HEAD의 전체 CI로 재개한다.

## 검증 결과

- focused/adjacent: 20 PASS
- 전체 회귀: 1,957 PASS
- 직접 evidence chain: 18단계 PASS
- historical #7501 snapshot: PASS
- lesson registry: 34 PASS
- compileall·governance·diff-check: PASS
- 계약 Evidence SHA-256: `abe651b1b143a2c4d6719eb1185329bc3a87a167270e738ae579329e3a9795d6`

## 원격 PostgreSQL 증거

- CI run: #1791, workflow run `35557306944`, head `431f48ad82d2f6b4cd20d66801cd9942c80b28de`
- 상태: `PASS_POSTGRES_RETRY_RESILIENCE`
- 실증 Evidence SHA-256: `6c096c6fc0198eaed665f03b20fad4dfc47a885c721cf7e4bb071fc0cc54d749`
- artifact: `postgres-ephemeral-repository-proof`, ID `10620647981`, 1,696 bytes
- artifact ZIP SHA-256: `a9bb2d60564795797a8d6d1403b06e40aaf5d2abb46e17788160cad9975b06c1`
- PostgreSQL 실증, artifact upload, schema/container cleanup, ARKAON bootstrap이 모두 SUCCESS다.

## 잔여 위험

- 단일 CI PostgreSQL 인스턴스는 실제 운영 부하, 장기 연결 불안정, failover, 복제 지연을 증명하지 않는다.
- deadlock과 실제 network partition 검증은 후속 독립 단계가 필요하다.
- 운영 재시도 정책 적용, migration, receipt 발급, 금융 처리, 병합과 배포는 별도 승인 전까지 금지한다.
