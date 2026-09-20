# NURION PG #9901~#10300 설계 — 합성 응답 독립검토·반박·정정 계보

## 1. 목적

#9501~#9900에서 접수된 20개 clarification response intake를 독립 검토하고, 실제 응답이 필요한 16개 항목에 한해서만 검토의견·반박기회·정정요청을 연결한다. 이 단계는 사실판단이나 승인 단계가 아니다. 모든 결과는 미결 상태로 보존하며 사람의 다음 판단을 기다린다.

최대 상태는 다음으로 고정한다.

`RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_READY_ON_HOLD_NOT_RESOLVED`

## 2. 절대 경계

- 합성 데이터와 메모리 저장만 허용한다.
- 실제 문서 전송·전자서명·외부 PG/API·카드망 호출을 금지한다.
- 결제·취소·환불·정산·송금·실원장 기록을 금지한다.
- 답변의 진실성 판정, 분쟁 결론, 추천, 수락, 승인, 활성화를 금지한다.
- 운영 자격증명 조회, 배포, 운영 정책·Prompt·가중치 변경을 금지한다.
- CI 성공을 운영승인으로 해석하지 않는다.

## 3. 입력 계약

입력은 #9501~#9900의 완전한 최신 docket 하나만 허용한다.

- 20개 ordered intake position
- 16개 response document와 4개 no-response marker
- 각 intake의 flow, answer kind, request digest, responder, response document digest
- 즉시 이전 intake digest
- 13개 upstream source role
- response-intake compiler와 validator
- source docket digest와 ordered intake-set digest
- 누적 lesson registry·remediation manifest digest
- source sequence와 `is_latest=true`

입력 전체가 없거나 순서가 다르거나 최신이 아니면 fail-closed 한다.

## 4. 의미값 재계산

아르카온은 전달된 라벨이나 digest를 신뢰하지 않는다.

1. flow와 answer kind로 20개 위치를 다시 계산한다.
2. source request의 outcome과 response-required 상태를 다시 확인한다.
3. `CONSISTENT` 위치에는 response document가 없어야 한다.
4. conflict 위치에는 flow로부터 파생된 responder와 response document가 있어야 한다.
5. intake projection digest를 의미값에서 재생성한다.
6. 20개 projection의 정렬 집합으로 intake-set digest를 다시 계산한다.
7. source docket과 full-lineage digest를 다시 계산한다.

내부 의미값부터 최외곽 anchor까지 모두 다시 해시한 변조도 거부해야 한다.

## 5. 처리 구조

### 5.1 독립 검토

16개 response document 각각에 대해 `REVIEW_REQUIRED` 항목을 생성한다. 검토자는 upstream 15개 역할 및 response 작성자와 다른 identity여야 한다.

검토 결과는 다음 세 가지 중 하나만 허용한다.

- `CLARIFICATION_SUFFICIENT_FOR_NEXT_HUMAN_REVIEW`
- `REBUTTAL_OPPORTUNITY_REQUIRED`
- `CORRECTION_REQUEST_REQUIRED`

이 값들은 결론이나 승인으로 해석하지 않는다.

### 5.2 반박기회

`REBUTTAL_OPPORTUNITY_REQUIRED`에만 반박 슬롯을 생성한다. 반박문이 아직 없더라도 슬롯과 hold는 보존한다. 반박자를 검토자로 재사용할 수 없다.

### 5.3 정정요청

`CORRECTION_REQUEST_REQUIRED`에만 정정요청을 생성한다. 정정요청은 원본 response, review, 선택적 rebuttal의 digest를 모두 포함해야 한다. 정정본을 자동 생성하거나 원본을 덮어쓰지 않는다.

### 5.4 미결 docket

20개 위치를 모두 보존한다.

- 4개 no-response 위치: `NOT_APPLICABLE_PRESERVED`
- 16개 response 위치: review 결과와 필요한 hold 보존
- 누락·부분 batch·순서 변경·중간 문서 생략 시 완료 불가

## 6. 역할 분리

다음 역할의 namespace·순서·identity를 모두 검증한다.

1. readiness reviewer
2. preflight reviewer
3. reconsideration reviewer
4~7. packet compiler 4명
8. human deliberation chair
9. cross-party validator
10. issue-matrix compiler
11. issue-matrix validator
12. clarification drafter
13. clarification reviewer
14. response-intake compiler
15. response-intake validator
16. response independent reviewer
17. rebuttal custodian
18. correction-request compiler

