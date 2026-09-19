# #5501~#5900 합성 검토 이의제기·재검토 계보

직전 운영자 검토 사전 도켓에 대해 입주사·NURION·본PG 전자문서 흐름의 이의제기 근거를 남기고 독립 재검토에 인계하는 합성·메모리 전용 계층이다. 결정을 내리거나 승인·활성화·배포하지 않는다.

## 통제 구조

16개 작업군에 25개 공통 aspect를 적용해 #5501~#5900의 정확히 400개 통제를 구성한다.

| 범위 | 작업군 |
|---|---|
| #5501~#5525 | PREFLIGHT_PACKET_SOURCE_ANCHOR |
| #5526~#5550 | LESSON_RULE_REGISTRY_BINDING |
| #5551~#5575 | TENANT_CHALLENGE_DOCUMENT |
| #5576~#5600 | NURION_CHALLENGE_DOCUMENT |
| #5601~#5625 | UPSTREAM_CHALLENGE_DOCUMENT |
| #5626~#5650 | FOUR_DIRECTION_CHALLENGE_ROUTE |
| #5651~#5675 | EVIDENCE_GAP_GROUND |
| #5676~#5700 | SEMANTIC_BINDING_GROUND |
| #5701~#5725 | ROLE_CONFLICT_GROUND |
| #5726~#5750 | PARTIAL_BATCH_GROUND |
| #5751~#5775 | LINEAGE_BREAK_GROUND |
| #5776~#5800 | RECONSIDERATION_ASSIGNMENT |
| #5801~#5825 | INDEPENDENT_REVIEWER_SEPARATION |
| #5826~#5850 | APPEND_ONLY_CHALLENGE_HOLD_CHAIN |
| #5851~#5875 | RECONSIDERATION_RECEIPT_LINEAGE |
| #5876~#5900 | NON_DECISION_ACTIVATION_BOUNDARY |

## 완전성 및 안전경계

- 세 당사자 전자문서 digest와 네 방향 route를 의미적으로 결속한다.
- 각 challenge 문서는 흐름의 발신 당사자·해당 당사자 원본 문서·route·이의 근거에서 파생하며 challenger도 발신 당사자와 정확히 일치해야 한다.
- 네 흐름 × 다섯 이의 근거의 정확히 20개 challenge와 20개 hold를 요구한다.
- readiness reviewer, preflight reviewer, reconsideration reviewer의 역할을 분리한다.
- 저장 key↔객체 의미, event↔artifact, hold↔challenge를 전체 상태에서 재구성한다.
- 최대 상태는 `RECONSIDERATION_DOCKET_READY_NOT_DECIDED_NOT_ACTIVATED`이다.
- 전송·서명·외부 PG/API·카드망·결제·승인·취소·환불·정산·송금·원장·자격증명·배포·활성화·운영 Prompt/정책/가중치 변경은 0이다.
