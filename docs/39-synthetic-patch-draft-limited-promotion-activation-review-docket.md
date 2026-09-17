# 기능 #039 — 합성 제한승격 활성화 Manifest 최종심사 대장

기능 #038의 사전점검 Manifest 원문과 에테르니언 최종심사를 SQLite 대장에
영속 고정한다. PASS는 다음 운영자 판단 자료를 만들 수 있는 상태일 뿐 활성화나
운영자 승인을 의미하지 않는다.

## 상태

`PENDING_ETERNIAN_FINAL_REVIEW → READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION`

보류와 거절은 각각 `HELD`, `REJECTED`로 분리한다. 자동심사와 기준 완화는 없다.

## 무결성

- Manifest 전체 JSON·SHA-256과 수신증·패킷·Shadow·계획 계보를 보존한다.
- 제출과 최종심사를 append-only 감사사슬에 기록한다.
- 동일 제출·심사의 정확한 재전송만 멱등 처리한다.
- 저장행·Manifest 원문·감사행의 변조를 차단한다.
- 저장과 감사 기록은 단일 트랜잭션이며 실패 시 rollback한다.
- 재시작 후에도 전체 결합과 상태를 재검증한다.

## 권한 경계

최대 상태는 `READY_FOR_SYNTHETIC_LIMITED_PROMOTION_OPERATOR_DECISION`이다.
운영자 판단 기록, 합성 활성화, rollback 실행, 코드·patch·diff 생성, 파일 변경,
결제·정산, 외부 차단조건 종료, 병합·배포 또는 운영 승격 메서드는 없다.