한 사람이 둘 이상의 역할로 재등장하면 거부한다.

## 7. 400개 통제 매트릭스

16개 workstream에 각각 25개 공통 aspect를 적용한다.

### Workstream

1. `RESPONSE_INTAKE_DOCKET_ANCHOR`
2. `LESSON_RULE_REGISTRY_BINDING`
3. `INTAKE_SEMANTIC_RECONSTRUCTION`
4. `NO_RESPONSE_MARKER_PRESERVATION`
5. `RESPONSE_DOCUMENT_PROJECTION`
6. `INDEPENDENT_REVIEW_ASSIGNMENT`
7. `REVIEW_RESULT_CONSTRAINED_CLASSIFICATION`
8. `REBUTTAL_OPPORTUNITY_ROUTING`
9. `CORRECTION_REQUEST_ROUTING`
10. `IMMEDIATE_PARENT_DOCUMENT_LINEAGE`
11. `SOURCE_ROLE_NAMESPACE_PROJECTION`
12. `NEW_ROLE_SEPARATION`
13. `APPEND_ONLY_REVIEW_EVENT`
14. `UNRESOLVED_HOLD_CHAIN`
15. `PARTIAL_BATCH_FAIL_CLOSED`
16. `NON_RESOLUTION_NON_EXECUTION_BOUNDARY`

### 공통 aspect

`input_schema`, `required_fields`, `semantic_label`, `source_type`, `tenant_scope`, `role_scope`, `state_precondition`, `latest_sequence`, `source_binding`, `digest_recalculation`, `negative_path`, `missing_input`, `duplicate_input`, `replay`, `conflict`, `stale_version`, `concurrency`, `partial_batch`, `ordering`, `append_only`, `hold_propagation`, `review_independence`, `receipt_lineage`, `operator_gate`, `non_execution`

번호는 #9901부터 #10300까지 정확히 연속되어야 한다.

## 8. 상태 전이

```text
RESPONSE_INTAKE_DOCKET_ANCHORED
  -> RESPONSE_REVIEWS_RECORDED
  -> REBUTTAL_AND_CORRECTION_ROUTES_RECORDED
  -> RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_READY_ON_HOLD_NOT_RESOLVED
```

역방향 전이, 건너뛰기, 자동 resolved 전이는 허용하지 않는다.

## 9. 필수 부정 테스트

- control slot 교환 후 재해시
- source intake 의미값 전체 재해시 치환
- no-response 위치에 response 삽입
- conflict 위치의 response 제거
- responder party 치환
- source role namespace 전체 치환
- independent reviewer와 기존 역할 충돌
- rebuttal custodian과 reviewer 충돌
- correction compiler와 response 작성자 충돌
- review 결과의 임의 라벨 변경
- response → correction으로 rebuttal 중간문서 건너뛰기
- immediate-parent digest 변경
- intake/review/rebuttal/correction 일부 누락
- append-only event 또는 hold 삭제·재정렬
- completed/answered/resolved/recommended/accepted/approved/activated/deployed 변조
- 동시 idempotency와 동일 키 충돌

## 10. 아르카온 강제 학습 적용

구현 전에 `ARL-3901-001`부터 `ARL-9501-001`까지 읽고 evidence에 전체 ID와 registry digest를 기록한다.

특히 다음 규칙은 생략할 수 없다.

- 라벨이 아니라 실제 의미값에서 상태를 파생한다.
- ordered complete set에서 집합 digest를 재생성한다.
- 즉시 이전 문서만 parent로 허용한다.
- 역할은 인원수뿐 아니라 namespace·순서·identity까지 검증한다.
- 에테르니언이 수정한 결함은 신규 remediation·lesson·실제 부정 테스트로 등록한다.
- 누적 lesson이나 필수 테스트가 하나라도 빠지면 후속 단계와 evidence 생성을 차단한다.

## 11. 완료 조건

- 정확히 400개 통제 등록
- 20개 intake position 완전 보존
- 16개 response review와 4개 N/A marker
- 필요한 rebuttal/correction route와 hold 완전 생성
- source/new role 완전 분리
- append-only event·hold chain 검증
- 전용·누적 lesson·전체 회귀 PASS
- evidence 2회 byte-for-byte 동일
- `compileall`, `git diff --check` PASS
- 최대 상태와 모든 non-execution counter 확인

이 조건을 모두 만족해도 결과는 구현·배포·운영승인이 아니라 다음 사람 검토를 위한 합성 docket일 뿐이다.
