# 기능 #031 — 합성 Patch Draft 제한승격 계획

기능 #030의 `AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION` 합성 수신증에서
ARKAON이 사람 검토용 제한승격 계획 메타데이터만 작성한다. 계획은 실제 패치,
배포 또는 운영 승격을 수행하지 않는다.

## 계획 계약

- 범위는 `SYNTHETIC_FIXTURE_COHORT_ONLY`로 고정한다.
- 후보와 합성 평가군은 원문 대신 서로 다른 SHA-256 다이제스트로만 결합한다.
- 합성 평가군은 1~100개, 관찰창은 60~3,600초의 60초 단위로 제한한다.
- 안전 불변식, 증거 사슬, 합성 회귀 또는 예상하지 못한 부작용 중 하나라도
  실패하면 rollback 대상으로 판정하도록 네 가지 트리거를 빠짐없이 고정한다.
- 에테르니언 심사 전에는 합성 활성화도 허용하지 않으며, 비합성 사용에는
  최인석 운영자의 재확인이 별도로 필요하다.

## 실패 폐쇄

- `HOLD`와 `REJECT` 수신증은 계획을 만들 수 없다.
- 원천 수신대장의 메타데이터·감사 사슬·레코드 결합을 모두 검증한다.
- 계획 시각은 수신증보다 빠를 수 없고 timezone을 포함해야 한다.
- 같은 수신증의 정확한 재전송만 멱등 처리한다.
- 후보·평가군 다이제스트, 한도 또는 rollback 트리거 변경은 충돌로 차단한다.
- append-only SHA-256 계획 사슬과 원천 수신증의 전후 다이제스트를 검증한다.

## 권한 경계

최대 상태는 `SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION_PLAN_DRAFTED`다. 코드·패치·
diff·파일을 계획에 넣지 않으며 적용, 실행, 네트워크, 개인정보, 자격증명, 실제
결제·송금, 병합·배포 또는 운영 활성화 메서드를 제공하지 않는다. 이 계획은
실제 운영자 승인이나 제한승격이 아니다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_draft_limited_promotion_plans -v
PYTHONPATH=src python scripts/run_synthetic_patch_draft_limited_promotion_plan_evidence.py
```

CI 통과는 합성 활성화나 운영 승격을 승인하지 않는다.
