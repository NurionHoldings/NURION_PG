# OPS-E05 외부 PG/VAN 연동 경계

## 완료 범위

Provider-neutral `PaymentProvider` SPI와 Toss Payments Core API 참조 어댑터를 구현했다. Toss 경계는 Basic 인증, 승인(`/v1/payments/confirm`), 취소·환불(`/v1/payments/{paymentKey}/cancel`), 조회를 지원한다. HTTP transport를 주입하므로 실 네트워크 없이 계약 테스트할 수 있다.

Toss Core의 `confirm`은 별도 매입 전 승인만 하는 API가 아니라 결제를 완료해 `DONE`으로 만드는 단일 단계 흐름이다. 따라서 성공 결과는 Payment Intent의 승인금액과 매입금액을 함께 반영해 `captured`로 종결한다. 별도 `capture` 명령은 지원한다고 가장하지 않고 안전하게 거절한다.

`operation_id`를 Provider 멱등키로 사용한다. timeout/5xx/429는 제한적으로 재시도하며 결과를 확정할 수 없는 transport 오류는 성공이나 실패로 기록하지 않고 `UNKNOWN`으로 남겨 조회 reconciliation 대상으로 보낸다. terminal 응답만 PostgreSQL의 `apply_provider_result`에 연결되어 Payment Intent, Operation, Outbox가 한 트랜잭션에서 완료된다.

응답은 status/paymentKey/안전한 오류코드만 보관한다. 카드·개인정보·원문 오류·Authorization 값은 저장하거나 로그에 싣지 않는다. webhook은 allowlist 증거로만 수집하며 직접 결제상태를 변경하지 않는다.

## 운영 차단

이 단계는 Sandbox-ready 구현이다. 운영 secret은 구성하지 않았고 실제 승인·취소·환불·조회 네트워크 호출은 수행하지 않았다. 상용계약, 운영키 주입, webhook 진위검증 방식 확정, 운영 승인 전에는 live traffic을 허용하지 않는다.
