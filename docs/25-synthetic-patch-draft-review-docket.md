# 합성 패치 초안 에테르니언 검토대장

## 목적

기능 #024의 메타데이터 전용 패치 초안 Manifest 원문과 독립 심사결과를
재시작 가능한 SQLite 대장에 고정한다. 심사는 `PASS`, `HOLD`, `REJECT`만
기록하며 실제 패치 생성·적용이나 운영승격을 허가하지 않는다.

## 상태기계

`PENDING_ETERNIAN_REVIEW`에서 한 번만 다음 상태로 전이한다.

- `PASS` → `READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW`
- `HOLD` → `HELD`
- `REJECT` → `REJECTED`

`PASS`는 별도 합성 Patch Draft Shadow의 입력 준비 상태일 뿐 코드 작성·적용
허가가 아니다. `HOLD`와 `REJECT`는 Shadow 원천으로 사용할 수 없다.

## 실패 폐쇄

- 타입이 보장되고 사슬이 무결한 Manifest Book만 접수한다.
- Manifest 원문 JSON과 다이제스트·수신증·패킷 결합을 저장한다.
- 제출·심사 시각은 앞 단계보다 빠를 수 없고 timezone을 포함해야 한다.
- 심사자와 심사 ID에 합성 에테르니언 namespace를 강제한다.
- 제출과 심사는 각각 정확한 재전송만 멱등 처리한다.
- 저장행과 append-only 감사행은 동일 트랜잭션으로 기록한다.
- 재시작 후 메타데이터·원문·심사·감사 사슬을 전부 재검증한다.
- 저장행 또는 감사행 위변조가 발견되면 Shadow 원천 제공을 차단한다.

## 권한 경계

최대 상태는 `READY_FOR_SYNTHETIC_PATCH_DRAFT_SHADOW`다. 패치·diff·경로 원문,
소스 및 파일시스템 변경, 자동 적용, 안전기준 완화, 실행, 네트워크·운영 키·
개인정보 사용, 결제·자금이동, 병합·배포·운영승격 메서드는 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_draft_review_docket -v
PYTHONPATH=src python scripts/run_synthetic_patch_draft_review_docket_evidence.py
```

CI 통과와 에테르니언 `PASS`는 실제 패치 또는 운영 승인으로 해석하지 않는다.
