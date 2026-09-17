# 기능 #033 — 합성 Patch Draft 제한승격 Shadow 평가

기능 #032에서 에테르니언 심사를 통과한 제한승격 계획을 실제로 활성화하지 않고,
미리 계산된 합성 관찰값으로만 Shadow 평가한다. 평가 결과는 재심사 후보 또는
rollback 필요 판정이며 자동 적용이나 실제 제한승격으로 이어지지 않는다.

## 평가 계약

- 계획의 합성 평가군 크기와 정확히 같은 수의 관찰값을 요구한다.
- 관찰 순번·ID·SHA-256은 중복 없이 고정한다.
- 모든 관찰값을 계획·후보·평가군 다이제스트와 결합한다.
- 안전 불변식, 증거 사슬, 합성 회귀, 예상하지 못한 부작용을 평가한다.
- 네 조건 중 하나라도 위반되면 해당 관찰과 전체 평가를
  `ROLLBACK_REQUIRED`로 판정한다.
- 전 항목 통과도 최대 `PROPOSED_FOR_ETERNIAN_REVIEW`까지만 허용한다.

## 실패 폐쇄

- `HOLD` 또는 `REJECT`된 계획은 Shadow 입력이 될 수 없다.
- 계획 심사대장의 메타데이터·감사 사슬·저장 결합을 먼저 검증한다.
- 계획보다 적거나 많은 관찰값, 순서 변경, 중복 및 다이제스트 불일치를 거부한다.
- timezone 없는 시각과 심사보다 이른 평가 시각을 거부한다.
- 정확 재전송만 멱등 처리하고 관찰값 변경은 충돌로 차단한다.
- 평가 SHA-256 사슬과 심사대장 전후 다이제스트를 고정한다.

## 권한 경계

이 계층은 후보 내용·패치·diff를 보유하지 않으며 코드·파일 변경, 자동 적용,
명령 실행, 합성 활성화, 네트워크, 자격증명, 개인정보, 실제 결제·송금, 병합·
배포·운영승격 메서드가 없다. `ROLLBACK_REQUIRED`는 안전한 합성 판정이며 실제
운영 rollback을 실행하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_draft_limited_promotion_shadow -v
PYTHONPATH=src python scripts/run_synthetic_patch_draft_limited_promotion_shadow_evidence.py
```

CI 성공과 Shadow 통과는 합성 또는 운영 활성화 승인이 아니다.
