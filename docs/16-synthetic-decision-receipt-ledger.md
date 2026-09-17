# 합성 결정 의사 수신대장

## 목적

`SYNTHETIC_DECISION_VALIDATED` 상태의 합성 운영자 결정 의사 검증 결과를
재시작 가능한 SQLite 증거로 보관한다. 이 수신대장은 실제 최인석 운영자의
결정을 기록하거나, 판단 패킷·코드·결제·운영 상태를 변경하지 않는다.

## 저장 계약

- 합성 평가 ID·다이제스트와 봉투 ID·다이제스트
- 운영자 판단 패킷 ID·다이제스트
- 합성 운영자 ID와 합성 결정값
- 원본 평가 JSON과 기록시각
- 이전 감사 다이제스트에 연결된 append-only SHA-256 감사행

DB 파일명은 `synthetic-` 접두어와 `.db`, `.sqlite`, `.sqlite3` 확장자만
허용한다. 서버·URI DB와 실제 운영 저장소 연결은 거부한다.

## 실패 폐쇄

- 평가 사슬과 평가 다이제스트가 일치하지 않으면 기록하지 않는다.
- 평가보다 이른 시각과 timezone 없는 시각을 거부한다.
- 평가·봉투·패킷의 ID 및 다이제스트 결합을 재검증한다.
- 동일 증거의 재전송은 한 건으로 멱등 처리한다.
- 중복 패킷, 식별자 충돌, 감사행 실패는 전체 트랜잭션을 rollback한다.
- 재시작 후에도 레코드 결합과 감사 사슬을 다시 검증한다.
- 합성 전용 스키마 버전·메타데이터가 삭제되거나 달라지면 처리를 차단한다.
- 저장행 또는 감사행 위변조가 발견되면 이후 처리를 차단한다.

## 권한 경계

최대 상태는 `SYNTHETIC_RECEIPT_RECORDED`다. 이는 합성 검증 결과의 영속
수신증일 뿐 실제 승인·보류·거절이 아니다. 운영자 결정 기록, 패킷 상태 변경,
코드 변경, 자동 적용, 결제 실행, 자금 이동, 병합·배포·운영승격 메서드는 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_operator_decision_receipt_ledger -v
PYTHONPATH=src python scripts/run_operator_decision_receipt_ledger_evidence.py
```

CI 통과는 실제 운영자 승인, 계약 효력, 코드 변경 또는 운영승격을 뜻하지 않는다.
