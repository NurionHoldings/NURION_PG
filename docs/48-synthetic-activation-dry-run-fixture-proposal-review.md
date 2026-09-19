# 기능 #048 — 합성 활성화 Dry-run fixture 제안 독립심사

기능 #047의 비생성 fixture 제안을 에테르니언이 별도로 심사하고 `PASS`, `HOLD`,
`REJECT` 결과를 고정한다. `PASS`의 최대 상태는
`READY_FOR_SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFT`이며 fixture 초안 준비만 허용한다.

fixture 내용·파일 생성, Dry-run 실행, 실제 활성화·rollback·결제·정산·송금·외부 API·
파일 변경·병합·배포 메서드는 제공하지 않는다.
