# 합성 웹훅 명령 제안 경계

## 목적

영속 수신함의 `ACCEPTED` 웹훅을 Payment Intent에 직접 적용하지 않는다. 원본 봉투,
수락 receipt, 현재 Payment Intent snapshot과 정책 digest를 묶은 사람 검토용 제안서만
작성한다.

## 생성 조건

- 영속 수신함의 receipt SHA-256 사슬이 유효할 것
- event 현재 판정이 `ACCEPTED`이고 수락 receipt와 봉투 digest가 일치할 것
- 합성 Payment Intent가 존재할 것
- event 발생 후 10분 이내의 제안일 것
- webhook의 `expected_version`과 현재 Intent version이 일치할 것
- `SUCCEEDED` 결과이고 명령별 현재 상태·금액 조건이 맞을 것

하나라도 맞지 않으면 제안서를 만들지 않고 `HUMAN_REVIEW` 또는 `BLOCKED` 평가만
append-only 사슬에 기록한다. `FAILED` 결과를 임의의 내부 상태로 추측해 변환하지 않는다.

## 합성 내부 매핑

| 합성 event | 검토용 제안 | 필수 상태 |
|---|---|---|
| `AUTHORIZATION_RESULT` | `AUTHORIZE` | `CREATED` |
| `CAPTURE_RESULT` | `CAPTURE` | `SYNTHETIC_AUTHORIZED`, 전액 일치 |
| `CANCEL_RESULT` | `CANCEL` | 매입 전 상태 |
| `REFUND_RESULT` | `REFUND` | 매입 후 상태, 잔여 환불액 이내 |

이 표는 합성 내부시험 계약이며 실제 공급자의 Scheme·event 의미·API Parameter가 아니다.

## 권한 경계

- 제안에는 실행 메서드가 없음
- `review_required=true`
- `automatic_application_allowed=false`
- `operator_approval_recorded=false`
- 제안 생성 전후 Payment Intent의 상태와 version은 동일
- 실제 승인·취소·환불·송금·정산 및 운영승격 불가

추후 실행 경계를 만들더라도 에테르니언 심사와 운영자 승인을 분리하고, 실행 직전에
Intent version·정책 digest·원본 receipt를 다시 검증해야 한다.
