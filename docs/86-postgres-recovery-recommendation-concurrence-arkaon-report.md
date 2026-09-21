# NURION_PG #19501-#19900 ARKAON 선행 구현 보고

## 결론

exact review receipt에 action·risk digest와 독립 author를 결속한 비실행 recovery recommendation, 그리고 독립 reviewer들의 concurrence/conflict 기록을 구현했다. 하나라도 `HOLD_CONFLICT`이면 recommendation은 계속 비실행 HOLD다.

## 안전 계약

- recommendation은 exact `(receipt_id, receipt_digest)` 복합 FK에 결속
- author와 reviewer 동일인 금지
- recommendation별 reviewer당 verdict 1개
- 동일 envelope 수렴, changed action·cross-receipt·self-review·동일 reviewer 재판정 거부
- recommendation·concurrence UPDATE/DELETE 거부
- operator view DML 거부 및 read-only 검증
- payment·receipt issuance·retry·approval·execution authority 모두 false

## 에테르니언 검수 요청

disposable PostgreSQL에서 composite FK, actor separation, reviewer unique, conflict HOLD, append-only와 zero-authority를 독립 검수한다. merge·deploy·production write는 별도 승인 전 수행하지 않는다.
