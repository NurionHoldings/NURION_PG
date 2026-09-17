# 패치 초안 운영자 판단 패킷

## 목적

기능 #020에서 에테르니언 심사를 통과한 패치 Shadow 증거를 최인석 운영자가
검토할 수 있도록 하나의 불변 패킷으로 묶는다. 이 계층은 판단 자료만 만들며
운영자 결정을 기록하거나 패치 초안을 생성하지 않는다.

## 패킷 구성

- 구현제안·구현심사·패치 Shadow 평가·Shadow 심사의 SHA-256
- 범위별 `*_DRAFT_ONLY` 식별자와 결과 다이제스트
- 외부 차단조건 Registry와 권한·승격 정책의 SHA-256
- `PENDING` 외부 차단조건 ID 전체
- 제한된 운영자 선택지와 필수 확인사항
- 생성시각·7일 유효기간·이전 패킷에 연결되는 SHA-256 사슬

허용 선택지는 다음 세 가지다.

1. `AUTHORIZE_SYNTHETIC_PATCH_DRAFT`
2. `HOLD`
3. `REJECT`

첫 번째 선택도 합성 패치 초안 작성을 다음 단계에서 검토할 수 있게 하는
의사표현일 뿐, 소스 변경·적용·병합·배포·결제·운영승격을 허가하지 않는다.

## 실패 폐쇄 기준

- 원본 상태가 `READY_FOR_OPERATOR_DECISION`이 아니면 생성하지 않는다.
- 선행 대장·평가 원문·심사·거버넌스 Snapshot 위변조를 거부한다.
- 외부 차단조건이 자동 종료되거나 권한·직무분리 정책이 완화되면 거부한다.
- 생성 후 7일이 지나면 조회를 차단하며 자동 갱신하지 않는다.
- 같은 Shadow에 다른 거버넌스 증거가 제시되면 충돌로 차단한다.

## 권한 경계

최대 상태는 `AWAITING_OPERATOR_DECISION`이다. 운영자 결정 기록, 패치본문 생성,
코드 변경, 자동 적용, 안전기준 완화, 외부 차단조건 종료, 결제·환불·송금,
자동병합·배포·운영승격 메서드는 제공하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_patch_operator_decision_packets -v
PYTHONPATH=src python scripts/run_patch_operator_decision_packet_evidence.py
```

CI 결과는 승인이나 운영 권한이 아니다.
