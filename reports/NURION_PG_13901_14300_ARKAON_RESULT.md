# NURION_PG #13901~#14300 ARKAON 선행 결과

## 자율 결론

단계명은 `비실행 관찰준비 매니페스트·독립 승인게이트`로 정했다. 직전 계약만으로 준비 완료를 주장할 수 있는 구조적 공백을 차단하기 위해 materialization 이전 필수 조건을 source-bound 계획으로 결속했다.

## 구현 및 극복 방향

- 16×25의 정확히 400 controls와 `ARKAON-LESSONS-13901` stage snapshot을 추가했다.
- 16 routed 계획에 resource budget, privacy/data classification, determinism, isolation, timeout, side-effect prohibition, receipt schema, 독립 승인 게이트를 결속했다.
- 거부 시 최소 계획 보수안과 전면 재구성안 두 경로를 비용·위험·가역성·검증·중단·rollback·재개 조건과 함께 제공한다.
- 4 N/A에는 actor와 계획 내용을 금지하고 16 routed에는 서로 다른 planner/challenger를 요구한다.
- fixture materialization, probe 실행, 관찰값, PASS/FAIL, 원인 확정, 승인·활성화·배포 권한은 모두 0이다.
- 전체 downstream 재해시 공격으로 budget 삭제, 개인정보 등급 하향, 결정성/timeout 삭제, 격리 완화, side effect 허용, receipt 오염, 승인 우회, materialization/execution 위조, 단일 복구경로, source 변조를 검증한다.

## 자체 검증

- 전용·인접·lesson registry: 67 PASS
- 전체 회귀: 1,834 PASS
- governance / lesson registry / compileall / diff-check: PASS
- 11단계 연속 evidence: PASS
- evidence SHA-256: `204f31d2dde1879b78a8f795e72abda13f0e6680f68a85454cb84f5ad145f62d`
- 공통 final-docket validator 추출은 여러 과거 단계의 검증 의미를 동시에 바꾸는 고위험 리팩터링이므로 이번 단계에는 포함하지 않고, 인터페이스·불변식 호환성을 먼저 설계하는 후속 구조개선 후보로 유지한다.

## 에테르니언 HOLD 보완

- 원인: plan digest는 각 행을 결속했지만 서로 다른 key 사이의 `plan_id` 전역 유일성을 검사하지 않았다.
- 권장안을 적용해 동일 key·동일 행은 멱등 반환, 동일 key 변경은 conflict, 다른 key ID 재사용은 API와 사후 integrity에서 모두 거부한다.
- 병렬 N/A 행 멱등성과 duplicate ID 전체 downstream 재해시 공격을 추가했다.
- 잔여위험: 현재 receipt schema는 필드명 계약이며 manifest/plan digest가 receipt의 manifest/source 결속을 간접 보장한다. receipt 자체에 복합 plan identity를 직접 포함하는 대안은 schema migration과 과거 evidence 호환성 검토가 필요한 후속 구조개선이다.

## 검수 요청

`ETH-13901-AUDIT-001` / `ARL-13901-001`을 등록했다. 에테르니언은 구현·테스트·evidence를 독립 검수하고 HOLD 시 원인, 권장안, 2개 대안, 비용·위험·가역성, 검증, 중단·재개·rollback을 제시해야 한다. 이 문서는 승인·병합·배포 판정이 아니다.
