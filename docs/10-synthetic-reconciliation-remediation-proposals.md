# 합성 정합성 보완안 초안

기능 #010은 에테르니언이 `CONFIRM`하여
`READY_FOR_REMEDIATION_PROPOSAL`이 된 정합성 사건만 입력으로 받는다. ARKAON은
알려진 finding을 허용목록의 조사·계약검토·합성시험 항목으로 구조화하고,
에테르니언 검토용 보완안 초안을 만든다.

## 허용된 초안 유형

- `EVIDENCE_CHAIN_INVESTIGATION`
- `WORKFLOW_LINKAGE_REVIEW`
- `PAYMENT_LEDGER_RECONCILIATION`
- `STABLE_SNAPSHOT_REPRODUCTION`

각 항목의 범위는 `*_DRAFT_ONLY`, `*_ANALYSIS_ONLY` 또는
`SYNTHETIC_FIXTURE_DRAFT_ONLY`로 제한된다. 모든 항목은 실패 폐쇄 기준 유지,
회귀시험 유지·추가, SHA-256 증거 재생성, 에테르니언 심사를 요구한다.

알려지지 않은 finding은 임의 추론하지 않고 `HUMAN_REVIEW`로 전환한다.
ARKAON은 초안을 만들 수 있지만 코드·정책·시험을 변경하거나 원 사건을 닫을 수
없다. 초안은 자동 적용·운영자 승인·결제 실행·운영승격 권한을 가지지 않는다.

## 무결성

- confirmed case·source report·Eternian review digest 결속
- finding code·subject·action·scope·required check별 item digest
- 전체 proposal digest와 append-only assessment digest 사슬
- 동일 case의 동시 요청 및 exact replay 멱등성
- 초안 전후 source case evidence digest 비교
- plan item·assessment 변조 탐지

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_reconciliation_remediation_proposals -v
PYTHONPATH=src python scripts/run_reconciliation_remediation_proposal_evidence.py
```
