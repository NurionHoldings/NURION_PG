# NURION PG #4701~#5100 아르카온 결과

## 주제

합성 입주사–본 PG 연동 온보딩 리허설·준비도 인계 도켓. #4301~#4700에서 모의 인수된 전자문서·adapter 패키지를 실제 연결 전에 4방향×6개 시나리오로 리허설하고 독립 검토 receipt까지 연결한다.

## 구현

- 16개 작업군×25개 aspect = 정확히 400개 통제
- accepted package manifest와 acceptance receipt를 source anchor에 직접 결속
- registry digest, 적용 lesson ID, 세 당사자 capability profile 결속
- route와 common-capability digest의 canonical 재계산
- 24개 비실행 계획과 24개 메모리 전용 결과
- source-derived assembler와 독립 reviewer
- append-only event/hold chain 및 event↔artifact 재구성
- 부분 계획, stale source, capability 이탈, 역할 충돌, 재해시 변조 fail-closed

## 아르카온 자가진단 및 즉시 보완

초기 테스트에서 anchor 멱등 재호출이 값은 같지만 기존 객체가 아닌 새 객체를 반환하는 불일치를 발견했다. 저장된 권위 객체를 반환하도록 수정하고 멱등 테스트로 고정했다. 또한 Git history 형태에 의존하는 lesson 탐지는 shallow/squashed CI에서 불안정하므로 신규 evidence는 registry와 안정적인 재발방지 manifest 자체를 검증하고 두 digest를 기록한다.

## 안전경계

실제 문서 전송·전자서명·외부 API·카드망·결제·승인·취소·환불·정산·송금·원장·운영 자격증명·배포·운영 Prompt/정책/가중치 변경 능력은 없다. 최대 상태는 `READY_FOR_OPERATOR_REVIEW_NOT_ACTIVATED`이다.

## 최종 검증

- 전용 테스트: 37 PASS
- 전체 회귀: 1118 PASS
- evidence 2회 결정론 일치
- evidence SHA-256: `2443437a960f5ad36c6b3f5b96657b64f264914189bc48dd103ae5e7dba94c7f`
- `compileall`: PASS
- `git diff --check`: PASS
# 에테르니언 독립 감사 보완

- 세 당사자 capability profile 명세를 anchor에 직접 결속하고 operation·token-class 교집합 재계산
- anchor·plan·result·receipt ID와 digest namespace 사후 재검증
- capability 교집합 위장 및 result namespace 재해시 공격 테스트 추가
- 보완 내용을 `ETH-4701-AUDIT-001` / `ARL-4701-001`로 즉시 학습 환류
