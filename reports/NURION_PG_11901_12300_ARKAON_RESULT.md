# NURION_PG #11901~#12300 ARKAON 결과

## 아르카온 선행 결정

단계명은 **반사실 판단준비 스트레스테스트**다. #11501~#11900은 판단에 필요한 항목과 복수 대안을 마련했지만, 대안별 가정·반증시험·중단조건이 독립된 원천결속 레코드가 아니었다. 따라서 다음 계층은 판단을 내리는 대신 각 극복안이 어떤 조건에서 실패하는지를 먼저 증명하도록 설계했다.

## 자가감사와 교훈

- 발견: `ETH-11501-AUDIT-001`
- 교훈: `ARL-11501-001`
- 결함: 대안 수만 검사하면 실질적으로 같은 선택지를 둘로 표시하거나 숨은 가정을 남길 수 있다.
- 수정: 원천 review와 판단준비 packet에 직접 결속된 서로 다른 두 option profile, 미검증 assumption register, option별 disconfirming test와 stop condition을 canonical digest로 고정한다.
- HOLD 보완: 변경 row뿐 아니라 모든 후속 parent·event·hold·최종 docket을 정합 재해시하는 공격을 구성했다. 내장 SourceBundle은 anchor·ordered reviews·docket을 이용해 이전 계층 validator를 재구성하여 매번 전체 의미 무결성을 다시 검사한다. 이전 judgment packet부터 downstream까지 전부 재해시한 공격도 거부한다.

## 안전 경계

정확히 400개 통제(16×25), 4개 N/A 보존, 16개 인간판단 hold, append-only event/hold, partial-batch fail-closed를 적용한다. ARKAON은 수정방향·복수 극복안·검증기준·잔여위험·escalation/rollback만 준비하며 순위화·선택·결론·추천·수락·해결·승인·활성화·배포는 하지 않는다. 외부·PG·금융·원장·자격증명·배포 작업은 모두 0이다.
