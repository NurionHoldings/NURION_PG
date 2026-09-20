# NURION PG #5501~#5900 에테르니언 독립 감사

## 발견 및 보완

challenge의 문서 digest와 challenger가 형식적으로만 검증되어 다른 흐름의 문서 또는 발신 당사자로 교환한 뒤 외곽 digest를 재계산할 수 있었다. 이를 다음과 같이 보완했다.

- 4개 흐름별 발신 당사자 고정 mapping
- challenge document digest를 발신 당사자·anchor의 당사자 문서·flow·ground·route에서 재계산
- challenger를 흐름의 발신 당사자와 정확히 결속
- 문서 및 challenger 교환 후 재해시 공격 전용 테스트 추가
- `ETH-5501-AUDIT-001`과 `ARL-5501-001`로 아르카온 재발방지 학습에 즉시 반영

## 안전경계

합성·메모리 전용 검증 구조만 변경했다. 실제 결정·승인·활성화·배포·문서전송·전자서명·외부 PG/API·카드망·금융처리·원장·운영 자격증명·Prompt/정책/가중치 변경 능력은 없다.

## 최종 재검증

- 전용 테스트: 35 PASS
- 전체 회귀 테스트: 1188 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `971b7ce51ff8b24ff0a8ccf0d594ef34bdc89448129e17442e55abe100abbcca`
