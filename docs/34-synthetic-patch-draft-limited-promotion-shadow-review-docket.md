# 기능 #034 — 합성 Patch Draft 제한승격 Shadow 재심사대장

기능 #033의 Shadow 평가 원문과 에테르니언 독립 재심사를 합성 SQLite에 영속
고정한다. 안전 통과와 rollback 필요 결과를 모두 보존하되 서로 다른 후속 상태로
분리하여 rollback 필요 결과가 운영자 재확인 경로로 진입하지 못하게 한다.

## 상태 분리

- `PENDING_ETERNIAN_REVIEW`
- 안전 통과 + 재심사 `PASS` →
  `READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION`
- rollback 필요 + 재심사 `PASS` → `ROLLBACK_REQUIRED_CONFIRMED`
- 재심사 `HOLD` → `HELD`
- 재심사 `REJECT` → `REJECTED`

운영자 재확인 준비 상태는 실제 재확인·승인·활성화가 아니다. 확인된 rollback
필요 상태도 실제 운영 rollback을 실행하지 않는다.

## 실패 폐쇄

- 평가 사슬, 관찰 결과 다이제스트와 전체 평가 다이제스트를 제출 전에 검증한다.
- 평가 원문 JSON과 계획·심사 다이제스트를 함께 보존한다.
- 제출·재심사 감사행을 단일 트랜잭션의 append-only SHA-256 사슬로 기록한다.
- 정확 재전송만 멱등 처리하고 상충하는 두 번째 재심사를 차단한다.
- 재시작 후 메타데이터·원문·저장행·감사행 결합을 모두 재검증한다.
- 안전 결과와 rollback 결과의 조회 경로를 별도로 제공한다.

## 권한 경계

최대 상태는 `READY_FOR_PATCH_DRAFT_LIMITED_PROMOTION_OPERATOR_RECONFIRMATION`이다.
자동심사·운영자 재확인 기록·후보 내용·패치·diff·파일 변경·자동 적용·명령
실행·합성 활성화·실제 rollback·결제·송금·병합·배포·운영 활성화 메서드는 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_draft_limited_promotion_shadow_review_docket -v
PYTHONPATH=src python scripts/run_synthetic_patch_draft_limited_promotion_shadow_review_evidence.py
```

CI 성공과 재심사 `PASS`는 실제 운영자 승인이나 제한승격이 아니다.
