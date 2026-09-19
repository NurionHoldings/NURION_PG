# NURION PG #5501~#5900 아르카온 구현·1차 검증 결과

## 결과

- 주제: 합성 검토 이의제기·재검토 계보
- 통제: 16개 작업군 × 25개 aspect = 정확히 400개
- 범위: #5501~#5900 연속, 누락·중복 없음
- challenge: 4방향 × 5개 근거 = 20개
- open challenge hold: 정확히 20개
- 최대 상태: `RECONSIDERATION_DOCKET_READY_NOT_DECIDED_NOT_ACTIVATED`

## 학습 선적용

`ARL-3901-001`부터 `ARL-5101-001`까지 전체 lesson과 `ARP-01~08`을 source anchor에 결속했다. stable remediation manifest와 명명된 부정 테스트를 evidence 전에 검증한다.

## 아르카온 자가진단과 즉시 보완

초기 설계에서 각 challenge가 hold를 생성하는 것만으로 충분하다고 볼 위험을 발견했다. challenge 하나 또는 hold 하나가 제거된 부분 자료도 반드시 실패하도록 전체 20개 challenge key 집합과 기대 hold 목록을 도메인 상태에서 재구성했다. `test_missing_challenge_fails_closed`, `test_missing_hold_fails_closed`로 고정했다.

또한 control slot 교환, 당사자 문서 교환, route 치환, challenge key 교환, 상태·결정 boolean·source reviewer 변조 후 digest 재계산을 부정 테스트로 검증했다.

## 검증

- 전용 테스트: 33 PASS
- 전체 회귀 테스트: 1186 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `e1bdf0510fabab4cddfdbabad94ec0c8df2b53eb876ba219124e002f41166dd8`

## 안전경계

모든 구현은 합성·메모리 전용이다. 실제 전송·전자서명·외부 PG/API·카드망·금융처리·원장·자격증명·배포·활성화·결정·운영 Prompt/정책/가중치 변경 능력은 없다.
