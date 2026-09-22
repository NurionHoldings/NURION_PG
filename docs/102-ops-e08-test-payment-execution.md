# OPS-E08 실제 승인·취소·환불 실행 체계

Toss **테스트키**와 공식 Toss HTTPS 또는 loopback Emulator만 허용하는 production-shaped worker를 구성했다. 임의 HTTPS 호스트로 테스트키가 유출되지 않도록 endpoint를 제한한다. Operation은 PostgreSQL에서 `SKIP LOCKED`로 lease되며 bounded backoff, dead-letter, lease 만료 후 재시작 복구를 지원한다.

승인 전 내부 callback은 paymentKey를 가맹점·Operation·orderId·amount와 대조해 감사·Outbox와 한 트랜잭션에서 결합한다. 외부 승인이 시작되지 않은 결제의 취소는 로컬에서 즉시 종결해 provider key 없는 pending 작업을 남기지 않는다. Toss confirm의 `DONE`은 승인과 매입이 끝난 단일단계 결제로 처리하며 별도 capture API를 지원한다고 주장하지 않는다. 취소·환불은 기존 paymentKey를 상속하고 환불금액과 사유를 전달한다.

Timeout이나 불확실 응답 후에는 재호출보다 조회 대사를 먼저 수행한다. terminal 성공만 Payment Intent에 반영하고, `DONE`과 refund 성공은 Operation ID 기반 결정적 Journal로 정확히 한 번 분개한다. 실패·UNKNOWN에는 원장을 기록하지 않는다.

로컬 HTTP Emulator로 승인→취소 및 별도 승인→부분환불→전액환불→조회를 실제 왕복 검증했다. 외부 Toss live 호출, 운영키, 상용 금전거래는 수행하지 않았다.
