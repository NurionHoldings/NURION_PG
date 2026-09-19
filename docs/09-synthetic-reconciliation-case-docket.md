# 합성 정합성 사건 검토대장

기능 #009는 기능 #008의 읽기 전용 정합성 보고서 중 `HUMAN_REVIEW` 또는
`BLOCKED` 결과만 영속 사건으로 접수한다. `PASS` 보고서는 사건을 만들 이유가
없으므로 접수하지 않는다.

## 상태와 역할 분리

```text
PENDING_ETERNIAN_REVIEW
  ├─ CONFIRM → READY_FOR_REMEDIATION_PROPOSAL
  ├─ HOLD    → HELD
  └─ REJECT  → REJECTED
```

ARKAON 감시기는 보고서를 제출할 수 있지만 심사할 수 없다. 에테르니언의
`CONFIRM`도 수정 승인이나 수정 실행이 아니라, 별도의 보완안 설계를 검토할 수
있다는 뜻이다. 이 기능에는 보완안 생성·코드수정·운영자결정·결제실행 메서드가
없다.

## 무결성 통제

- source report 전체 canonical SHA-256 및 component snapshot digest 재검증
- finding 수·심각도·report status 연결 검증
- 자동수정·결제상태변경·자금이동·운영승격 금지 플래그 검증
- case/report/review 고유 식별자와 exact replay 멱등성
- SQLite `BEGIN IMMEDIATE` 기반 submission/review 원자성
- actor·상태·근거·기록시각을 포함한 append-only SHA-256 audit 사슬
- 저장 report·review·audit binding 및 재시작 복구 검증
- 동시 review 중 하나의 상태전이만 허용

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_reconciliation_case_docket -v
PYTHONPATH=src python scripts/run_reconciliation_case_docket_evidence.py
```

모든 자료는 합성 식별자만 사용하며 실제 공급자, 운영 DB, 자격증명,
개인정보, 결제수단 또는 네트워크와 연결하지 않는다.
