# 합성 통제·감사 체계 종결 — 100%

## 종결 판정

`#1~#20300`으로 동결한 **합성 통제·감사 체계**는 아래의 명시적 종결 기준 10개를 모두 통과했으므로 100% 완료로 판정한다. 이 수치는 합성 통제 범위의 완결성을 뜻하며 실제 PG 운영, 상용 준비, 실결제 또는 규제 승인을 뜻하지 않는다.

## 기계검증 기준

| 기준 | 검증 내용 |
| --- | --- |
| MODULE_TEST_PARITY | 104개 `synthetic_*` 모듈마다 동일 이름의 전용 테스트 존재 |
| FAIL_CLOSED_GOVERNANCE | 기본 권한 결정 `BLOCKED` |
| NO_LIVE_EXECUTION_AUTHORITY | 실제 결제·환불·지급 권한 금지 |
| NO_AUTOMATIC_MERGE_OR_DEPLOY | 자동 병합·배포·운영 승격 금지 |
| EXTERNAL_BLOCKERS_OPEN | 외부 계약·등록·보안·자격증명 blocker가 미해결 상태로 유지 |
| PINNED_CI_ACTIONS | 모든 GitHub Action을 전체 commit SHA로 고정 |
| DETERMINISTIC_EVIDENCE_RUNNERS | 100개 이상의 결정론 evidence runner 유지 |
| FULL_REGRESSION_GATE | CI에서 전체 테스트 discovery 강제 |
| POSTGRES_FAILURE_PROOFS | deadlock·connection loss·quarantine 실제 PostgreSQL proof 강제 |
| ROLE_SEPARATED_REVIEW | 에테르니언 remediation·아르카온 lesson registry·독립 검토 기준 유지 |

`scripts/validate_synthetic_control_closure.py`는 저장소 상태에서 이 조건을 재계산하고 `build/synthetic-control-closure-evidence.json`과 SHA-256 sidecar를 생성한다. 조건 누락, 모듈·테스트 불일치, 정책 완화, CI gate 제거는 실패폐쇄한다.

## 고정 경계

- stage 번호는 `#20300`에서 동결한다.
- 신규 synthetic stage를 공정률 목적으로 추가하지 않는다.
- 기존 synthetic 자산은 OPS 운영 코드의 부정 테스트와 수용기준으로만 재사용한다.
- 실제 PG 완성률과 상용 운영 준비도는 별도 지표로 유지한다.
- 실결제, 운영 자격증명, 자동 병합, 자동 배포는 계속 금지한다.
