# 기능 #043 — 합성 제한승격 활성화 비실행 초안

기능 #042의 `AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION` 수신증과 현재 #040
패킷을 다시 결합해 합성 fixture Dry-run을 위한 메타데이터 초안만 만든다.

초안은 최종심사 Manifest, 후보·평가군, 표본 수, 관찰창·관찰결과, rollback 조건을
그대로 고정한다. `HOLD`·`REJECT`, 만료 패킷, 변조·불일치 출처는 실패 폐쇄한다.

최대 상태는 `SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_DRAFTED`다. 에테르니언의 별도
심사 전에는 Dry-run 준비조차 허용하지 않는다. 코드·patch·diff·파일을 만들거나
변경하지 않으며 실제 활성화, rollback, 결제·정산, 병합·배포 메서드는 없다.
