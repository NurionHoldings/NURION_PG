# 합성 인간 심의 질문 도켓 (#7101~#7500)

## 목적

직전 비구속적 대안 시뮬레이션을 자동 추천이나 결정으로 연결하지 않고, 운영자가 직접 확인해야 하는 가정·잔여위험·추가자료·미해결 의미·안전경계 질문을 구성한다. 입주사, NURION PG, 본 PG의 전자문서 digest와 네 방향 연동 흐름을 합성 데이터로만 검증한다.

## 통제 구조

- 16개 작업군 × 25개 공통 통제 관점 = 정확히 400개(`#7101`~`#7500`).
- 네 방향 흐름 × 다섯 질문 종류 = 20개 질문과 20개 human hold.
- 전체 source reviewer 3명, source compiler 3명, 모든 질문 drafter와 human reviewer, 최종 chair의 역할을 빠짐없이 분리한다.
- 문서, 경로, 질문, 가정, 잔여위험, 추가자료 요구와 source lineage를 digest로 의미 결속한다.
- event와 hold는 append-only chain이며 누락·교환·재해시·부분 배치는 fail-closed 된다.

## 안전경계

최대 상태는 `HUMAN_DELIBERATION_QUESTION_DOCKET_READY_NOT_ANSWERED_NOT_DECIDED`이다. 질문 작성은 답변·추천·동의·결정·승인·활성화가 아니다. 문서 전송, 전자서명, 외부 PG/API, 카드망, 결제·취소·환불·정산·송금, 원장, 운영 자격증명, 배포, 운영 Prompt·정책·가중치 변경 능력을 포함하지 않는다.
