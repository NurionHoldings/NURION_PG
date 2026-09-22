# OPS-E04 — Payment Intent 운영 API (100%)

## 제공 범위

- 가맹점별 Payment Intent 생성·조회
- 승인·매입·취소·환불 요청 API
- API Key 인증, Payment 권한, 가맹점 격리
- 원 단위가 아닌 통화 최소단위 정수 금액과 ISO 형식 통화코드
- 생성 및 모든 명령의 `Idempotency-Key` 충돌 검증
- `expected_version` 기반 낙관적 동시성 제어
- 승인·매입·취소·환불 상태기계와 매입·환불 상한
- Payment, Operation, Outbox, 명령 영수증의 단일 PostgreSQL 트랜잭션
- 처리 중인 Provider 명령의 추월 금지와 Provider 결과 상태 일치 검증
- Provider 성공·실패 적용 시 Payment·Operation·완료 Outbox의 단일 트랜잭션
- `NURION_PG_DATABASE_URL` 설정 시 마이그레이션·영속 인증·Payment 저장소 자동 연결과 종료 시 연결 정리

## 응답 계약

- 최초 생성 `201`, 동일 요청 재생 `200`
- 최초 비동기 명령 `202`, 동일 요청 재생 `200`
- 잘못된 상태·버전·멱등 충돌 `409`
- 입력 불변식 위반 `422`, 다른 가맹점 또는 권한 부족 `403`
- 모든 외부 실행 요청은 `*_pending`까지만 진행한다.

진행 중인 승인 요청에 취소 요청을 겹쳐 넣을 수 없다. 내부 Adapter 결과도 해당 명령의 `*_pending` 상태와 일치할 때만 적용하며, 실패 결과는 금액 불변식을 유지한 채 직전의 안정 상태로 복구되어 새 멱등키로 재시도할 수 있다.

## 안전 경계

공개 API에는 provider 성공 결과를 기록하는 경로가 없다. 내부 Adapter 경계만 provider 결과를 적용할 수 있으며, OPS-E05에서 실제 연동 서명·재시도·웹훅 검증을 별도로 종결하기 전에는 실제 승인·취소·환불을 수행하거나 성공으로 표시하지 않는다.
