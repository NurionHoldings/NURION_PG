# #3501~#3900 합성 설계 검증·전자문서 추적성

## 목적과 범위

P0 설계 기준선의 요구사항을 실제 구현 전에 검증 가능한 16개 workstream × 25개 통제로 변환한다. 모든 자료는 합성 데이터와 메모리에만 존재한다. 범위는 #3501부터 #3900까지 정확히 400개이며 누락·중복·부분 dossier는 거부한다.

## 16개 workstream

1. P0 기준선 요구사항 연결
2. 위협·수용기준 추적성
3. 신뢰경계 흐름 검증
4. 토큰화 데이터 제약
5. 개념 자금·원장 불변식
6. 생명주기 상태전이
7. 입주사/대행업체 당사자·역할 계약
8. 입주사 → NURION PG 전자문서 schema
9. NURION PG → 본 PG사 전자문서 schema
10. 양방향 field mapping
11. correlation·멱등성·receipt
12. consent·approval·hold gate
13. 문서 version·출처·검토 계보
14. 비실행 연동 adapter 초안 격리
15. 부분 batch fail-closed·append-only chain
16. 운영자 gate·비실행 경계

각 workstream은 input schema부터 non-execution까지 동일한 25개 검증 관점을 갖는다. control은 P0 anchor, requirement reference, threat, fixture digest, expected result, evidence digest, source version, owner role에 결속된다.

## 전자문서와 연동프로그램 초안

기록된 dossier에서만 다음 네 문서 초안을 자동 생성한다.

- 입주사/대행업체 → NURION PG 요청
- NURION PG → 본 PG사 요청
- 본 PG사 → NURION PG 응답
- NURION PG → 입주사/대행업체 응답

문서는 동일 correlation ID·idempotency key·schema version·field mapping을 공유하고 이전 문서 digest를 참조한다. 모든 문서와 adapter는 생성 근거 dossier digest 및 검토 receipt digest에 직접 결속되며, 7개 생성 사건은 별도의 append-only digest chain으로 기록된다. 입주사, NURION PG, 본 PG사의 adapter specification도 생성하지만 `SPECIFICATION_ONLY`이며 transport, 전자서명, 외부 API를 모두 비활성화한다.

## 안전 경계

- 문서 상태는 `DRAFT_ONLY`, consent와 approval은 항상 미기록이다.
- 실제 전송·서명·운영 등록·외부 PG/API·카드망·결제·원장·송금 능력이 없다.
- 운영 자격증명을 읽지 않으며 정책·Prompt·가중치를 바꾸지 않는다.
- 부분 문서나 adapter, 계보 단절, digest를 다시 계산한 의미 변조도 fail-closed 처리한다.
- 최대 상태는 검증 추적성의 기록이며 운영 승인이나 구현 승격이 아니다.
