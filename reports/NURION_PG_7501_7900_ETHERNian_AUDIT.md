# NURION PG #7501~#7900 에테르니언 독립 감사

## 발견 및 보완

semantic claim과 material manifest가 answer 및 receipt에 포함됐지만, 두 digest 자체는 임의의 64자리 값으로 수용됐다. 공격자가 claim부터 receipt까지 연쇄 재계산하면 구조 검사를 통과할 수 있었다.

- semantic claim을 질문·당사자·원본 문서·route에서 파생
- material manifest를 질문·당사자·claim·route·문서 버전에서 파생
- answer와 receipt를 파생 claim/manifest로 다시 계산
- claim→manifest→answer→receipt 전체 연쇄 재해시 공격 테스트 추가
- `ETH-7501-AUDIT-001` / `ARL-7501-001`로 아르카온 학습 게이트에 즉시 반영

## 안전경계

합성·메모리 전용 검증 구조만 변경했다. 실제 외부 답변 접수·수락·전송·서명·추천·결정·승인·활성화·배포·외부 PG/API·금융처리·원장·자격증명·Prompt/정책/가중치 변경 능력은 없다.

## 최종 재검증

- 전용 테스트: 42 PASS
- 전체 회귀 테스트: 1379 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `541f99add6a522015c611dc87598b9f2fde3b21f2e2bc7bbacb93e331ceb3344`
