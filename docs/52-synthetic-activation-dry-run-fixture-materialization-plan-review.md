# 기능 #052 — 합성 활성화 Dry-run fixture 물질화 계획 독립심사

기능 #051의 metadata-only 물질화 계획을 에테르니언이 별도로 심사해 `PASS`,
`HOLD`, `REJECT` 결과를 불변 기록한다. `PASS`의 최대 상태는
`READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_MATERIALIZATION_SPECIFICATION`이며
비실행 specification 준비만 허용한다.

Fixture 내용·bytes·파일 생성과 filesystem 기록, Dry-run 실행, 실제 활성화·rollback·
결제·외부 API·병합·배포 메서드는 제공하지 않는다.
