# NURION PG #5101~#5500 아르카온 구현·1차 검증 결과

## 결과

- 주제: 합성 운영자 검토 도켓·비활성화 사전검증 결정 패킷
- 통제: 16개 작업군 × 25개 aspect = 정확히 400개
- 범위: #5101~#5500 연속, 누락·중복 없음
- 검토 항목: 4방향 × 6시나리오 = 24개
- partial batch hold: 정확히 4개
- 최대 상태: `OPERATOR_REVIEW_DOCKET_READY_NOT_APPROVED_NOT_ACTIVATED`

## 학습 선적용

- stable remediation manifest와 lesson registry를 evidence 전에 검증
- 적용 lesson: `ARL-3901-001`, `ARL-4301-001`, `ARL-4301-002`, `ARL-4301-003`, `ARL-4701-001`
- 적용 지도사항: `ARP-01~08`
- evidence에 registry·manifest·guidance digest 및 적용 ID 기록

## 아르카온 자가진단과 즉시 보완

초기 구현은 각 hold의 형식과 partial-batch artifact 포함 여부는 검사했으나, 한 hold가 삭제된 경우 나머지 hold가 모두 유효하면 통과할 여지가 있었다. 이를 발견하여 도메인 상태에서 기대되는 네 개의 `reason↔artifact` 목록을 순서까지 재구성하도록 보완했고 `test_missing_hold_fails_closed`를 추가했다.

그 밖에 다음 공격을 전용 부정 테스트로 검증했다.

- source digest·lesson·rule·capability profile 변경 후 outer digest 재계산
- route/capability digest 치환 후 재계산
- 실제 namespace로 위장
- approval/status/source-reviewer 변경 후 receipt 재계산
- event artifact 및 hold attachment 치환 후 chain 재계산
- maker-checker 동일 identity와 최신 source 위반

## 검증

- 전용 테스트: 32 PASS
- 전체 회귀 테스트: 1150 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `464a6eca500763dc4149873d827ea1fa4a00b697894bb6ef51f64413f4e2ef18`

## 안전경계

실제 문서 전송·전자서명·외부 PG/API·카드망·결제·승인·취소·환불·정산·송금·원장·자격증명·배포·활성화·운영 Prompt/정책/가중치 변경 능력은 구현하지 않았다. 모든 결과는 합성·메모리 전용이며 외부 호출 수는 0이다.
