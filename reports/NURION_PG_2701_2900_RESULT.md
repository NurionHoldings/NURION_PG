# NURION PG #2701~#2900 구현·1차 검증 결과

- 브랜치: `feat/2701-2900-synthetic-feasibility-decision-portfolio`
- 범위: Synthetic Feasibility Decision Portfolio, 8 × 25 = 200 controls
- 실행 경계: synthetic/in-memory only
- 최대 상태: `SYNTHETIC_DECISION_PORTFOLIO_RECORDED`

## 구현 결과

- typed upstream docket digest/state/version/decision 검증
- 최대 20개 portfolio batch와 unique membership
- OBSERVE/REASSESS/HOLD 분포 및 HELD/RECORDED 상태 분리
- curator/reviewer/verifier/auditor 역할 분리
- idempotency/conflict/stale version/concurrency/replay 차단
- append-only source/portfolio/event/review/receipt/hold 무결성
- semantic aggregate 및 membership index 변조 탐지
- deterministic capability-gap evidence

## 검증 결과

- 전용 테스트: 29 PASS
- 전체 회귀 테스트: 922 PASS
- compileall: PASS
- git diff --check: PASS
- evidence 2회 결정론 검증: `2e0ce90e428481ac827096968d3fabe2b1d5a3bc22f98fc330a96125fec8f742`

## ARKAON 자기보완

1차 구현 자체 감사에서 downstream 역할이 upstream observer/analyst와 같은 identity를
재사용할 가능성을 발견했다. reviewer/verifier/auditor까지 모든 upstream 역할과
분리하도록 즉시 강화하고 전용 회귀검사를 추가했다.

실결제·승인·취소·환불·정산·송금, 외부 PG/카드망, 운영 자격증명,
실제 원장, 운영 정책·Prompt·가중치 변경, 원격 push/PR/merge/deploy는 수행하지 않았다.

## Ethernian 독립 감사 보완

- 재해시된 source record라도 source version, member bound, upstream 역할분리,
  hold 사유가 의미적으로 잘못되면 차단하도록 typed boundary를 강화했다.
- hold event를 정확한 attachment에 결속하고 hold reason, actor namespace,
  역할 독립성, rejected-review provenance를 재검증한다.
- capability-gap evidence가 200개 통제 매트릭스의 누락·중복·변형도
  fail-closed로 탐지하도록 확장했다.
