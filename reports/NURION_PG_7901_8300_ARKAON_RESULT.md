# NURION PG #7901~#8300 아르카온 결과

## 확정 주제

합성 당사자 간 답변 교차 일치·불일치·버전 충돌 검증 및 인간 조정 대기열.

## 구현 결과

- 통제 번호: #7901~#8300 연속 400개
- 구조: 16 workstream × 25 aspect
- 합성 검증 대상: 4방향 × 5개 비교 유형 = 20개 case·hold
- 저장: 메모리 전용
- 선적용 학습: ARL-3901-001~ARL-7501-001, ARP-01~08
- 최대 상태: `HUMAN_RECONCILIATION_QUEUE_READY_NOT_ACCEPTED_NOT_DECIDED`

## 자가진단과 즉시 보완

초기 설계에서 이전 answer digest만 비교하면 claim·manifest·receipt·version의 의미 위치를 서로 바꾸고 외곽 digest를 다시 계산하는 공격을 구분할 수 없음을 확인했다. 각 provenance에 흐름·유형·당사자와 네 digest 및 version을 결속한 binding digest를 추가하고, 반대 방향 binding으로 comparison과 queue route를 재계산하도록 보완했다. 또한 source validator가 누적 역할 계보에서 빠질 가능성을 차단하기 위해 reviewer·compiler·chair와 함께 anchor·최종 packet에 직접 투영하고 전체 역할분리를 검사한다.

## 금지 능력 확인

실제 외부 답변 수신·수락·조정·추천·동의·결정·승인·활성화·배포·문서 전송·전자서명·외부 PG/API·카드망·금융처리·원장·자격증명·운영 Prompt/정책/가중치 변경 능력은 포함하지 않는다.

## 검증 결과

- 전용 테스트: 36 PASS
- 전체 회귀 테스트: 1,415 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `412458ac94935eb8b61f240ac802ee4186a14d6632a1ded5329fcdbce53f0c1e`

> 에테르니언 독립 감사에서 비교 결과가 실제 provenance 차이가 아니라 답변 종류 라벨로 결정되는 미비점이 발견되었다. 아래 수치는 아르카온 1차 결과이며, 최종 결과는 `NURION_PG_7901_8300_ETHERNian_AUDIT.md`를 따른다.
