# Payment worker

Dead-letter 또는 lease 적체 시 신규 dispatch를 중지하고 Provider 조회 대사를 먼저 수행한다. 결제 성공을 추정하지 않는다. Operation·Payment Intent·Outbox·원장 Journal을 대조하고, 이중승인 후 격리 해제한다.
