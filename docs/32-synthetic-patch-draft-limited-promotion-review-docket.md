# 기능 #032 — 합성 Patch Draft 제한승격 계획 심사대장

기능 #031의 제한승격 계획 원문과 에테르니언 독립심사를 합성 SQLite에 영속
고정한다. 심사 통과의 최대 상태는 별도 합성 Shadow 평가 준비이며, 계획을
활성화하거나 실제 제한승격을 수행하지 않는다.

## 심사 상태

- `PENDING_ETERNIAN_REVIEW`
- `READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW`
- `HELD`
- `REJECTED`

에테르니언은 `PASS`, `HOLD`, `REJECT` 중 하나와 findings SHA-256을 기록한다.
`PASS`도 별도 Shadow의 입력 자격만 만들며 합성 또는 운영 활성화 권한은 없다.

## 실패 폐쇄

- 합성 계획 사슬과 계획 다이제스트를 제출 전에 다시 검증한다.
- 계획 원문 JSON, 원천 수신증·패킷 결합과 심사 결과를 함께 보존한다.
- 제출·심사 감사행은 이전 SHA-256에 연결하며 단일 트랜잭션으로 기록한다.
- 정확한 제출·심사 재전송만 멱등 처리하고 다른 두 번째 심사를 거부한다.
- timezone 없는 시각과 계획·제출보다 이른 시각을 거부한다.
- 재시작 후에도 메타데이터·저장행·감사 사슬의 결합을 재검증한다.
- 저장 계획이나 감사행 위변조 발견 시 Shadow 준비 조회를 차단한다.

## 권한 경계

최대 상태는 `READY_FOR_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_SHADOW`다.
자동심사·운영자 결정 기록·후보 내용·패치·diff·파일 변경·자동 적용·실행·
합성 활성화·실제 결제·송금·병합·배포·운영 활성화 메서드는 없다. 비합성
사용에는 최인석 운영자의 별도 재확인이 계속 필요하다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_draft_limited_promotion_review_docket -v
PYTHONPATH=src python scripts/run_synthetic_patch_draft_limited_promotion_review_evidence.py
```

CI 통과와 심사 `PASS`는 합성 활성화나 실제 제한승격 승인이 아니다.
