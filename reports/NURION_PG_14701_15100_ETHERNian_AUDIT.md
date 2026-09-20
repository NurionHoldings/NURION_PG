# NURION_PG #14701~#15100 에테르니언 독립검수

## 결론

**수락 — PR 생성 가능, 병합·배포 불가.**

아르카온의 `비발급 승인영수증 스키마·독립 멱등키 계약`을 독립 검수했다. 최초 제출은 역할 namespace가 달라도 동일 인물 suffix를 가진 source actor와 receipt issuer/verifier의 겸임을 허용해 `HOLD`했다. 에테르니언은 전 원천·영수증 역할을 하나의 정규화된 신원 충돌영역으로 묶는 권장안과 현재 key만 비교하는 최소 대안을 제시했고, 아르카온은 재발 방지 범위가 넓은 권장안을 적용했다.

## 확인 결과

- #14701~#15100의 정확히 400 controls를 등록한다.
- 40개 approval intent 각각에 schema-only receipt 계약과 독립 idempotency key를 구성한다.
- routed 32건에는 32개 append-only human hold와 총 64개 recovery path가 존재한다.
- plan·flow·kind·source contract·readiness manifest·composite identity·source intent·actor slots·sequence·predecessor·nonce·idempotency scope를 직접 결속한다.
- 동일 key·동일 payload의 직렬 및 20중 병렬 요청은 같은 객체로 수렴한다.
- 동일 key의 payload 변경, 다른 key의 schema/key 재사용, nonce replay, 순서 교환, 부분 batch와 full downstream rehash를 거부한다.
- 실제 receipt ID/digest 발급, materialization, execution, observation, PASS/FAIL, 승인·활성화·배포는 모두 0이다.

## HOLD와 극복 지침

- 재현: source actor `synthetic:approval-intent-actor:a-1-0`과 receipt issuer `synthetic:approval-receipt-issuer-role:a-1-0`이 동시에 수락됐다.
- 원인: 역할 prefix만 분리하고 정규화된 실제 actor identity의 단계 간 충돌을 검사하지 않았다.
- 적용: 모든 source actor/counter actor, issuer/verifier, 최종 compiler/validator를 `_id` 기준 단일 occupied identity set으로 검증한다.
- 비권장 대안: 현재 key의 source actor만 비교하면 다른 key의 source actor와 receipt 역할이 겹칠 수 있어 채택하지 않았다.
- 검증: current actor/counter alias, 다른 key alias, 사후변조·전체 재해시 alias를 모두 거부한다. routed materialization/execution 각각의 20중 병렬 멱등성도 영구 회귀시험으로 고정했다.

## 과거 evidence 불변성

- live registry exact equality가 남은 실질 미이관 대상은 #7501 answer-material runner 1개로 확인됐다.
- `ARKAON-LESSONS-7501` 불변 historical snapshot으로 최소 이관하고 #9901 이후 직접 계보와 분리했다.
- 미래 lesson을 추가해도 #7501 snapshot payload가 변하지 않는 회귀시험과 #7501 evidence 실행을 독립 확인했다.

## 독립 재검증

- 전용·인접·registry: 66 PASS
- 전체 회귀: 1,886 PASS
- #9901~#15100 직접 계보 13단계 evidence: PASS
- #7501 historical evidence: PASS
- governance/lesson registry/compileall/diff-check: PASS
- Evidence SHA-256: `5aaa5a5e2dff4fcfc451056875b67d8651c2511704bc754b0593ea2f66b0ffd6`

## 잔여 위험과 다음 방향

- 현재 산출물은 receipt의 스키마 계약일 뿐 실제 receipt가 아니다. 발급 API, 서명, 영속 원장, 외부 호출 권한은 없다.
- 다음 단계는 발급 전 검증 패킷과 issuer/verifier 서명 입력 형식을 설계하되, 별도 인간 승인 전까지 receipt 생성과 상태 전이를 금지해야 한다.
- 병합과 배포는 별도 인간 승인 전까지 금지한다.
