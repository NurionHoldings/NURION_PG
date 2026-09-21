# NURION_PG #14301~#14700 에테르니언 독립검수

## 결론

**수락 — PR 생성 가능, 병합·배포 불가.**

아르카온의 `복합계획 신원·이중 승인인텐트 봉투 게이트`를 독립 검수했다. 최초 제출의 routed 재시도 충돌과 보완 제출의 과거 evidence 전역-latest 의존을 각각 `HOLD`했다. 각 HOLD에는 원인, 권장 수정, 대안, 비용·위험·가역성, 검증 및 재개 기준을 제공했고, 아르카온은 멱등 충돌 범위 교정과 공용 stage-bounded chain 검증을 적용했다.

## 확인 결과

- 정확히 400 controls와 40개 PENDING envelope(20 materialization, 20 execution)를 생성한다.
- routed 16건에는 32개 append-only human hold와 64개 recovery path가 존재한다.
- `plan_id`, flow, kind, source contract, readiness manifest를 복합 identity로 직접 결속한다.
- materialization과 execution intent는 독립 actor, counter actor, sequence, predecessor, nonce/replay scope를 갖는다.
- 동일 key·동일 후보의 직렬·병렬 재시도는 같은 객체로 수렴한다.
- 동일 key의 envelope ID/actor 변경, 다른 key의 ID 재사용, actor 재사용, nonce replay와 full downstream rehash 공격을 거부한다.
- receipt 발급, fixture materialization, probe 실행, 관찰값, PASS/FAIL, 승인·활성화·배포는 모두 0이다.

## HOLD와 극복 지침

1. **routed 멱등성 오탐**: 현재 key 자신의 actor·ID·nonce를 occupied 충돌 집합에서 제외하는 최소 보수를 권장했다. 별도 idempotency-key schema는 실제 receipt 단계 전 구조개선 대안으로 유지했다.
2. **미래 단계 추가 회귀**: `validated_stage_chain_through(max_end)` 공용 helper를 권장했다. runner별 로컬 필터는 변경량은 작지만 중복·드리프트 위험이 있어 차선으로 분류했다.
3. 공용 helper는 정확한 경계 존재, 상한 이하 연속성·단조성 검증을 수행한다. #13901과 #14301 runner의 `len(chain)`·`chain[-1]` 전역 가정을 제거했고 미래 snapshot 주입 회귀시험을 추가했다.

## 독립 재검증

- 전용·인접·registry: 64 PASS
- 전체 회귀: 1,859 PASS
- #9901~#14700 직접 계보 12단계 evidence: PASS
- governance/lesson registry/compileall/diff-check: PASS
- 고정 chain 길이/latest 검색: 0건
- Evidence SHA-256: `cff5833dec5722c54c7915bf8f5ac7f22310711c959e2f75af8d78d9660f0484`

## 잔여 위험과 후속 계획

- 전체 90개 역사·병렬 evidence runner는 이번 직접 12단계 승인 범위가 아니다. 별도 전수 점검에서 #7501 runner의 live-registry exact-equality 기술부채를 발견했으며, 향후 stage-bounded snapshot으로 이관해야 한다.
- 실제 approval receipt, materialization, execution은 아직 구현·승인되지 않았다. 다음 단계는 receipt schema와 idempotency key를 독립 설계·검증한 뒤에도 기본 상태를 HOLD/PENDING으로 유지해야 한다.
- 병합과 배포는 별도 인간 승인 전까지 금지한다.
