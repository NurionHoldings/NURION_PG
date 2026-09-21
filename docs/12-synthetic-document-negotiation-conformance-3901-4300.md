# #3901~#4300 합성 전자문서 협상·적합성 계층

## 목적

#3501~#3900에서 생성한 입주사/대행업체↔NURION PG↔본 PG사의 4개 `DRAFT_ONLY` 전자문서와 3개 `SPECIFICATION_ONLY` adapter를 입력 기준선으로 봉인한다. 이를 당사자 capability, schema version 교집합, 허용된 field mapping AST, 협상 라운드, 400개 합성 conformance case, 독립 검토 receipt로 발전시킨다. 결과는 구현·승인안이 아니라 검토 가능한 설계 패키지다.

## 16×25 통제

1. source draft bundle anchor
2. party capability profiles
3. schema offer negotiation
4. version range compatibility
5. field mapping rule AST
6. token class preservation
7. required/nullability conformance
8. enum/code translation
9. precision/timezone canonicalization
10. error taxonomy mapping
11. correlation/idempotency binding
12. order/replay/concurrency cases
13. round transcript append-only
14. independent review receipts
15. partial package hold chain
16. operator gate/non-execution boundary

각 workstream은 input부터 non-execution까지 동일한 25개 관점으로 구성되어 #3901~#4300을 누락·중복 없이 덮는다. 부분 source bundle, 세 당사자 profile 누락, schema version 교집합 불일치, 허용목록 밖 변환, 중복 source field, 라운드 계보 충돌, 400 case 미완성은 fail-closed 한다.

독립 감사 보완으로 mapping rule의 operation과 token class는 세 당사자 profile 모두의 공통 지원 집합에 포함되어야 한다. conformance case와 review receipt는 항상 최신 협상 라운드에만 결속되며, receipt의 author identity는 최신 proposer에서 파생되어 호출자가 대체할 수 없다. append-only event는 허용된 action뿐 아니라 실제 artifact digest와도 일치해야 한다.

## 산출 흐름과 안전경계

- source: 4 document digest + 3 adapter digest + dossier/receipt digest
- specification: 세 당사자 capability와 `COPY_TOKEN`, `RENAME`, `ENUM_LOOKUP`, `UTC_NORMALIZE`, `DECIMAL_STRING`만 허용하는 비실행 mapping AST
- negotiation: 동일 correlation/idempotency에 묶인 최대 3개 `REVIEW_REQUIRED` 라운드
- verification: 정확히 400개 합성 case와 독립 reviewer receipt
- 최대 상태: `REVIEW_RECORDED_NOT_APPROVED`

네트워크 transport, 전자서명, 본 PG API, 카드망, 결제·취소·환불·정산·송금, 실제 원장, 운영 자격증명, 배포, 운영 정책·Prompt·가중치 변경 능력은 포함하지 않는다.
