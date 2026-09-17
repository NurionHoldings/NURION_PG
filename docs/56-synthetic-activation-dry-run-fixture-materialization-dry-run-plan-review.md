# 기능 #056 — 합성 fixture 물질화 Dry-run 계획 독립심사

기능 #055의 비실행 Dry-run 계획을 에테르니언이 별도로 심사해 `PASS`, `HOLD`,
`REJECT` 결과를 불변 기록한다. `PASS`의 최대 상태는
`READY_FOR_SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_SCENARIO_DRAFT`이며
내용 없는 합성 scenario 초안 준비만 허용한다.

Fixture 물질화·filesystem 기록·Dry-run 실행, 활성화·rollback·결제·외부 API·
병합·배포 메서드는 제공하지 않는다.
