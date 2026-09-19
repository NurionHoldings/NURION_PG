# Synthetic Recovery Quarantine #1101–#1300

복구 검증을 통과한 합성 패킷이라도 즉시 재개하지 않고 격리·탐침·독립 검토·
냉각시간·발급 증명·재사용 차단을 거쳐 합성 해제 관찰 상태로 이동시킨다.
외부 전달과 결제 효과는 일절 발생하지 않는다.

| 범위 | Workstream | 핵심 계약 |
|---|---|---|
| #1101–#1125 | QUARANTINE_INTAKE | recovery receipt 결속, 입력 멱등·충돌 차단 |
| #1126–#1150 | BOUNDED_PROBE_SCHEDULING | 위험도 우선 결정론, 배치 최대 20 |
| #1151–#1175 | INDEPENDENT_PROBE_REVIEW | 탐침자와 검토자 역할 분리 |
| #1176–#1200 | COOLDOWN_ENFORCEMENT | 5분 이상 24시간 이하 냉각시간 |
| #1201–#1225 | RELEASE_ATTESTATION | 제3 역할의 합성 해제 증명 |
| #1226–#1250 | REPLAY_PREVENTION | attestation digest 단일 패킷 귀속 |
| #1251–#1275 | EMERGENCY_HOLD | 전역 합성 hold와 독립 해제 |
| #1276–#1300 | AUDIT_EVIDENCE | history·event·receipt·batch·hold 무결성 |

## 상태 경계

`QUARANTINED → PROBE_RESERVED → PROBE_PASSED → REVIEW_APPROVED →
RELEASE_ATTESTED → SYNTHETIC_RELEASED`만 허용한다. 탐침 실패 또는 검토 거부는
`HELD`로 실패 폐쇄한다. `SYNTHETIC_RELEASED`는 외부 전달·운영 승인·결제 결과가
아니며 테스트 안에서만 사용되는 관찰 상태다.

해제 전에는 탐침자·검토자·증명 발급자가 서로 달라야 한다. 활성 emergency hold가
있으면 새 증명 발급과 최종 해제가 모두 차단된다. 증명 digest는 다른 패킷에 재사용할
수 없다.

## 절대 금지

- 자동 승인, 실제 카드망·외부 PG API 또는 외부 전달
- 실제 결제·승인·취소·환불·정산·송금과 원장 반영
- 운영 자격증명 접근, production outcome 기록
- 운영 정책·Prompt·가중치 자동 변경
- Pattern 승격, 코드 병합, 자동병합 및 배포

CI 성공은 운영 준비나 금지 행위에 대한 승인을 뜻하지 않는다.
