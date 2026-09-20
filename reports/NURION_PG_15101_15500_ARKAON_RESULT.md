# NURION PG #15101~#15500 ARKAON 결과

## 결론

발급 전 검증 패킷과 이중 서명입력 계약을 구현했다. 정확히 400 controls, 40 validation packets, 80 domain-separated signature-input digests를 구성한다. 실제 서명·키·자격증명·receipt 발급·원장 기록·실행·관찰·권한 행위는 모두 0이다.

## 해결 지침

- 권장안: 손상된 단일 패킷을 폐기하고 온전한 source schema에서 새 key로 두 입력을 재구성한다. 비용/위험은 낮고 가역성은 높다.
- 대안: 순서 또는 predecessor가 불명확하면 해당 이중 패킷 묶음을 격리하고 canonical order로 재구성한다. 비용은 중간, 위험은 낮고 가역성은 높다.
- 중단: source, actor, policy, challenge 또는 lineage가 불일치하면 즉시 HOLD한다.
- 재개: 독립 검증자가 새 actor slots와 challenge를 확인한 뒤 fresh key로 재개한다.
- rollback: packet candidate만 폐기하고 source receipt schema와 이전 docket은 보존한다.

## 검증 범위

same-key convergence, routed materialization/execution 20-way concurrency, changed payload, global actor alias, cross-key packet/challenge/input reuse, partial batch/order swap, challenge/domain/audience/purpose/policy/expiry 교환·삭제·완화, full-rehash, forged signature/receipt/authority 공격을 fail-closed로 시험한다.

## 자체감사에서 발견하고 해결한 결함

1. 신규 issuer/verifier 접미사가 직전 단계 역할과 충돌했다. 권장안으로 단계 고유 식별자를 사용했고 namespace만 바꾸는 alias 공격 차단은 유지했다. 대안은 중앙 actor allocator 도입이나 이번 단계 범위를 넘어 선택하지 않았다.
2. API 진입 검사는 충분했지만 full downstream rehash 시 packet/docket namespace와 전역 packet/challenge/input 중복을 재검사하지 않는 공백이 있었다. 권장안으로 `_packet_valid`와 `_integrity` 양쪽에 namespace 및 전역 유일성 검사를 추가했다. 대안인 외부 validator 분리는 비용과 결합도가 높아 보류했다.
3. 에테르니언 독립검수에서 namespace가 맞으면 v0 정책도 최초 입력으로 수락되는 downgrade가 발견되어 HOLD됐다. 원인은 정책값을 digest에 결속했지만 허용 버전을 고정하지 않은 것이다. 권장안으로 `REQUIRED_POLICY_VERSION=v1`을 단계 계약과 lesson 규칙에 명시하고 API와 무결성 검사 모두에서 exact match를 요구했다. 대안은 anchor에 allowed-policy registry digest를 결속하는 방식이며 확장성은 높지만 이번 단계에서는 복잡도가 커 후속으로 보류한다. 상수 gate는 최소 변경·저위험·가역적이지만, 향후 정책 변경은 새 stage/snapshot과 명시적 accepted-version 변경을 동반해야 한다. v0·missing·unknown·future 최초 입력과 v0를 scope/nonce/양쪽 input/후속 predecessor/event/docket까지 완전 재해시한 공격을 모두 거부한다.

수정은 packet 후보만 폐기하면 되므로 가역적이며 source schema에는 영향을 주지 않는다. 최종 focused/adjacent/registry 58 PASS, 전체 회귀 1,902 PASS, #9901~#15500 직접 증거계보 14단계와 #7501 역사적 evidence가 통과했다. Evidence SHA-256은 `6c4a8a72b9537ee27b6bf14c8dea02202fed441470c8e0628cd675f5b043e33e`이다.

병합·배포는 수행하지 않았다.
