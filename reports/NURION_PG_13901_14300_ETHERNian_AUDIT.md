# NURION_PG #13901~#14300 에테르니언 독립검수

## 결론

**수락 — PR 생성 가능, 병합·배포 불가.**

아르카온의 `비실행 관찰준비 매니페스트·독립 승인게이트`를 검수했다. 최초 제출은 서로 다른 case에서 동일한 `plan_id`를 재사용할 수 있어 `HOLD`했다. 에테르니언은 전역 ID 유일성 보강과 복합 identity migration 두 경로를 제시했고, 아르카온은 최소·가역적인 전역 유일성 검증을 적용했다.

## 확인 결과

- 400 controls, 20 plans(4 N/A+16 routed), 32 복구경로, 16 append-only 인간판단 hold
- resource budget, privacy/data classification, determinism, isolation, timeout, side-effect prohibition, receipt schema, 독립 approval gate를 source-bound 계획에 결속한다.
- fixture materialization, probe 실행, 관찰값, PASS/FAIL, 원인 확정, 승인·활성화·배포는 모두 0이다.
- budget 삭제, privacy 하향, determinism/timeout 제거, isolation 완화, side effect 허용, receipt 오염, approval 우회, materialization/execution 위조, 단일 복구경로, source 재해시 공격을 거부한다.
- `plan_id`는 batch 전체에서 유일하며 동일 key·동일 row는 멱등, 동일 key 충돌과 다른 key ID 재사용은 거부된다.
- duplicate ID를 주입한 뒤 parent/event/hold/final docket을 정합 재해시해도 integrity와 complete는 false다.

## 독립 재검증

- 전용·인접·registry: 67 PASS
- 전체 회귀: 1,834 PASS
- 11단계 연속 evidence: PASS
- governance/lesson registry/compileall/diff-check: PASS
- Evidence SHA-256: `204f31d2dde1879b78a8f795e72abda13f0e6680f68a85454cb84f5ad145f62d`

## 잔여 위험

receipt schema는 plan identity를 직접 포함하지 않고 manifest/plan digest를 통해 간접 결속한다. `(flow, kind, source_contract_digest)` 복합 identity를 receipt에 직접 포함하는 migration과 공통 final-docket validator는 후속 구조개선 후보다. 실제 materialization과 실행은 별도 승인 전까지 금지된다.
