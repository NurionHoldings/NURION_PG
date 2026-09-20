# #5901~#6300 합성 증거 공개·반박·정정 준비도

직전 재검토 계보를 입주사·NURION·본PG 사이 전자문서의 증거 공개 초안, 상대방 반박 초안, 정정 초안으로 확장하는 합성·메모리 전용 계층이다. 외부 공개·전송·서명·결정·승인·활성화·배포는 수행하지 않는다.

## 통제 구조

16개 작업군에 25개 공통 aspect를 적용해 #5901~#6300의 정확히 400개 통제를 구성한다.

| 범위 | 작업군 |
|---|---|
| #5901~#5925 | RECONSIDERATION_RECEIPT_ANCHOR |
| #5926~#5950 | LESSON_RULE_REGISTRY_BINDING |
| #5951~#5975 | TENANT_DISCLOSURE_DOCUMENT |
| #5976~#6000 | NURION_DISCLOSURE_DOCUMENT |
| #6001~#6025 | UPSTREAM_DISCLOSURE_DOCUMENT |
| #6026~#6050 | FOUR_DIRECTION_DISCLOSURE_ROUTE |
| #6051~#6075 | EVIDENCE_GAP_DISCLOSURE |
| #6076~#6100 | SEMANTIC_BINDING_DISCLOSURE |
| #6101~#6125 | ROLE_CONFLICT_DISCLOSURE |
| #6126~#6150 | PARTIAL_BATCH_DISCLOSURE |
| #6151~#6175 | LINEAGE_BREAK_DISCLOSURE |
| #6176~#6200 | COUNTERPARTY_REBUTTAL_DOCUMENT |
| #6201~#6225 | CORRECTION_DRAFT_PROVENANCE |
| #6226~#6250 | APPEND_ONLY_CORRECTION_HOLD_CHAIN |
| #6251~#6275 | INDEPENDENT_PACKET_COMPILATION |
| #6276~#6300 | NON_PUBLICATION_EXECUTION_BOUNDARY |

## 완전성 및 안전경계

- 세 당사자 전자문서와 네 방향 route를 의미적으로 결속한다.
- 네 흐름 × 다섯 주제의 정확히 20개 case와 20개 hold를 요구한다.
- 공개 문서는 발신 당사자 원문·flow·topic·route·challenge set에서 파생한다.
- 반박 문서는 정확한 상대 당사자와 공개 문서에서, 정정 초안은 공개·반박 문서 모두에서 파생한다.
- source reviewer 3인과 packet compiler의 역할을 분리한다.
- reconsideration receipt digest와 세 source reviewer를 reviewer-lineage digest로 직접 결속한다.
- control·case 저장 key, event artifact, hold attachment를 전체 상태에서 재구성한다.
- 최대 상태는 `CORRECTION_READINESS_PACKET_READY_NOT_PUBLISHED_NOT_DECIDED`이다.
- 공개·전송·서명·외부 PG/API·카드망·결제·승인·취소·환불·정산·송금·원장·자격증명·배포·활성화·운영 Prompt/정책/가중치 변경은 0이다.
