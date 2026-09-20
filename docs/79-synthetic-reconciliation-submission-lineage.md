# 합성 조정 제안·반론·증거 계보 및 인간 보류 docket (#8301~#8700)

## 목적

입주사·NURION PG·본 PG의 양방향 조정 대기열 다음 단계에서 당사자별 비구속 제안, 반론, 증거 참조 전자문서를 합성 구조로만 생성하고 계보를 검증한다. 어떤 자료도 결론·추천·수락·승인으로 전환하지 않고 인간 검토 hold에 둔다.

## 통제 구조

- 16개 workstream × 25개 aspect = 정확히 400개 통제
- 4방향 × 5개 답변 유형 = 20개 source case
- case마다 비구속 제안·반론·증거 참조 3건 = 60개 submission, 20개 bundle·hold
- source case set digest는 정렬된 20개 case digest에서 재계산한다.
- 이전 비교 결과는 종류 라벨이 아니라 claim → manifest → receipt → version 실제 값 차이에서 다시 도출한다.
- 제안·증거 작성 당사자는 흐름의 발신자, 반론 작성 당사자는 수신자로 파생한다.
- 제출 parent는 `제안 → 반론 → 증거 참조`의 직전 문서를 반드시 가리키며 content digest는 source case, 실제 비교 결과, 문서 종류, 작성 당사자, 순번에서 재계산한다.
- source reviewer·compiler·chair·validator와 작성자·lineage validator·bundle compiler·docket compiler의 역할 충돌을 차단한다.
- submission, bundle, hold 일부 누락이나 append-only event 불일치는 fail-closed 한다.

## 안전 경계

최대 상태는 `RECONCILIATION_SUBMISSION_HOLD_DOCKET_READY_NOT_ACCEPTED_NOT_DECIDED`이다. 실제 문서 전송·서명·수락·추천·결정·승인·활성화·배포, 외부 PG/API·카드망, 결제·취소·환불·정산·송금, 원장·운영 자격증명 접근 능력은 없다.

## 결정론적 증적

`python scripts/run_synthetic_reconciliation_submission_lineage_evidence.py`는 누적 14개 lesson과 ARP-01~08을 검증한 뒤 evidence JSON 및 SHA-256을 생성한다.
