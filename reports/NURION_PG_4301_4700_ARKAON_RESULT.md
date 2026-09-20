# NURION PG #4301~#4700 구현·독립 감사 결과

## 범위와 주제

- 범위: #4301~#4700, 누락·중복 없는 정확히 400개
- 구조: 16개 workstream × 25개 통제 관점
- 주제: 입주사/대행업체↔NURION PG↔본 PG사 합성 연동 패키지 조립·모의 인수 검증
- 최대 상태: `ACCEPTANCE_REVIEWED_NOT_RELEASED`

## 구현

- 직전 source bundle·협상 round·400-case set·독립 review receipt digest 결속
- 7개 비실행 artifact 유형 × 4개 전자문서 흐름 = 정확히 28개 산출물
- tenant/upstream 식별자와 4개 route binding의 content-addressed manifest
- 정확히 400개 합성 mock acceptance case
- maker-checker가 분리된 비승인 acceptance receipt
- append-only event·hold chain, 멱등·동시성·부분 패키지 fail-closed

## 아르카온 자가진단·보완

초기 구현은 artifact party가 유효 역할인지만 검사해 흐름 송신 주체와의 불일치를 차단하지 못했다. 4방향별 고정 owner를 도입하고 생성·무결성 검증 양쪽에서 강제했으며, 다른 당사자가 흐름을 소유하려는 우회 테스트를 추가했다.

## 1차 검증

- 전용·재발방지 테스트: 44 PASS
- 전체 회귀: 1079 PASS
- `compileall`: PASS
- evidence 2회 byte-for-byte 결정론 검증: PASS
- evidence SHA-256: `db8cd88204f43969310f6603173712f2afa18e9931b15290dee4fc505e287157`
- `git diff --check`: PASS

## 에테르니언 독립 감사·보완

- assembler identity를 manifest digest에 결속해 maker identity 동시 재해시 공격을 차단
- tenant/upstream/flow 기반 route digest를 무결성 검사에서 재계산
- manifest의 package/tenant/upstream/assembler namespace를 사후 재검증
- acceptance receipt의 `accepted_for_review=true`를 강제
- route substitution, assembler substitution, review-state 의미 변조 공격 테스트 3개 추가
- CI 보완: 로컬 전용 commit SHA와 git history 의존을 제거하고 stable remediation manifest↔lesson 1:1 검증으로 전환. 실제 부정 테스트 이름의 저장소 존재 여부까지 확인

## 재발방지 학습 게이트

- versioned lesson registry v1에 직전·이번 에테르니언 보완 lesson 3개 등록
- 기준 commit 이후 `fix:` 보완 커밋과 lesson remediation reference 자동 대조
- lesson entry, ARKAON acknowledgement, 필수 부정 테스트, PASS 재검증 증적 누락 시 fail-closed
- evidence 생성 전에 registry를 검증하고 version·digest·적용 lesson ID를 evidence에 기록
- 운영 Prompt·가중치·운영 정책 자동 변경 없음

## 안전경계

외부 호출, 문서 전송, 전자서명, 실행 adapter, 본 PG API, 카드망, 결제·승인·취소·환불·정산·송금, 실제 원장, 운영 자격증명, 배포, 운영 정책·Prompt·가중치 변경은 모두 0이며 release는 기록되지 않는다.
