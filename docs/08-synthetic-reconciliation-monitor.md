# 합성 정합성 감시

기능 #008은 합성 Payment Intent, 균형원장, 영속 웹훅 수신함, ARKAON 명령
제안, 에테르니언 검토대장의 연결을 읽기 전용으로 검사한다. 불일치를 고치지
않고 근거가 고정된 보완 제안만 만든다.

## 검사 범위

- Payment Intent 최종 상태·버전·포착액·환불액과 이벤트 사슬 일치
- 포착·환불 이벤트와 합성 원장 journal의 식별자·계정·금액·통화·정책 일치
- 수락 웹훅과 접수증, ARKAON 평가, 제안, 검토대장의 SHA-256 연결
- 웹훅 접수증, 제안 평가, 검토대장 감사 사슬 및 저장 레코드 무결성
- 검사 전후 component snapshot digest 비교를 통한 비변경 증명

`WARNING`은 에테르니언 검토가 필요한 미완료 연결이다. 사슬 훼손이나 상충은
`BLOCKED`로 실패 폐쇄한다. 보고서에는 자동수정, 운영자결정, 결제상태 변경,
실제 자금이동 및 운영승격이 모두 `false`로 고정된다.

## 명시적 비기능

감시기는 수정·재처리·승인·실행 메서드를 제공하지 않는다. 운영 DB, 실제
개인정보, 결제수단, 자격증명, 공급자 API 및 네트워크에 연결하지 않는다.
에테르니언은 결과를 독립 심사할 수 있지만 운영자 결정을 대신할 수 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_reconciliation_monitor -v
PYTHONPATH=src python scripts/run_reconciliation_monitor_evidence.py
```
