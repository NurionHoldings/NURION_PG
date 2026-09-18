# 기능 #028 — Patch Draft 제한승격 운영자 판단 패킷

기능 #027에서 에테르니언 독립심사를 통과한 Patch Draft Shadow 증거와 현재의
거버넌스 증거를 최인석 운영자의 재판단 자료로 묶는다. 이 패킷은 판단을 기록하거나
승격을 실행하지 않는다.

## 패킷 내용

- Manifest·사전심사·Shadow 평가·사후심사 SHA-256
- `*_DRAFT_ONLY` 범위, 대상 경로 다이제스트, 항목 결과 다이제스트
- 외부 차단조건·권한정책·승격정책 Snapshot
- 허용 선택지와 필수 확인사항
- 생성시각, 7일 만료 및 이전 패킷과 연결되는 SHA-256 사슬

허용 선택지는 `AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION`, `HOLD`,
`REJECT`뿐이다. 첫 번째 선택도 별도의 다음 계층에서 검증할 합성 제한승격 의사일
뿐이며 실제 승인·코드 변경·병합·배포가 아니다.

## 실패 폐쇄

- 원본 상태가 `READY_FOR_PATCH_DRAFT_OPERATOR_DECISION`이 아니면 생성하지 않는다.
- 평가 원문, 심사, 감사 사슬 또는 거버넌스 Snapshot이 불일치하면 차단한다.
- 모든 Shadow 항목이 `PASS`이고 Manifest·경로 결합이 유지되어야 한다.
- 동일 Shadow에 다른 증거가 제시되면 충돌로 차단한다.
- 생성 후 7일이 지나면 조회를 차단하며 자동 갱신하지 않는다.

## 권한 경계

최대 상태는 `AWAITING_PATCH_DRAFT_PROMOTION_OPERATOR_DECISION`이다. 패치·diff 생성,
소스·파일 변경, 자동 적용, 안전기준 완화, 외부 차단조건 종료, 결제·송금,
자동병합·배포·운영 활성화 메서드는 제공하지 않는다.
