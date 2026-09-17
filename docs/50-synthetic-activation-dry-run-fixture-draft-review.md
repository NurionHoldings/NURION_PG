# 기능 #050 — 합성 활성화 Dry-run fixture 초안 독립심사

기능 #049의 비물질화 fixture 초안을 에테르니언이 별도로 심사해 `PASS`, `HOLD`,
`REJECT` 결과를 고정한다. `PASS`의 최대 상태는
`READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_PLAN`이며 물질화 계획의
준비만 허용한다.

fixture 물질화·생성·파일 기록, Dry-run 실행, 실제 활성화·rollback·결제·외부 API·
병합·배포 메서드는 제공하지 않는다.
