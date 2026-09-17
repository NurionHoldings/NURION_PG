# 합성 패치 Shadow 독립 검토대장

## 목적

기능 #019에서 모든 범위가 통과한 메타데이터 전용 패치 Shadow 결과만
합성 SQLite 대장에 영속화하고, ARKAON 평가자와 분리된 에테르니언 심사를
기록한다. 최대 상태는 `READY_FOR_OPERATOR_DECISION`이며 운영자 결정을
기록하거나 대신하지 않는다.

## 접수 조건

- 패치 Shadow 평가 사슬 전체가 유효해야 한다.
- 대상 구현제안의 Shadow 평가가 정확히 한 건이어야 한다.
- 종합 판정은 `PROPOSED_FOR_ETERNIAN_REVIEW`여야 한다.
- 모든 범위 결과가 `PASS`이고 평가·항목 SHA-256이 일치해야 한다.
- 패치 본문, 소스·파일 변경, 네트워크·운영 접근, 자격증명·개인정보 및
  금전 이동 흔적이 없어야 한다.
- 누락·중복·위변조·시간 역전은 실패 폐쇄한다.

## 상태기계

| 현재 상태 | 에테르니언 심사 | 다음 상태 |
| --- | --- | --- |
| `PENDING_ETERNIAN_REVIEW` | `PASS` | `READY_FOR_OPERATOR_DECISION` |
| `PENDING_ETERNIAN_REVIEW` | `HOLD` | `HELD` |
| `PENDING_ETERNIAN_REVIEW` | `REJECT` | `REJECTED` |

각 결과는 이번 기능의 종결 상태다. `READY_FOR_OPERATOR_DECISION`은 운영자가
증거를 검토할 수 있다는 뜻일 뿐 승인·코드수정·적용·병합·결제·배포 또는
운영승격을 의미하지 않는다.

## 무결성과 권한 분리

- `synthetic-*.(db|sqlite|sqlite3)` 파일 또는 메모리 SQLite만 허용한다.
- Shadow 원문, 심사, 상태변경은 트랜잭션으로 기록한다.
- append-only SHA-256 감사 사슬과 저장 레코드의 결속을 매번 재검증한다.
- ARKAON 제출자와 `synthetic:eternian-reviewer:*` 심사자를 분리한다.
- 자동심사·운영자 결정·패치본문·코드변경·기준완화·실행 경로는 제공하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_shadow_review_docket -v
PYTHONPATH=src python scripts/run_synthetic_patch_shadow_review_docket_evidence.py
```

CI 증거는 `build/synthetic-patch-shadow-review-docket-evidence.json`과 SHA-256
파일로 고정한다. CI 통과는 병합·배포·운영승인을 뜻하지 않는다.
