# NURION PG #5901~#6300 아르카온 구현·1차 검증 결과

## 결과

- 주제: 합성 증거 공개·반박·정정 준비도
- 통제: 16개 작업군 × 25개 aspect = 정확히 400개
- 범위: #5901~#6300 연속, 누락·중복 없음
- correction case: 4방향 × 5개 주제 = 20개
- operator review hold: 정확히 20개
- 최대 상태: `CORRECTION_READINESS_PACKET_READY_NOT_PUBLISHED_NOT_DECIDED`

## 학습 선적용

`ARL-3901-001`부터 `ARL-5501-001`까지 전체 lesson과 `ARP-01~08`을 source anchor에 결속했다. stable remediation manifest와 명명된 부정 테스트를 evidence 전에 검증한다.

## 아르카온 자가진단과 즉시 보완

초기 구현에서 source reviewer 문자열이 손상된 경우 단순한 fail-closed 거부가 아니라 문자열 분해 예외가 발생할 수 있음을 발견했다. 안전한 namespace predicate로 교체하고 `test_malformed_source_reviewer_fails_closed`를 추가했다.

또한 case 하나 또는 hold 하나가 삭제된 부분 배치, control/case key 교환, 당사자 원문 교환, disclosure·rebuttal·correction draft·당사자·상태·event artifact·packet publication boolean을 바꾸고 digest를 다시 계산하는 공격을 전용 부정 테스트로 고정했다.

## 검증

- 전용 테스트: 34 PASS
- 전체 회귀 테스트: 1222 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `1cfae7e9dfa251a308db1fce0ce8b6cd85fd6f39f5bc56c03c6af14c1b25c0ff`

## 안전경계

모든 구현은 합성·메모리 전용이다. 실제 공개·전송·전자서명·외부 PG/API·카드망·금융처리·원장·자격증명·배포·활성화·결정·운영 Prompt/정책/가중치 변경 능력은 없다.
