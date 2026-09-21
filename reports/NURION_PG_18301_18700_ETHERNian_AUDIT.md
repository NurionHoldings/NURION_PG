# NURION_PG #18301–#18700 ETHERNIAN 독립 감사

## 최종 판정

**ACCEPT — 증분 PR 검수 통과, 병합·배포 미수행.**

기존 recovery quarantine case에 인간검토 처분을 결속하되 실행 권한을 만들지 않는 `HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE` 증명 계층이 로컬 회귀와 disposable PostgreSQL CI에서 확인됐다. 실제 network partition, failover, fault injection, 운영 DB 쓰기는 수행하거나 주장하지 않았다.

## 역할 분리

- ARKAON: 선행 구현, HOLD 수정, 전체 회귀
- ETHERNIAN: 데이터 결속·우회 경로·원격 PostgreSQL·아티팩트 독립 검수
- 승인 경계: merge, deploy, production write는 수행하지 않음

## HOLD와 되는 해결 방향

| HOLD | 원인 | 적용한 해결 | 대안 | 비용·위험·가역성 | 검증 | 중단·재개·rollback |
|---|---|---|---|---|---|---|
| wrong digest 우회 | disposition의 `case_digest`가 quarantine case ID와 DB에서 한 쌍으로 결속되지 않음 | quarantine `(case_id, case_digest)` UNIQUE와 disposition composite FK 적용 | application 선조회 | 낮음·중간·높음; 선조회는 race/우회 위험으로 미채택 | 별도 미처분 case에 새 key·새 sequence·wrong digest INSERT 실제 거부 | 성공 시 HOLD, FK 복구 후 fresh DB 재실행, fixture schema drop |
| 원격 cross-key 처분 성공 | 같은 case에 새 disposition key와 sequence를 허용해 `cross_key_fail_closed` 주장과 모순 | 현재 단계에서 `UNIQUE(case_id)`로 case당 단일 처분 강제 | 복수 처분 허용 | 낮음·중간·높음; 계보 없는 복수 처분은 미채택 | 실제 cross-key INSERT 거부와 disposition row count 1 | 성공 시 HOLD, unique 제약 복구 후 재실행, fixture schema drop |
| 일반 invariant 오류 | 최초 원격 실패가 실패 항목을 구분하지 못함 | 값·DSN·credential 없이 실패한 invariant 이름만 정렬 출력 | 단계별 assert | 낮음·낮음·높음 | `failed=<invariant keys>`만 노출 | 비밀값 노출 시 중단, 진단 제거 후 재실행, patch revert |

향후 재검토나 처분 변경이 필요하면 현재 행을 덮어쓰거나 두 번째 key를 임의 추가하지 않고, 별도 supersession/versioning 공정에서 predecessor 결속과 순서를 설계해야 한다.

## 원격 증거

- PR: #413
- 검증 head: `b504269d38023134adc4f27121fd47e644ecd0b4`
- CI run: `35577916001` / run number `1865`
- ARKAON governed synthetic bootstrap: SUCCESS, 1,987 tests PASS
- PostgreSQL ephemeral repository proof: SUCCESS
- recovery disposition evidence SHA-256: `14786cf3c902cb759b4eb268da67b56909beee1ebe13dcdb9bd3c392defba7b9`
- PostgreSQL artifact: `10628891002`
- PostgreSQL artifact ZIP SHA-256: `dd2bd4d60d6ef3d57815686c3564acdf73e8fd950ed9182048d76f460b3491a5`
- bootstrap artifact: `10629565742`
- bootstrap artifact ZIP SHA-256: `e2e126c8639c8b64cc3247b7e0ccfae6d5ea67a17aa6e82f92b2803b847634ed`

## 아티팩트 직접 대조

- deterministic disposition identity와 exact quarantine case binding: true
- same replay: one row, converged
- same-key changed payload, cross-key alias, new-key/new-sequence wrong digest: 모두 fail closed
- composite case digest FK enforced: true
- disposition append-only 및 quarantine unchanged: true
- operator view INSERT·UPDATE·DELETE rejection: true
- reviewed time exact PostgreSQL timestamptz equality: true
- payment·receipt·retry·approval·execution authority: 모두 false
- production database writes: 0
- cleanup succeeded: true
- credential disclosure/password configuration: false
- actual network partition/failover/fault injection: 모두 false

## 다음 공정 경계

실제 failover 증명은 승인된 disposable primary/standby 환경, 통제된 fault injection, 역할 판별, partition 전후 식별자 결속, recovery reconciliation, exact cleanup이 마련된 별도 공정에서만 수행한다. 준비되지 않은 단일 service CI를 failover로 해석하지 않는다.
