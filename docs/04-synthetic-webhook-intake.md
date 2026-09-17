# 합성 웹훅 격리 수신

## 목적

외부 결제 결과처럼 보이는 입력을 즉시 신뢰하거나 Payment Intent에 자동 반영하지 않고,
서명·키·시간·스키마·중복·순서를 먼저 검증하는 격리 경계다.

## 수신 판정

- `ACCEPTED`: 봉투 무결성과 순서가 검증됨. 결제 적용 승인이 아님.
- `DUPLICATE`: 동일 event ID와 동일 서명의 정확한 재전송.
- `QUARANTINED`: 앞선 sequence가 도착하지 않아 격리됨.
- `BLOCKED`: 위변조, key 오류, nonce 재사용, event ID 충돌, 만료, PII 또는 스키마 위반.

순서역전 이벤트는 앞선 sequence가 정상 접수된 뒤 내부 재검증을 거쳐서만 격리 해제된다.
격리 중 key가 철회·만료되거나 event 허용시간이 지나면 해제하지 않는다.

## 보호 장치

- 합성 `.invalid` 공급자와 `synthetic:` key·event·nonce·aggregate만 허용
- HMAC-SHA256 및 constant-time 비교
- key 유효기간·철회·provider/key binding
- event ID·nonce·aggregate sequence 재전송 통제
- 카드·계좌·주민번호·이름·이메일·전화·주소·좌표·token·secret 필드 차단
- 허용 event type별 정확한 payload field 집합
- canonical JSON 강제 및 실제 UTF-8 byte 크기 제한
- append-only SHA-256 수신 영수증 사슬

## 비범위

네트워크 Listener, 실제 Provider Scheme, 운영 인증서·secret, Payment Intent 자동 변경,
실결제·환불·송금·정산은 포함하지 않는다. 실제 Provider 계약과 Sandbox 공식문서가
확보되기 전까지 Endpoint·header·parameter를 추측해 추가하지 않는다.
