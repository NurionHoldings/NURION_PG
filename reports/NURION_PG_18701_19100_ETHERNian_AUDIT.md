# NURION_PG #18701–#19100 ETHERNIAN 독립 감사

## 최종 판정

**ACCEPT — append-only recovery supersession 증명 통과, 병합·배포 미수행.**

기존 `HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE` 처분을 수정하거나 삭제하지 않고, 정확한 predecessor를 따라 재검토 버전을 추가하는 단일 계보가 disposable PostgreSQL에서 증명됐다. 이 단계는 결제·영수증·재시도·승인·실행 권한을 생성하지 않으며 실제 network partition, failover, fault injection 또는 운영 DB 쓰기를 주장하지 않는다.

## 역할 분리

- ARKAON: 선행 구현, HOLD 수정, 전체 회귀
- ETHERNIAN: 계보 제약, 우회 경로, 원격 PostgreSQL 및 아티팩트 독립 검수
- 승인 경계: merge, deploy, production write 미수행

## HOLD와 해결 방향

| HOLD | 원인 | 적용한 해결 | 대안 | 비용·위험·가역성 | 검증 | 중단·재개·rollback |
|---|---|---|---|---|---|---|
| lineage sequence gap 허용 | `lineage_sequence`가 양수·UNIQUE만 강제돼 version 3에 sequence 99가 가능 | 단일 case·단일 chain 모델에 맞춰 DB `CHECK(lineage_sequence=version)` 적용 | predecessor lineage sequence를 복합 FK에 포함하고 +1 CHECK | 낮음·중간·높음; 단일 계보에서는 version 대응이 단순·명확 | sequence 재사용과 실제 gap 99를 분리해 INSERT 거부 | gap 성공 시 HOLD, CHECK 복구 후 fresh DB 재실행, fixture schema drop |
| lesson/stage 고정 개수 실패 | 신규 lesson과 stage 추가 후 기대값이 이전 수치 유지 | lesson 39, stage chain 17로 갱신 | 동적 계산 | 낮음·낮음·높음 | 전체 회귀 1,995 PASS | 불일치 시 registry HOLD, 선언과 테스트 동시 검토, patch revert |
| 기존 retry proof 간헐 실패 | loser가 최초 winner의 commit 완료 전에 즉시 재진입해 실제 `40001`을 3회 소진 가능 | winner commit `Event` handoff 후 attempt 2가 bounded wait하고 fresh connection으로 재시도 | 고정 sleep 또는 max-attempt 확대 | 낮음·낮음·높음; 운영 로직이 아닌 disposable harness만 변경 | 첫 실제 40001 1건, attempt 2 성공, fresh PID, 전체 1,996 PASS | 5초 내 handoff 없으면 fail closed, 원인 수정 후 fresh schema 재실행, harness patch revert |

향후 복수 계보 또는 병합이 필요하면 현재 단일 successor 제약을 느슨하게 바꾸지 않고 별도 branch/merge 모델, 충돌 판정, 인간 승인 경계를 설계해야 한다.

## 원격 증거

- PR: #414
- 검증 head: `a4ca064cd872973328ee6012d38481da6e5c69bb`
- CI run: `35582610647` / run number `1881`
- 전체 회귀: 1,996 PASS
- PostgreSQL proof: SUCCESS
- supersession evidence SHA-256: `e826681a535d73c27689ca5580a28365a0eefd8de20d902195dc279451f2426f`
- PostgreSQL artifact: `10630613944`
- PostgreSQL artifact ZIP SHA-256: `7668baeb33cbb219969837b0c2fd8e0ae52a06ec18b2a8caed851788e95df9a6`
- bootstrap artifact: `10630911865`
- bootstrap artifact ZIP SHA-256: `21f1f6c6389a631c11c55b9b9d5d8654721e96c0c2386995e1100e32d1fece72`

## 아티팩트 직접 대조

- deterministic supersession identity: true
- base disposition 및 predecessor digest exact match: true
- version과 lineage sequence의 단조·연속 증가: true
- sequence gap·reuse: fail closed
- genesis 1개, predecessor당 successor 1개, current head 1개: true
- same replay: 2-row lineage 유지 및 추가 행 없음
- changed payload, cross-key, predecessor fork, stale head, alias predecessor: fail closed
- base disposition immutable, supersession append-only: true
- operator view INSERT·UPDATE·DELETE rejection: true
- payment·receipt·retry·approval·execution authority: 모두 false
- cleanup succeeded: true
- production database writes: 0
- credential disclosure/password configuration: false
- actual partition/failover/fault injection: 모두 false

## 다음 공정 경계

다음 단계는 current head를 읽는 운영자 검토 snapshot/receipt를 비실행·append-only로 고정하거나, 실제 failover로 진입하기 전 disposable primary/standby fixture의 생성·역할·fault·복구·폐기 계약을 구체화하는 방향이 적합하다. 실제 장애 전환 주장은 multi-node 환경과 통제된 fault injection이 마련된 뒤에만 허용한다.
