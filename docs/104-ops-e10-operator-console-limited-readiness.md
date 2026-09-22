# OPS-E10 운영 콘솔·제한운영 전환 준비

가맹점 범위가 강제되는 운영 API로 결제, 격리 Webhook, 정산 Hold, 접근감사를 조회한다. 감사자는 읽기만 가능하고 Webhook 재처리는 Merchant Admin의 `operations:write` 권한을 요구하며 허용 행위를 영속 감사한다. Provider 결제키와 원문 Webhook은 반환하지 않는다.

Production 쓰기는 기본 차단된다. 제한운영은 정확한 가맹점 Cohort, 거래 상한, 외부 승인영수증 SHA-256이 모두 설정된 경우에만 열린다. 이 구현은 전환 절차를 완성하지만 외부 계약, 상용 자격증명, 실제 배포와 금전 이동을 승인하거나 수행하지 않는다.

Rollback은 `NURION_PG_LIMITED_OPERATION_ENABLED`를 제거해 즉시 쓰기 차단하고 기존 조회·감사 증거는 보존한다.
