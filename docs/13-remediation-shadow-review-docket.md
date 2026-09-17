# 합성 Shadow 결과 영속 검토대장

## 목적

기능 #012의 합성 Shadow 평가 중 모든 항목이 통과한 결과만 영속화하고,
ARKAON 평가자와 분리된 에테르니언 심사를 기록한다. 이 기능이 도달할 수 있는
최대 상태는 `READY_FOR_OPERATOR_DECISION`이며 운영자의 결정을 대신하지 않는다.

## 접수 조건

- Shadow 평가 사슬 전체가 유효해야 한다.
- 대상 제안에 대한 평가가 정확히 한 건이어야 한다.
- 종합 판정은 `PROPOSED_FOR_ETERNIAN_REVIEW`여야 한다.
- 모든 항목 결과가 `PASS`이고 결과·평가 SHA-256이 일치해야 한다.
- 평가시각보다 이른 제출, 누락·중복·위변조 자료는 실패 폐쇄한다.

## 상태기계

| 현재 상태 | 에테르니언 심사 | 다음 상태 |
| --- | --- | --- |
| `PENDING_ETERNIAN_REVIEW` | `PASS` | `READY_FOR_OPERATOR_DECISION` |
| `PENDING_ETERNIAN_REVIEW` | `HOLD` | `HELD` |
| `PENDING_ETERNIAN_REVIEW` | `REJECT` | `REJECTED` |

모든 결과 상태는 이번 기능에서 종결 상태다. `READY_FOR_OPERATOR_DECISION`은
운영자에게 판단 가능한 증거가 준비되었다는 뜻이며 승인·코드수정·적용·결제·
배포·운영승격을 의미하지 않는다.

## 무결성과 권한 분리

- 합성 SQLite 파일만 허용하며 URI·서버 DB는 거부한다.
- 평가 원문, 심사, 상태변경을 하나의 트랜잭션 안에서 기록한다.
- append-only SHA-256 감사 사슬과 저장 레코드의 상호 결합을 검증한다.
- 심사 직전에 전체 저장 증거를 다시 검증하며 위변조 시 상태변경 없이 거부한다.
- ARKAON 제출자 ID와 `synthetic:eternian-reviewer:*` 심사자 ID를 분리한다.
- 자동심사, 운영자 결정, 코드 변경, 자동 적용, 실행 메서드를 제공하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_remediation_shadow_review_docket -v
PYTHONPATH=src python scripts/run_remediation_shadow_review_docket_evidence.py
```

CI 증거는 `build/synthetic-shadow-review-docket-evidence.json`과 SHA-256 파일로
고정한다. CI 통과는 병합·배포·운영승인을 뜻하지 않는다.
