# 합성 패치 결정 의사 수신대장

## 목적

`SYNTHETIC_PATCH_DECISION_VALIDATED` 평가 결과를 재시작 가능한 SQLite 증거로
보존한다. 이 대장은 실제 최인석 운영자의 결정을 기록하거나 패치 내용·코드·
운영 상태를 생성 또는 변경하지 않는다.

## 저장 계약

- 합성 평가·봉투·nonce·패킷의 ID 및 SHA-256 다이제스트
- 합성 운영자 ID와 합성 결정값
- 원본 평가 JSON과 timezone 포함 기록시각
- 이전 감사 다이제스트에 연결된 append-only 감사행

파일 DB는 `synthetic-` 접두어와 `.db`, `.sqlite`, `.sqlite3` 확장자만 허용한다.
서버 DB·URI·운영 저장소는 거부한다.

## 실패 폐쇄

- 평가 사슬, 평가 다이제스트 또는 합성 전용 메타데이터가 깨지면 기록하지 않는다.
- 평가보다 이른 시각과 timezone 없는 시각을 거부한다.
- 평가·봉투·nonce·패킷 결합을 저장행마다 다시 검증한다.
- 동일 증거의 재전송은 한 건으로 멱등 처리한다.
- 하나의 패킷에서 복수 수신증 생성을 차단한다.
- 저장행과 감사행은 한 트랜잭션으로 기록하고 실패 시 rollback한다.
- 재시작 후에도 저장 결합과 감사 사슬을 재검증한다.
- 저장행·감사행 위변조가 발견되면 이후 기록을 차단한다.

## 권한 경계

최대 상태는 `SYNTHETIC_PATCH_DECISION_RECEIPT_RECORDED`다. 이는 합성 검증
결과의 수신증일 뿐 실제 승인·보류·거절이나 패치 작성 허가가 아니다. 실제 결정
기록, 패킷 변경, 패치 내용 생성, 코드 변경·적용, 안전기준 완화, 결제·자금이동,
네트워크 접근, 병합·배포·운영승격 메서드는 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_patch_operator_decision_receipt_ledger -v
PYTHONPATH=src python scripts/run_patch_operator_decision_receipt_ledger_evidence.py
```

CI 통과는 실제 운영자 승인, 패치 작성·적용, 병합 또는 배포 승인을 뜻하지 않는다.
