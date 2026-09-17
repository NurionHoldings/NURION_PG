# 합성 구현제안 영속 심사대장

## 목적

ARKAON이 만든 `SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFTED` 초안을 SQLite
심사대장에 격리하고 에테르니언의 독립심사를 영속 증거로 남긴다. 심사를
통과해도 합성 패치 Shadow 준비 상태까지만 도달하며 코드 변경 권한은 생기지
않는다.

## 상태

- `PENDING_ETERNIAN_REVIEW`
- `READY_FOR_SYNTHETIC_PATCH_SHADOW`
- `HELD`
- `REJECTED`

결정은 `PASS`, `HOLD`, `REJECT`만 허용한다. `PASS`는
`READY_FOR_SYNTHETIC_PATCH_SHADOW`로만 전환한다. `HOLD`와 `REJECT`는
Shadow 원천으로 사용할 수 없다.

## 무결성·복구 통제

- typed 구현제안 Book과 제안 사슬 검증
- 제안 ID·다이제스트·수신증·패킷 결합 재검증
- 합성 전용 SQLite 파일명과 스키마 메타데이터 강제
- 제출·심사 SHA-256 감사 사슬
- 제출·심사 멱등성 및 충돌 차단
- 감사 기록 실패 시 전체 트랜잭션 rollback
- 재시작 후 제안·심사·감사 결합 재검증
- 저장 JSON·심사값·감사행·메타데이터 위변조 실패 폐쇄

## 권한 경계

최대 상태는 `READY_FOR_SYNTHETIC_PATCH_SHADOW`다. 실제 운영자 결정 기록,
코드 작성·적용, 시험 완화, 결제, 자금이동, 병합, 배포, 운영승격 메서드는
제공하지 않는다. 심사 결과도 실제 운영 승인이나 법적 승인이 아니다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_implementation_review_docket -v
PYTHONPATH=src python scripts/run_synthetic_implementation_review_evidence.py
```
