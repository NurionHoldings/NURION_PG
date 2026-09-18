# 기능 #055 — 합성 fixture 물질화 Dry-run 비실행 계획

기능 #054에서 독립심사를 통과한 specification으로부터 기존 계보 digest와
`materialization_executed=false`, `dry_run_executed=false`인 contract digest만 고정한다.

최대 상태는 `SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_DRY_RUN_PLAN_DRAFTED`이며
별도 에테르니언 심사를 요구한다. Fixture 내용·bytes·경로·파일을 만들거나 기록하지 않고,
물질화 Dry-run·활성화·rollback·결제·외부 API·병합·배포를 수행하지 않는다.
