# NURION_PG #15501~#15900 에테르니언 독립검수

## 결론

**수락 — PR 생성 가능, 병합·배포 불가.**

아르카온의 `비발급 검증결과 봉인·원자적 멱등예약 계약`을 독립 검수했다. 40개 preissuance packet마다 비권한 reservation·result candidate·seal input을 하나씩 구성하며 최대 상태는 `RESERVED_NOT_COMMITTED_NOT_ISSUED`다. 검수 중 시간창 하한과 snapshot sequence의 사후 불변식 공백을 발견해 `HOLD`했고, 사전·사후 검증 parity와 완전 재해시 음성시험을 적용한 뒤 재검증했다.

## 확인 결과

- #15501~#15900의 정확히 400 controls를 등록한다.
- reservation, result candidate, seal input을 각각 40개 구성한다.
- routed 32건에는 32개 append-only human hold와 총 64개 recovery path가 존재한다.
- source packet·양쪽 signature input·composite identity·source scopes·policy v1·sequence·predecessor·nonce·owner/validator를 직접 결속한다.
- 동일 key·동일 payload의 직렬·병렬 및 routed materialization/execution 20중 요청은 같은 객체로 수렴한다.
- changed payload, cross-key reservation ID/token/scope/nonce 재사용, actor alias, 순서 교환, 부분 batch와 commit·receipt·authority 위조를 거부한다.
- cryptographic verification, signature/key/credential, commit, receipt, DB/ledger, PG/API, 실행·관찰·승인·배포는 모두 0이다.

## HOLD와 되는 방향 지침

### 시간창 하한

- 재현: `observed_epoch=0`이 packet의 `issued_at_epoch=2000000100`보다 이전인데도 예약됐다.
- 권장안: `issued_at_epoch ≤ observed_epoch ≤ expires_at_epoch` 폐구간을 API와 `_reservation_valid` 양쪽에 동일 적용했다.
- 대안: clock-state enum을 별도 도입할 수 있으나 이번 결정적 합성 단계에는 복잡도가 커 보류했다.
- 검증: 발급 직전과 만료 직후는 거부하고 양쪽 경계는 수락한다. 하한 위조 후 reservation·seal·후속 predecessor·event·docket을 전부 재해시해도 무결성은 false다.

### snapshot sequence 사후 불변식

- 원인: anchor는 양의 정수 sequence를 검사했지만 `_snapshot_valid`가 같은 조건을 재검증하지 않았다.
- 권장안: 양의 정수, bool 금지 조건을 사전·사후에 동일 적용했다.
- 검증: `0`, 음수, `True`를 API와 완전 downstream rehash 경로 모두에서 거부한다.
- 두 수정은 합성 reservation 후보에만 영향을 주며 원천 packet은 보존되므로 비용·회귀위험이 낮고 가역적이다.

## 독립 재검증

- 전용·인접·registry: 49 PASS
- 전체 회귀: 1,919 PASS
- #9901~#15900 직접 계보 15단계 evidence: PASS
- #7501 historical evidence: PASS
- lesson registry: 31 lessons PASS
- governance/compileall/diff-check: PASS
- Evidence SHA-256: `5794bd8cefe79e4fe87594631d80be78f45222e74ede71e38cecb9929fdeb4eb`

## 잔여 위험과 다음 방향

- 현재 원자성은 단일 프로세스의 `RLock` 기반 합성 계약이다. PostgreSQL unique constraint, transaction isolation, crash recovery를 증명하지 않는다.
- 다음 단계는 실제 금융 행위 없이 PostgreSQL용 reservation 원장 schema·transaction proof를 독립 설계하는 것이 적절하다.
- 병합과 배포는 별도 인간 승인 전까지 금지한다.
