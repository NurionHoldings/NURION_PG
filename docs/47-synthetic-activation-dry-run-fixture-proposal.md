# 기능 #047 — 합성 활성화 Dry-run fixture 비생성 제안

기능 #046에서 `PASS`된 설계 심사만 받아 fixture schema, 합성 입력, 기대 결과,
rollback 기대조건의 다이제스트를 제안한다. fixture 내용이나 파일은 만들지 않는다.

최대 상태는 `SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_PROPOSED`다. 별도 에테르니언 심사
전에는 fixture 생성도 허용하지 않는다. Dry-run 실행·실제 활성화·rollback·결제·정산·
송금·외부 API·파일 변경·병합·배포 메서드는 제공하지 않는다.
