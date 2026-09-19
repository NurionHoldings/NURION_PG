# #4701~#5100 합성 온보딩 리허설·준비도 인계 도켓

직전 단계의 입주사–NURION PG–본 PG사 전자문서·연동 패키지를 실제 연결 전에 검증하는 합성·메모리 전용 계층이다. 전송기, 서명기, 외부 API client, 카드망, 금융 처리, 원장 쓰기, 자격증명 loader, 배포기는 존재하지 않는다. 최대 상태는 `READY_FOR_OPERATOR_REVIEW_NOT_ACTIVATED`이며 운영자 검토가 활성화나 승인을 뜻하지 않는다.

## 정확히 400개 통제

16개 작업군마다 공통 25개 aspect를 적용한다. 통제 ID는 `4701 + 작업군 index×25 + aspect index`로 계산하여 #4701~#5100에 누락·중복 없이 배치한다.

| 범위 | 작업군 |
|---|---|
| #4701~#4725 | ACCEPTED_PACKAGE_SOURCE_ANCHOR |
| #4726~#4750 | LESSON_REGISTRY_APPLICATION |
| #4751~#4775 | PARTY_CAPABILITY_INTERSECTION |
| #4776~#4800 | TENANT_ONBOARDING_BLUEPRINT |
| #4801~#4825 | UPSTREAM_ONBOARDING_BLUEPRINT |
| #4826~#4850 | FOUR_DIRECTION_ROUTE_REHEARSAL |
| #4851~#4875 | DOCUMENT_SCHEMA_REHEARSAL |
| #4876~#4900 | TOKEN_BOUNDARY_REHEARSAL |
| #4901~#4925 | IDEMPOTENCY_REPLAY_REHEARSAL |
| #4926~#4950 | ORDERING_CONCURRENCY_REHEARSAL |
| #4951~#4975 | FAILURE_RECOVERY_REHEARSAL |
| #4976~#5000 | PARTIAL_BATCH_FAIL_CLOSED |
| #5001~#5025 | REHEARSAL_RESULT_LINEAGE |
| #5026~#5050 | INDEPENDENT_READINESS_REVIEW |
| #5051~#5075 | APPEND_ONLY_HOLD_CHAIN |
| #5076~#5100 | OPERATOR_ACTIVATION_GATE_BOUNDARY |

공통 aspect는 input/필수값/의미 label/source type/tenant/role/state/latest/source/digest/negative/missing/duplicate/replay/conflict/stale/concurrency/partial/order/append-only/hold/review/receipt/operator gate/non-execution의 25종이다.

## 누적 lesson의 선적용

- `ARL-3901-001`: 최신 source, source-derived maker, 공통 capability, event↔artifact 재구성
- `ARL-4301-001`: assembler를 source anchor에서 파생하고 route digest를 원 입력으로 재계산
- `ARL-4301-002`: readiness/activation/deployment boolean과 최대 상태를 사후 검증
- `ARL-4301-003`: Git history가 아닌 stable remediation ID↔lesson one-to-one 검증
- `ARP-01~08`: 의미 결속, 양 source 계보, 최신성, 역할분리, 파생 digest, 공통능력, event 의미, 안전상태

evidence는 lesson registry와 안정적인 재발방지 manifest의 SHA-256, 적용 lesson/rule ID를 기록한다. Git commit graph는 CI clone 방식에 따라 달라질 수 있으므로 lesson 적용 판단의 권위 source로 사용하지 않는다.

## fail-closed 경계

- 400개 통제, 세 당사자 capability profile, 최신 accepted-package anchor가 모두 있어야 계획을 만든다.
- 4방향×6종의 정확한 24개 계획이 없으면 리허설을 거부하고 hold chain에 기록한다.
- partial batch는 성공으로 흡수하지 않고 합성 결과 `FAIL_CLOSED`로 고정한다.
- reviewer는 source anchor의 assembler와 달라야 한다.
- event는 현재 도메인 상태에서 action과 artifact digest를 재구성하여 대조한다.
- 최종 receipt는 `activation_recorded=false`, `deployment_recorded=false`를 유지한다.
## 에테르니언 독립 감사 보완

공통 capability는 고정 결론값을 신뢰하지 않고 세 당사자의 operation·token-class profile 명세에서 교집합을 다시 계산한다. anchor·plan·result·receipt의 식별자 namespace와 source digest도 evidence 직전 사후 무결성 검사에서 재검증한다. 이 보완은 `ARL-4701-001`로 즉시 lesson registry에 환류된다.
