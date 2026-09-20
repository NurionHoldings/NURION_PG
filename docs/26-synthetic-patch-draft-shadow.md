# 합성 Patch Draft Shadow

## 목적

기능 #025에서 에테르니언 `PASS`를 받은 패치 초안 Manifest를 합성 fixture로
평가한다. 범위·대상 다이제스트 결합, 회귀·동시성·장애 통제와 증거 재현성을
검증하지만 코드·diff·파일·실행 가능한 패치는 만들지 않는다.

## 범위별 판정

- 모든 통제 통과 → `PASS`
- 통제 미완료 또는 대상과 후보 다이제스트 동일 → `HUMAN_REVIEW`
- 패치 내용·diff·파일 쓰기·네트워크·운영 접근·자격증명·개인정보·자금이동
  흔적 → `BLOCKED`

전체 결과는 `PROPOSED_FOR_ETERNIAN_REVIEW`, `HUMAN_REVIEW`, `BLOCKED` 중
하나이며 최대 자동판정은 `PROPOSED_FOR_ETERNIAN_REVIEW`다.

## 실패 폐쇄

- `READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW` 상태만 입력으로 허용한다.
- Manifest의 모든 범위에 정확히 하나의 fixture가 필요하다.
- Manifest ID·다이제스트·범위·대상 다이제스트를 정확히 결합한다.
- fixture와 결과·전체 평가의 SHA-256을 재계산한다.
- 동일 Manifest의 정확한 fixture 재전송만 멱등 처리한다.
- 평가 전후 원천 검토대장의 증거가 바뀌면 결과를 취소한다.
- 합성 평가 사슬이나 색인 위변조가 발견되면 이후 평가를 차단한다.

## 권한 경계

Shadow 결과는 에테르니언 재심사 후보일 뿐 패치 승인이나 실제 변경이 아니다.
패치·diff 생성, 소스·파일시스템 변경, 자동 적용, 안전기준 완화, 실행, 네트워크,
운영 키·개인정보 사용, 결제·자금이동, 병합·배포·운영승격 기능은 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_draft_shadow -v
PYTHONPATH=src python scripts/run_synthetic_patch_draft_shadow_evidence.py
```

CI 통과는 실제 패치 작성·적용 또는 운영승격을 뜻하지 않는다.
