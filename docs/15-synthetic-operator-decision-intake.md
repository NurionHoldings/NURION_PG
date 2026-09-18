# 합성 운영자 결정 봉투 검증

## 목적

운영자 판단 패킷을 대상으로 서명된 **합성 결정 의사 봉투**의 계약과 검증
절차를 시험한다. 이 기능은 실제 최인석 운영자의 결정을 생성·서명·저장하거나
운영 효력을 부여하지 않는다.

## 봉투 계약

- 합성 운영자 ID: `synthetic:operator:CHOI_IN_SEOK`
- 현재 운영자 판단 패킷 ID·SHA-256
- 패킷이 허용한 결정값과 합성 초안 범위
- 필수 확인사항 전체
- 발행시각, 10분 만료시각, 일회성 nonce
- 합성 검증키 ID와 HMAC-SHA256 서명

실제 인증서·비밀번호·운영 토큰·개인정보는 입력할 수 없다. 합성 키 ID와
키 재료는 각각 `synthetic:key:operator-decision:` 및
`synthetic:operator-secret:` 접두어를 강제한다.

## 검증과 실패 폐쇄

- 패킷 만료, 봉투 만료, 30초를 초과한 미래시각을 거부한다.
- 패킷 ID·다이제스트·범위·결정값·필수 확인사항이 다르면 거부한다.
- 미등록·만료·철회·위변조 키와 서명을 거부한다.
- 동일 봉투의 정확한 재전송은 멱등 처리하지만 payload 충돌은 차단한다.
- 다른 봉투에서 nonce가 재사용되면 차단한다.
- 검증 전후 운영자 판단 패킷은 변경되지 않는다.

## 권한 경계

최대 상태는 `SYNTHETIC_DECISION_VALIDATED`다. 이는 합성 계약시험 결과이며
실제 승인·보류·거절 기록이 아니다. 운영 서명 기능, 결정 영속화, 코드 변경,
자동 적용, 결제·자금이동, 병합·배포·운영승격 기능은 제공하지 않는다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_operator_decision_intake -v
PYTHONPATH=src python scripts/run_operator_decision_intake_evidence.py
```

CI 통과는 실제 운영자 승인이나 법적 효력을 의미하지 않는다.
