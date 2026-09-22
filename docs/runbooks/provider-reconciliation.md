# Provider reconciliation

Webhook 격리 증가 시 event digest, merchant, order, payment key의 마스킹 식별자만 사용한다. Provider 조회 결과와 내부 금액·상태가 일치하지 않으면 자동 적용하지 않고 hold한다.
