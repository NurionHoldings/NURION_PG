# Synthetic Feasibility Decision Portfolio (#2701-#2900)

## 목적과 경계

#2501~#2700에서 생성된 비권한 decision docket의 최종 기록을 typed boundary에서
검증하고, 최대 20개씩 관찰 포트폴리오로 집계한다. 이 계층은 결정 분포와
보류/기록 상태를 관찰할 뿐 승인·실행·배포 권한을 만들지 않는다.

## 8개 통제 workstream

| 범위 | 통제 |
|---|---|
| #2701~#2725 | typed docket boundary |
| #2726~#2750 | 최대 20개 portfolio batch |
| #2751~#2775 | source digest/version 결속 |
| #2776~#2800 | OBSERVE/REASSESS/HOLD 분포 |
| #2801~#2825 | HELD/RECORDED 상태 분리 |
| #2826~#2850 | 독립 portfolio review |
| #2851~#2875 | replay/conflict/concurrency 차단 |
| #2876~#2900 | append-only audit evidence |

각 workstream은 정확히 25개 통제로 구성되어 총 200개다.

## 불변조건

- upstream `DocketRecord` 타입·digest·version·decision·terminal state를 재검증한다.
- source는 한 포트폴리오에만 속하며 교차 포트폴리오 replay를 차단한다.
- curator/reviewer/verifier/auditor를 역할과 identity 기준으로 분리한다.
- review와 receipt는 멱등이며 충돌 및 stale version을 fail-closed 처리한다.
- source, portfolio, event, artifact, hold는 append-only digest chain으로 검증한다.
- 최대 상태는 `SYNTHETIC_DECISION_PORTFOLIO_RECORDED`다.
- 외부 호출, 원장 기록, 결제·승인·배포, 운영 정책 변경은 모두 0이다.

## ARKAON capability upgrade

이번 범위에서 terminal source 의미 검증, 상태별 집계 재계산, membership index
패리티, semantic tamper 탐지와 capability-gap evidence를 추가했다. 무결성 관찰
공백은 `capability_gap_evidence.fail_closed=true`로 나타난다.
정확한 200개 통제 매트릭스의 누락·중복·범위 이탈·변형도 동일하게
fail-closed 처리한다. 외부에서 다시 해시한 source record 역시 source version,
member bound, 역할분리, hold 사유의 의미 검증을 통과해야 한다.
