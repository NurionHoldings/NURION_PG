# NURION_PG #15101~#15500 에테르니언 독립검수

## 결론

**수락 — PR 생성 가능, 병합·배포 불가.**

아르카온의 `발급 전 검증 패킷·이중 서명입력 계약`을 독립 검수했다. 실제 서명값이나 receipt를 만들지 않고, 40개 source schema에 대해 issuer/verifier용 입력 digest 80개를 분리 구성한다. 검수 중 정책 namespace만 맞으면 구버전 `v0`도 최초 입력으로 수락되는 downgrade를 발견해 `HOLD`했고, 정확한 단계 정책 버전 고정과 명시적 migration 기준을 적용한 뒤 재검증했다.

## 확인 결과

- #15101~#15500의 정확히 400 controls를 등록한다.
- 40개 validation packet과 80개 domain-separated signature-input digest를 구성한다.
- routed 32건에 32개 append-only human hold와 64개 recovery path가 존재한다.
- source schema identity, idempotency scope, composite identity, source intent, sequence, predecessor, nonce, actor, challenge, audience, purpose, policy, 결정적 expiry를 직접 결속한다.
- issuer/verifier와 모든 선행 actor·compiler·validator의 정규화 identity 충돌을 거부한다.
- 동일 key·동일 payload의 직렬·병렬 및 routed materialization/execution 20중 요청은 같은 객체로 수렴한다.
- cross-key packet/challenge/input 재사용, 순서 교환, 부분 batch, forged signature·receipt·authority와 full downstream rehash 공격을 거부한다.
- 서명값 생성·검증, 키·자격증명 접근, receipt 발급, 원장 기록, PG 호출, 실행·관찰·승인·배포는 모두 0이다.

## HOLD와 되는 방향 지침

- 재현: 최초 `add_packet` 호출에 `synthetic:signature-policy-version:v0`를 넣으면 정합 패킷으로 수락됐다.
- 원인: policy version을 digest에 결속했지만 허용 가능한 현재 버전을 정확히 제한하지 않았다.
- 권장안: `REQUIRED_POLICY_VERSION=v1`을 단계 계약에 고정하고 API와 사후 무결성 검사 모두 정확 일치를 요구한다.
- 대안: anchor에 allowed-policy registry tuple/digest를 결속하면 확장성은 높지만 이번 단계에서는 변경 범위와 결합도가 커 후속 과제로 유지한다.
- migration: 정책 변경은 새 stage snapshot과 명시적 accepted-version 변경을 동반해야 하며 자동 하향 호환은 금지한다.
- 검증: v0·누락·unknown·미래 v2의 최초 입력과, v0 기준으로 scope·nonce·양쪽 입력·후속 predecessor·event·docket을 전부 재해시한 공격을 모두 거부한다.

## 독립 재검증

- 전용·인접·registry: 58 PASS
- 전체 회귀: 1,902 PASS
- #9901~#15500 직접 계보 14단계 evidence: PASS
- #7501 historical evidence: PASS
- lesson registry: 30 lessons PASS
- governance/compileall/diff-check: PASS
- Evidence SHA-256: `6c4a8a72b9537ee27b6bf14c8dea02202fed441470c8e0628cd675f5b043e33e`

## 잔여 위험과 다음 방향

- 현재 산출물은 content-addressed 서명 입력 계약이며 실제 cryptographic signature 검증이나 키 보관을 구현하지 않는다.
- 다음 단계는 영속 원장에 쓰기 전에 검증 결과를 봉인하는 비발급 검증 receipt와 원자적 idempotency reservation을 설계하되, 실제 키·서명·receipt 발급은 별도 단계와 인간 승인 전까지 금지해야 한다.
- 병합과 배포는 별도 인간 승인 전까지 금지한다.
