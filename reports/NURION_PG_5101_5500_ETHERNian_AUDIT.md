# NURION PG #5101~#5500 에테르니언 독립 감사

## 감사 결과

아르카온 산출물을 독립 재검증하여 재해시 의미 변조 경로 세 가지를 발견하고 직접 보완했다.

1. registry key와 control object ID를 직접 대조하지 않아 두 통제 객체의 슬롯 교환이 가능했다.
2. 당사자 label과 capability profile digest 사이의 파생 결속이 없어 profile digest 교환 후 outer digest 재계산 경로가 있었다.
3. review item 생성이 공통 capability의 부분집합도 받아들여 생성 시점과 사후 무결성 규칙이 불일치했다.

## 보완

- key↔control ID 정확 일치 검증
- party↔profile↔operation↔token class binding digest 도입 및 재계산
- review item의 exact common capability 입력 강제
- workstream/control aspect 전체 구조 재구성 검증
- 세 공격 경로의 전용 부정 테스트 추가
- `ETH-5101-AUDIT-001` 및 `ARL-5101-001` 등록으로 다음 단계 아르카온에 즉시 강제 적용

## 안전경계

보완은 합성·메모리 전용 검증기, 테스트, 증적 계보에 한정했다. 실제 승인·활성화·배포·문서전송·전자서명·외부 PG/API·카드망·결제·취소·환불·정산·송금·원장 반영·운영 자격증명 사용·Prompt/정책/가중치 변경 능력은 추가하지 않았다.

## 최종 재검증

- 전용 테스트: 35 PASS
- 전체 회귀 테스트: 1153 PASS
- `compileall`: PASS
- `git diff --check`: PASS
- evidence 2회 결정론 검증: PASS
- evidence SHA-256: `9652bf0cb96b9473b1ac579cad8f44a897dce273ad93a540a8c609523ce1ed92`
