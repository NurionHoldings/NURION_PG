# NURION_PG #13101~#13500 에테르니언 독립검수

## 결론

**수락 — PR 생성 가능, 병합·배포 불가.**

아르카온의 `자동 스냅샷 체인·미확정 원인 진단 프리플라이트`를 독립 검수했다. 최초 제출은 source evidence가 아니라 case 순번으로 네 원인을 순환 배정하여 `HOLD`했다. 에테르니언은 증거기반 분류와 비판정 진단행렬 두 경로를 제시했고, 아르카온은 source에서 확정 가능한 신호가 없음을 정직하게 보존하는 안전한 비판정 경로를 구현했다.

## 확인 결과

- stage snapshot mapping의 범위 연속성·비중복·lesson 단조 증가를 자동 검증한다.
- 400 controls, 20 audits(4 N/A+16 routed), 32 read-only 진단 options, 16 append-only 인간판단 hold를 확인했다.
- routed row마다 guidance digest·challenge digest·snapshot digest·rejection reason·4개 `NOT_RUN` probe·비변경 선언을 `cause_evidence`에 결속한다.
- probe가 모두 PASS/FAIL이고 정확히 하나만 PASS일 때만 원인을 확정한다. 현재는 probe 미실행이므로 16건 모두 `CAUSE_UNDETERMINED`로 유지한다.
- 진단 최소안과 독립 원인 재검증안을 제공하며 가정·반증·중단·preflight·검증·잔여위험·비용/위험/가역성·escalation·rollback/resume을 결속한다.
- 강제 원인·근거 삭제·미확정 원인 승격·probe PASS 위조·대안 복제·preflight 삭제·source 변조의 전체 downstream 재해시 공격을 거부한다.
- 동일 row는 멱등이고 충돌 row·중복 ID는 거부한다.
- 결론·추천·선택·수락·해결·승인·활성화·배포 및 외부·PG·금융·원장·자격증명 실행은 모두 0이다.

## 독립 재검증

- 전용·인접·registry: 56 PASS
- 전체 회귀: 1,781 PASS
- 9단계 연속 evidence: PASS
- governance/lesson registry/compileall/diff-check: PASS
- Evidence SHA-256: `f5ae6e65d3fb0ce4a9716c03c090b0fde23673f60eb1a64c9b492bb8f8988d29`

## 잔여 위험

현재 원인 probe는 의도적으로 실행되지 않았다. 따라서 이 단계는 원인을 해결하거나 특정 경로를 추천하지 않으며, read-only 진단 준비와 인간 판단 hold만 증명한다. 실제 probe 실행·원인 확정·복구경로 선택은 별도 승인과 독립 검증이 필요하다.
