# 운영자 판단 증거 패킷

## 목적

에테르니언 심사를 통과한 합성 Shadow 결과를 최인석 운영자가 직접 검토할 수
있도록 하나의 불변 증거 패킷으로 묶는다. 이 기능은 판단 자료만 만들며 운영자
결정을 기록하거나 대신하지 않는다.

## 패킷 구성

- 원본 보완안·합성 Shadow 평가·에테르니언 심사의 SHA-256
- 합성 평가 항목의 작업유형과 결과 다이제스트
- 외부 차단조건 Registry와 권한·승격 정책의 SHA-256
- 여전히 `PENDING`인 외부 차단조건 ID 전체
- 허용 가능한 운영자 응답 선택지와 필수 확인사항
- 생성시각과 7일 유효기간
- 이전 패킷에 연결되는 append-only SHA-256 사슬

허용 선택지는 다음 문구로 제한한다.

1. `AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT`
2. `HOLD`
3. `REJECT`

첫 번째 선택지도 합성 구현안의 **초안 작성만** 허용하는 의미다. 코드수정,
적용, 병합, 배포, 결제 또는 운영승격을 허가하지 않는다.

## 실패 폐쇄 기준

- 원본 상태가 `READY_FOR_OPERATOR_DECISION`이 아니면 패킷을 만들지 않는다.
- 외부 차단조건 하나라도 자동 종료·완료된 것으로 입력되면 거부한다.
- ARKAON 금지행위 또는 권한분리 정책이 빠지거나 완화되면 거부한다.
- 생성 후 7일이 지나면 `STALE`로 취급해 조회를 차단하며 자동 갱신하지 않는다.
- 원본 대장, 거버넌스 Snapshot 또는 패킷이 위변조되면 실패 폐쇄한다.

## 권한 경계

최대 상태는 `AWAITING_OPERATOR_DECISION`이다. 운영자 결정 기록, 외부 차단조건
종료, 코드 생성·수정, 자동 적용, 결제·환불·송금, 자동병합·배포·운영승격
메서드는 제공하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_operator_decision_packets -v
PYTHONPATH=src python scripts/run_operator_decision_packet_evidence.py
```

CI 결과는 승인이나 운영 권한이 아니다.
