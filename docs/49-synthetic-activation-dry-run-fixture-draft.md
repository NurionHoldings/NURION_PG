# 기능 #049 — 합성 활성화 Dry-run fixture 비물질화 초안

기능 #048에서 `PASS`된 제안 심사만 받아 schema·입력·기대결과·rollback digest를
하나의 blueprint digest로 고정한다. fixture 내용은 직렬화하지 않고 파일도 만들지 않는다.

최대 상태는 `SYNTHETIC_ACTIVATION_DRY_RUN_FIXTURE_DRAFTED`다. 별도 심사 전에는 fixture
생성도 허용하지 않는다. Dry-run 실행·실제 활성화·rollback·결제·외부 API·파일 변경·
병합·배포 메서드는 제공하지 않는다.
