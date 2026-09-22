# OPS-E07 원장·정산·지급

통화와 가맹점별 append-only 복식원장을 구성했다. 모든 Journal은 debit과 credit 합계가 같아야 하며 PostgreSQL deferred constraint가 commit 시 이를 다시 검증한다. Capture는 PG미수금 debit과 가맹점미지급금·플랫폼수익·PG수수료 credit으로 분개하고, refund는 가맹점미지급금 debit/PG미수금 credit으로 분개한다. 수정은 기존 행 변경이 아닌 원분개의 reversal과 새 분개로만 수행한다.

정산은 `draft → review → approved → payable`을 거치며 차이가 발견되면 자동 `held` 처리한다. `held → adjusted → review` 재심사가 가능하다. 지급가능액은 가맹점미지급금에서 pending payout과 reserve/hold를 차감한다.

Payout 내부 경계는 가맹점 격리, 역할 확인, 멱등키, 잔액 잠금, 정산별 잔여 지급한도, 요청자 자기승인 금지, 서로 다른 2인 승인을 적용한다. 은행 송금 Adapter는 연결하지 않았으므로 `paid` 확정과 실제 송금은 차단된다.

Journal과 Outbox는 같은 PostgreSQL transaction에서 기록된다. 운영키, 은행·PG live 호출, 실송금은 수행하지 않았다.
