# NURION_PG #17901–#18300 ETHERNIAN 독립 감사

## 최종 판정

**ACCEPT — 증분 PR 검수 통과, 병합·배포 미수행.**

`HOLD_NOT_COMMITTED` 원천 사건을 자동 재실행하지 않고 별도의 append-only·non-executable recovery quarantine case로 보존하는 계약이 로컬 회귀와 disposable PostgreSQL CI에서 확인됐다. 이 판정은 실제 network partition, failover, 운영 DB 쓰기, 결제·receipt·retry·approval 실행을 허가하거나 증명하지 않는다.

## 역할 분리

- ARKAON: 구현, 실패 원인 분석, 최소 수정, 전체 회귀 수행
- ETHERNIAN: 코드·계약·원격 로그·아티팩트 독립 검수 및 최종 판정
- 승인 경계: merge, deploy, production write는 본 감사 범위 밖이며 수행하지 않음

## 검수 이력과 HOLD 해소

| 항목 | 원인 | 권고 해결 및 적용 | 대안 | 비용·위험·가역성 | 검증 | 중단·재개·rollback |
|---|---|---|---|---|---|---|
| operator view 쓰기 가능성 | 단순 PostgreSQL view는 자동 갱신 가능 | `GROUP BY` 집계 view로 구조적 non-updatable을 만들고 write-capable 연결에서 INSERT·UPDATE·DELETE 실제 거부 | privilege revoke | 낮음·낮음·높음 | 세 DML 모두 rejected=true | 하나라도 성공하면 HOLD, view 수정 후 전체 재실행, fixture schema drop |
| observed time 완화 비교 | 문자열 prefix는 exact instant를 증명하지 못함 | SQL `observed_at = %s::timestamptz` exact boolean 사용 | Python aware datetime 비교 | 낮음·낮음·높음 | `observed_at_exact_match=true` | false/null이면 HOLD, temporal binding 수정 후 재실행, fixture schema drop |
| 원격 CI 첫 replay 충돌 | psycopg는 `timestamptz`를 datetime으로 반환하지만 기대값은 ISO 문자열이어서 같은 instant도 타입 불일치 | replay SELECT에서도 PostgreSQL이 exact timestamptz equality를 계산하고 boolean true와 나머지 필드를 완전 비교 | Python datetime 정규화 | 낮음·낮음·높음; DB 의미 이중화 방지 | focused 8 PASS, full 1,978 PASS, 재실행 PostgreSQL PASS | 충돌 시 기존 행 보존 후 HOLD, 최소 수정 후 새 CI, 단일 패치 revert 또는 fixture schema drop |

## 원격 증거

- PR: #412
- 검증 head: `c985fed38960117126150b70faf3fee4aab9d465`
- CI run: `35573981636` / run number `1844`
- ARKAON governed synthetic bootstrap: SUCCESS, 1,978 tests PASS
- PostgreSQL ephemeral repository proof: SUCCESS
- recovery quarantine evidence SHA-256: `66b5795a610b34f6b9c534889da1475cd8414b0c3544dbd1de85089000356785`
- PostgreSQL artifact: `10627452137`
- artifact ZIP SHA-256: `8b57befd755574e42dd068fa444dfe3283b8e7ca1e6129839d980550179281d5`
- bootstrap artifact: `10627168354`

## 아티팩트 직접 대조

- same exact replay: one row, converged
- changed payload and cross-key alias: fail closed
- deterministic case identity and all exact bindings: true
- append-only UPDATE/DELETE rejection: true
- operator view INSERT/UPDATE/DELETE rejection: true
- payment, receipt, retry, approval authority: all false
- precommit source row count and retry count: both 0
- fresh read-only operator packet and reconciliation view: true
- cleanup succeeded: true
- production database writes: 0
- credential disclosure and password configuration: false
- actual network partition and failover claims: false

## 잔여 경계와 다음 가능한 방향

실제 network partition 또는 failover를 주장하려면 별도의 승인된 disposable multi-node fixture, 명시적 fault injection, primary/standby 역할 판별, 복구 후 exact reconciliation, cleanup 증거가 필요하다. 단일 PostgreSQL service에서 이를 추정하거나 현재 PASS를 확장 해석해서는 안 된다.

현재 단계의 안전한 운영 원칙은 quarantine case를 읽기 전용 인간 검토 입력으로만 사용하고, 자동 retry·payment·receipt·approval 경로와 연결하지 않는 것이다.
