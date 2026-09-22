# OPS-E06 Webhook·재처리·대사

Provider webhook은 결제 성공 명령이 아니라 **검증 전 증거**로 수신한다. 원문 자체는 저장하지 않고 SHA-256, 수신시각, 공급자 중복키, 가맹점, 결제키·주문키·상태의 허용 필드만 PostgreSQL inbox에 영속화한다. 카드·개인정보와 원문 오류는 저장하지 않는다.

Toss webhook에 지원되지 않는 서명 검증을 구현했다고 주장하지 않는다. 출처와 최신 상태는 test-key API 조회로 검증하며 조회 결과만 권위값으로 사용한다. 따라서 중복·순서역전·지연 webhook도 과거 payload로 Payment Intent를 덮어쓰지 않는다.

조회 결과의 결제키·주문키가 다르거나 pending operation이 없거나 결과가 UNKNOWN이면 격리한다. 재처리는 지수형 bounded backoff와 운영자 승인 경계를 거친다. 검증 완료 시 기존 `apply_provider_result`를 통해 Payment Intent, Operation, Outbox가 원자적으로 반영된다.

worker claim은 inbox 식별자만 반환하지 않고 정규화된 영속 증거를 함께 반환하므로, 프로세스 재시작 이후에도 메모리 payload에 의존하지 않고 동일한 조회 대사를 수행할 수 있다.

이 단계는 Sandbox-ready다. 운영키, live webhook, 실결제는 사용하지 않았다.
