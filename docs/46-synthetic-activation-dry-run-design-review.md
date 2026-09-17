# 기능 #046 — 합성 활성화 Dry-run 설계 독립심사

기능 #045의 비실행 설계를 에테르니언이 별도로 심사하고 `PASS`, `HOLD`, `REJECT`
결과를 위변조 탐지 사슬에 고정한다. `PASS`의 최대 상태는
`READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSAL`이며 합성 fixture의 제안
준비만 허용한다.

심사는 fixture를 만들거나 실행하지 않는다. Dry-run 실행·실제 활성화·rollback·결제·
정산·송금·외부 API·파일 변경·병합·배포 메서드는 제공하지 않는다.
