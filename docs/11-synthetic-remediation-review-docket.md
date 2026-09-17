# 합성 보완안 영속 검토대장

## 목적

기능 #010이 만든 실행 불가능한 보완안 초안을 SQLite 검토대장에 고정하고,
ARKAON 제안자와 분리된 에테르니언 심사 결과를 영속 기록한다. 이 기능은
보완안 실행이나 코드 수정 기능이 아니다.

## 입력과 무결성

- 입력은 `SyntheticRemediationProposalBook`의 정확히 한 건인
  `PROPOSED_FOR_ETERNIAN_REVIEW` 평가만 허용한다.
- 평가 사슬, 제안 다이제스트, 항목별 다이제스트, 허용 작업·범위와 모든
  비실행 경계를 다시 검증한다.
- SQLite 파일명은 `synthetic-`으로 시작해야 하며 URI·서버 DB는 거부한다.
- 제안 원문, 심사, 상태변경을 트랜잭션으로 기록하며 append-only SHA-256
  감사 사슬로 결합한다.

## 상태기계

| 현재 상태 | 독립심사 | 다음 상태 |
| --- | --- | --- |
| `PENDING_ETERNIAN_REVIEW` | `PASS` | `READY_FOR_SYNTHETIC_SHADOW` |
| `PENDING_ETERNIAN_REVIEW` | `HOLD` | `HELD` |
| `PENDING_ETERNIAN_REVIEW` | `REJECT` | `REJECTED` |

`READY_FOR_SYNTHETIC_SHADOW`는 후속 합성 Shadow 후보가 준비됐다는 뜻일 뿐,
Shadow 생성·실행, 코드 변경, 운영자 승인, 결제 실행 또는 운영승격을 뜻하지
않는다. 모든 결과 상태는 이번 기능에서 종결 상태다.

## 분리 통제

- 제안자 ID는 `synthetic:arkaon:NURION_PG:remediation-proposer`로 고정한다.
- 심사자는 별도 `synthetic:eternian-reviewer:*` ID를 사용한다.
- 자동 심사, 자체 승인, 실패 기준 완화, 자동 적용 메서드를 제공하지 않는다.
- 실제 개인정보·결제자료·자격증명·운영 DB를 사용하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_remediation_review_docket -v
PYTHONPATH=src python scripts/run_remediation_review_docket_evidence.py
```

생성되는 증거는 `build/synthetic-remediation-review-docket-evidence.json`과
동일 내용의 SHA-256 파일이다. CI 성공은 병합·배포·운영승인을 의미하지 않는다.
