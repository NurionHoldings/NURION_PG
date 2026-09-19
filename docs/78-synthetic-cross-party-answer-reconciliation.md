# 합성 당사자 간 답변 교차검증·인간 조정 대기열 (#7901~#8300)

## 목적

입주사·NURION PG·본 PG의 합성 답변 자료를 실제 수락이나 조정 판단으로 연결하지 않고, 양방향 짝의 claim·manifest·receipt·version provenance를 교차검증하여 인간 조정 대기열로만 묶는다.

## 통제 구조

- 16개 workstream × 25개 aspect = 정확히 400개 통제
- 4방향 전자문서 흐름 × 5개 비교 유형 = 20개 reconciliation case와 hold
- 비교 결과는 답변 종류의 고정 라벨이 아니라 양방향 provenance의 실제 값 차이를 claim → manifest → receipt → version 순서로 계산한다.
- 합성 fixture는 일치, claim 불일치, manifest 불일치, receipt 불일치, version 충돌을 모두 재현한다.
- 각 provenance는 흐름·유형·발신·수신 당사자·answer·claim·manifest·receipt·version에 의미 결속된다.
- 반대 방향 provenance와 comparison 및 queue route를 순차 재계산하여 외곽 digest만 다시 계산한 치환을 차단한다.
- source reviewer 3명, compiler 3명, chair, intake validator, reconciliation submitter, cross-validator, queue compiler를 역할 충돌 집합으로 검증한다.
- case 또는 hold 한 건이라도 누락되면 fail-closed 한다.

## 안전 경계

최대 상태는 `HUMAN_RECONCILIATION_QUEUE_READY_NOT_ACCEPTED_NOT_DECIDED`이다. 실제 답변 수신·수락, 조정·추천·동의·결정·승인·활성화·배포, 문서 전송·전자서명, 외부 PG/API·카드망·금융 처리·원장 기록·자격증명 접근 능력은 없다.

## 결정론적 증적

`python scripts/run_synthetic_cross_party_answer_reconciliation_evidence.py`는 누적 lesson registry와 ARP-01~08을 검증한 뒤 evidence JSON과 SHA-256을 생성한다.
