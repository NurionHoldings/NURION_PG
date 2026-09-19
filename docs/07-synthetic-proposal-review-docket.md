# 합성 제안 검토대장

## 목적

ARKAON이 만든 웹훅 명령 제안을 영속 접수하고 에테르니언 심사 결과까지 증거로 남긴다.
심사를 통과해도 최대 상태는 `READY_FOR_OPERATOR_DECISION`이며 운영자 승인이나 명령 실행은
이 모듈에 존재하지 않는다.

## 상태

- `PENDING_ETERNIAN_REVIEW`: ARKAON 제안이 접수돼 독립심사를 기다림
- `READY_FOR_OPERATOR_DECISION`: 에테르니언 `PASS`; 운영자 판단 대기
- `HELD`: 근거·시험·정책 보완 필요
- `REJECTED`: 제안 거부

`READY_FOR_OPERATOR_DECISION`은 승인·실행 가능 상태가 아니다. 운영자 판단 경계는 별도
기능과 별도 승인 없이는 추가하지 않는다.

## 통제

- 유효한 proposal assessment 사슬과 실제 제안서가 모두 필요
- ARKAON proposer와 에테르니언 reviewer 식별자 분리
- proposal ID·source event·proposal digest·assessment digest 고유제약
- submission·review·상태변경을 한 SQLite 트랜잭션과 audit 사슬로 기록
- review ID exact replay만 멱등 허용하고 변경 재사용 차단
- 동시 review 중 하나의 상태전이만 허용
- audit 실패 시 proposal·review·상태변경 전체 rollback
- audit 사슬이 actor·상태·근거 digest·기록시각 위변조 탐지
- 저장 proposal 원문·review record·audit evidence 사이의 binding 재검증
- 제안 이전 제출시각과 제출 이전 심사시각 차단

## 비범위

합성 reviewer ID는 실제 사람 본인인증이나 전자서명이 아니다. 운영자 결정, 운영 자격증명,
실제 결제·취소·환불·송금·정산, 운영 DB Migration 및 배포를 포함하지 않는다.
