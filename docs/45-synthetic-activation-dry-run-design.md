# 기능 #045 — 합성 활성화 Dry-run 비실행 설계

기능 #044에서 `PASS`된 에테르니언 심사 기록만 받아 후속 합성 Dry-run의 범위와 안전
게이트를 메타데이터로 고정한다. 후보·평가군·표본·관찰창·관찰결과·rollback 조건은
원본 초안에서 변경하지 않는다.

최대 상태는 `SYNTHETIC_ACTIVATION_DRY_RUN_DESIGNED`다. 별도 심사 전에는 합성 fixture
Dry-run도 실행할 수 없다. 실제 활성화·rollback·결제·정산·송금·외부 API·파일 변경·
병합·배포 메서드는 제공하지 않는다.
