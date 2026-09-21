# NURION_PG #15501~#15900 ARKAON 결과보고

## 결론

`비발급 검증결과 봉인·원자적 멱등예약 계약`을 합성·메모리 계층으로 구현했다. 40개 preissuance packet마다 정확히 하나의 비권한 reservation을 배정하고, 실제 commit·서명·receipt·DB/원장·외부 호출은 수행하지 않는다.

## 구현 통제

- 400 controls, 40 result candidates, 40 seal inputs, 40 reservations
- same key/same payload 직렬·20-way 병렬 단일 객체 수렴
- changed payload 및 다른 key의 ID/token/scope/nonce 재사용 fail-closed
- policy v1 exact gate와 wall-clock 비의존 결정적 expiry
- source packet, 양쪽 signature input, composite identity, source scope, sequence/predecessor/nonce 직접 결속
- source actor부터 final validator까지 `_id` 기반 전역 충돌영역
- 32 HOLD에 64개 content-addressed 복구경로

## 해결 지침

권장안은 손상·만료 reservation을 폐기하고 원본 v1 packet에서 새 key/token과 독립 actor로 재생성하는 것이다. 비용과 위험은 낮고 가역성은 높다. 순서·역할 계보가 불명확하면 대안으로 batch 전체를 격리한 뒤 canonical order로 재구축한다. source packet 또는 policy가 불완전하면 중단하고, 독립 검증 후 재개하며, rollback은 source docket을 보존한 채 비commit reservation만 폐기한다.

## 비권한 경계

`RESERVED_NOT_COMMITTED_NOT_ISSUED`를 넘지 않는다. cryptographic verification, signature, key/credential, commit, receipt, DB/ledger, materialization, execution, observation, PASS/FAIL, 승인, 활성화, 배포는 모두 0이다.

## 잔여 위험

메모리 모델이므로 프로세스 간 원자성, PostgreSQL unique constraint/transaction, crash recovery, 실제 cryptographic verification과 receipt issuance는 검증하지 않았다. 후속 단계의 별도 운영 계약과 독립 감사가 필요하다.

## 자체검증 결과

- focused/adjacent/registry: 49 PASS
- 전체 회귀: 1,919 PASS
- #9901~#15900 15단계 직접 evidence: PASS
- #7501 historical evidence: PASS
- governance registry: 31 lessons PASS
- compileall / `git diff --check`: PASS
- Evidence SHA-256: `5794bd8cefe79e4fe87594631d80be78f45222e74ede71e38cecb9929fdeb4eb`

## 에테르니언 HOLD 보완

### 시간창 하한

- 원인: 만료 상한만 검사해 packet 발급시각 이전의 합성 epoch가 허용됐다.
- 권장 해결: API와 사후 integrity 모두 `issued_at ≤ observed ≤ expires_at` 폐구간을 exact 검증한다.
- 대안: 별도 clock-state enum 도입. 이번 메모리 합성단계에는 복잡도 대비 이점이 작아 보류했다.
- 비용·위험·가역성: 비용 낮음, 위험 낮음, 완전 가역적이다.
- 검증: `issued_at-1`/`expires_at+1` 거부, 양 경계 수락, 하한 위조 후 전체 재해시 무결성 거부.
- 중단·재개·rollback: 범위 밖 epoch에서 중단하고 새 key/token으로 범위 안 재생성 후 재개한다. 비commit reservation만 폐기한다.

### snapshot sequence 사후 불변식

- 원인: anchor는 positive non-bool integer를 요구했지만 `_snapshot_valid`가 같은 검사를 반복하지 않았다.
- 권장 해결: 사전·사후 검증 parity를 맞춘다.
- 대안: 공통 snapshot validator 추출. 여러 계층을 함께 바꾸는 범위이므로 후속 리팩터링으로 남겼다.
- 비용·위험·가역성: 비용 낮음, 호환 위험 낮음, 가역적이다.
- 검증: `0`, `True`, 음수의 API 거부 및 snapshot·events·docket 전체 재해시 공격 거부.
- 중단·재개·rollback: invalid sequence에서 중단하고 원본 predecessor snapshot에서 양의 정수 sequence로 다시 anchor한다. 손상 snapshot과 비commit downstream만 폐기한다.
