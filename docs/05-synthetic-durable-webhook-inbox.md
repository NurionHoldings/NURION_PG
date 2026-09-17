# 합성 영속 웹훅 수신함

## 목적

프로세스 재시작 뒤에도 웹훅 event ID·nonce·aggregate sequence·격리 상태가 사라지지
않도록 합성 SQLite 수신함에 트랜잭션으로 고정한다. 이 수신함은 실제 PG 연결이나
Payment Intent 자동 반영 경로가 아니다.

## 원자적 처리

- `BEGIN IMMEDIATE` 트랜잭션 안에서 중복조회, event 저장, cursor 변경, receipt 기록 수행
- event ID, provider+nonce, aggregate+sequence, receipt digest에 DB 고유제약 적용
- receipt 기록이 실패하면 event와 cursor 변경도 함께 rollback
- receipt 사슬이 판정·사유·봉투 digest·기록시각 위변조를 탐지
- 두 연결의 동시 exact replay에서도 한 건만 `ACCEPTED`, 나머지는 `DUPLICATE`
- 재시작 뒤 exact replay·nonce 재사용·sequence 충돌을 동일하게 차단

## 격리 복구

순서역전 event는 `QUARANTINED` 상태로 영속화한다. 재시작 뒤 앞선 sequence가 접수돼도
자동 적용하지 않으며, 명시적 retry에서 서명·payload·event 시간·현재 key 상태를 다시
검증한 뒤에만 `ACCEPTED`로 바꾼다. 허용시간 만료나 key 철회·만료는 `BLOCKED`다.
저장된 봉투가 훼손돼 역직렬화 또는 원래 digest 검증에 실패해도 `BLOCKED`로 기록한다.

## 데이터 경계

- `:memory:` 또는 파일명이 `synthetic-`으로 시작하는 SQLite만 허용
- URI·서버 DB 연결문자열 차단
- 실제 provider·개인정보·운영 secret·결제정보 사용 금지
- receipt와 evidence 어디에도 DB 절대경로를 기록하지 않음
- 수신 성공은 결제 성공·금전이동·운영승인을 의미하지 않음

## 후속 차단조건

이 구현은 합성 SQLite 증거이며 운영 DB 선택이나 운영 Migration 승인이 아니다.
실제 인프라 전에는 공식 보안·감독 요구사항, 데이터 보존기간, 암호화·키관리,
백업·복구, 다중 노드 격리수준, 관측성 및 독립 부하·장애시험이 필요하다.
