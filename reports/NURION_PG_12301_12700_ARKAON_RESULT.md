# NURION_PG #12301~#12700 ARKAON 결과

## 아르카온의 단계 결정

- 단계명: `원천결속 극복방법론 독립챌린지`
- 이유: #11901~#12300은 선택지별 가정·반증·중단조건을 결속했지만 검증기준·잔여위험·escalation·rollback은 사례 공통 묶음이었다. 따라서 개별 수정방향의 위험이나 rollback을 숨기고 외곽 digest를 전면 재계산하는 우회를 차단할 다음 계층이 필요했다.

## 수정방향과 극복방안

- `CORRECT_AND_REVALIDATE`: 정정 초안만 준비하고 가정 증명·부정시험·회귀검증·인간 owner 확인이 모두 충족되지 않으면 중단한다.
- `PRESERVE_AND_ESCALATE`: 원천을 보존하고 독립 증거 챌린지로 이관하며 인간 scope 거부 또는 미검증 가정이 남으면 hold를 지속한다.
- 두 방안 모두 가정, 반증시험, 중단조건, 검증기준, 잔여위험, escalation, rollback을 해당 option/source/stress digest와 함께 하나의 방법론 카드에 결속했다.

## 자기감사와 방지책

- lesson: `ARL-12301-001`
- remediation: `ETH-12301-AUDIT-001`
- 공통 검증기준 치환, source 재결속, rollback 삭제, 단일 방법 축소, 이전 source 변조 후 downstream 전체 재해시 공격을 fail-closed 음성시험으로 등록했다.
- 에테르니언 HOLD 후 source metadata(registry/manifest/sequence/latest/lessons/rules)와 final docket namespace/state/status/authority를 사후에도 완전 재검증하도록 강화했다. 각 필드를 변조한 뒤 anchor/event/challenge/docket을 정합 재해시하는 공격에서도 integrity와 complete 판정이 모두 false임을 확인했다.

## 경계와 결과

- controls: 정확히 400개(16×25)
- challenges: 20개(4 N/A + 16 routed)
- content-addressed methodology cards: 32개
- append-only 인간판단 hold: 16개
- 순위화·선택·결론·추천·수락·해결·승인·활성화·배포 권한: 없음
- 외부/PG/card network/금융/원장/credential/deployment 동작: 0
- 상태: 에테르니언 독립검수 요청, 승인 아님

## 검증

- 전용/인접/lesson suite: 50 PASS
- 전체 회귀: 1,732 PASS
- governance: PASS
- lesson registry: PASS, 23 lessons
- compileall / diff-check: PASS
- evidence SHA-256: `146a6da1a85efa6689770cb930ebe073afe1d77bb2342193a6f44599fc9bd52a`
