# NURION_PG #19901-#20300 conflict-resolution docket 설계

## 목표

recommendation에 `HOLD_CONFLICT` concurrence가 존재할 때 이를 삭제하거나 덮어쓰지 않고, 정확한 conflict 집합을 봉인한 비실행 resolution docket과 후속 재검토 라운드를 append-only로 기록한다.

## 예정 불변식

- resolution docket은 exact recommendation digest와 conflict-set digest에 결속
- conflict-set은 누락·추가·순서 변경 없이 canonical digest로 봉인
- 기존 concurrence UPDATE/DELETE 금지 유지
- 동일 docket envelope는 1행으로 수렴
- changed conflict set·cross-recommendation·stale round·fork 거부
- round는 predecessor digest에 결속하며 단조 증가
- 해결안 작성자와 독립 재검토자 분리
- conflict를 해결했다고 기록해도 payment·receipt issuance·retry·approval·execution authority는 false
- 실제 실행 전 별도 인간 승인과 이후 단계 증명이 필수

## HOLD 조건

- 원본 recommendation 또는 conflict verdict가 불완전함
- conflict-set digest가 현재 append-only 집합과 다름
- 같은 predecessor에서 둘 이상의 resolution round가 생성됨
- actor separation 위반
- 운영 DB, 통제되지 않은 target 또는 production credential 접근 요구

## 검증 순서

1. 순수 계약 및 identity 부정 테스트
2. disposable PostgreSQL composite FK·unique·trigger 증명
3. 읽기 전용 operator view와 zero-authority 대조
4. ARKAON 교훈 원장·연속 snapshot 갱신
5. 전체 회귀와 원격 PostgreSQL CI

병합·배포·운영 DB 쓰기, 실제 network partition·failover·fault injection은 이 단계 범위가 아니다.
