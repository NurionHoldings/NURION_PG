# 합성 구현제안 초안

## 목적

합성 결정 의사 수신대장에서
`AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT`로 검증된 수신증만 받아
ARKAON이 사람 검토용 구현제안 골격을 작성한다. 실제 최인석 운영자의 결정을
기록하거나 코드·결제·운영환경에 변경을 적용하지 않는다.

## 허용 초안 범위

- `SYNTHETIC_FIXTURE_PATCH_DRAFT_ONLY`
- `TEST_HARDENING_PATCH_DRAFT_ONLY`
- `POLICY_CLARIFICATION_PATCH_DRAFT_ONLY`
- `DOCUMENTATION_PATCH_DRAFT_ONLY`

범위는 비어 있을 수 없으며, 중복·미등록 값·순서 변경을 거부한다. 초안에는
실행 명령, 운영 자격증명, 개인정보, 결제수단 또는 자금이동 지시를 넣지 않는다.

## 필수 통제

- 원래 실패 폐쇄 기준 유지
- 원천 SHA-256 증거 재현
- 합성 회귀시험 수행
- 필요한 경우 동시성·장애시험 수행
- 모든 변경 전 에테르니언 심사
- 제한 승격 전 운영자 승인

`HOLD`와 `REJECT` 수신증은 초안을 만들 수 없다. 원천 수신대장의 메타데이터,
감사 사슬, 레코드 결합이 하나라도 깨지면 실패 폐쇄한다. 정확한 재전송은 멱등
처리하고 동일 수신증의 범위 변경은 충돌로 차단한다.

## 권한 경계

최대 상태는 `SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFTED`다. 이 상태는 코드
변경 허가가 아니다. 실제 운영자 결정 기록, 코드 작성·적용, 시험 완화, 결제,
자금이동, 병합, 배포, 운영승격 메서드는 제공하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_implementation_proposals -v
PYTHONPATH=src python scripts/run_synthetic_implementation_proposal_evidence.py
```

CI 통과는 실제 운영자 승인이나 변경 실행 권한을 뜻하지 않는다.
