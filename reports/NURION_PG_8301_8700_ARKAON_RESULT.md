# NURION PG #8301~#8700 아르카온 결과

## 확정 주제

합성 당사자별 조정 제안·반론·증거 참조 전자문서 계보 검증 및 인간 조정 hold docket.

## 구현 결과

- 통제 번호: #8301~#8700 연속 400개
- 구조: 16 workstream × 25 aspect
- 합성 검증 대상: 20 source case, 60 submission, 20 bundle·hold
- 저장: 메모리 전용
- 선적용 학습: 누적 ARL 13개 및 ARP-01~08
- 최대 상태: `RECONCILIATION_SUBMISSION_HOLD_DOCKET_READY_NOT_ACCEPTED_NOT_DECIDED`

## 자가진단과 즉시 보완

초기 source projection이 비교 결과 문자열과 opaque digest만 보유하면 종류 라벨을 바꾸고 case digest를 다시 계산할 수 있음을 확인했다. source/counterpart의 claim·manifest·receipt·version 값을 anchor에 직접 투영하고, 검증 시 실제 차이를 claim → manifest → receipt → version 순서로 재계산하도록 즉시 보완했다. 제안·반론·증거 작성 당사자도 호출자 문자열이 아니라 흐름 및 submission 종류에서 파생하고, parent·content·bundle·hold route를 모두 사후 재계산한다.

## 금지 능력 확인

실제 문서 전송·전자서명·수락·추천·결정·승인·활성화·배포·외부 PG/API·카드망·결제·취소·환불·정산·송금·원장·자격증명·운영 Prompt/정책/가중치 변경 능력은 포함하지 않는다.

## 검증 결과

- 전용 테스트: 41 PASS
- 전체 회귀 테스트: 1,458 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `53e33868d3c53260ffb4b7c105a2fc8420d9f6549b19699933a7348cf49d8b85`

> 에테르니언 독립 감사에서 source case-set digest 파생과 즉시 이전 제출문서 parent 계보 미비점이 발견되었다. 위 수치는 아르카온 1차 결과이며 최종 판정은 `NURION_PG_8301_8700_ETHERNian_AUDIT.md`를 따른다.
