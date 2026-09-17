# 합성 패치 운영자 결정 의사 검증

## 목적

기능 #021의 패치 운영자 판단 패킷을 대상으로 서명된 합성 결정 의사 봉투의
계약과 검증 절차를 시험한다. 실제 최인석 운영자의 결정을 생성·서명·저장하거나
패치 작성 권한을 부여하지 않는다.

## 봉투 계약

- 합성 운영자 ID: `synthetic:operator:CHOI_IN_SEOK`
- 현재 패치 판단 패킷 ID·SHA-256
- 패킷이 허용한 결정값과 `SYNTHETIC_PATCH_DRAFT_ONLY` 범위
- 필수 확인사항 전체
- 발행시각, 10분 만료시각, 일회성 patch nonce
- 합성 검증키 ID와 HMAC-SHA256 서명

실제 인증서·비밀번호·운영 토큰·개인정보를 받지 않는다. 검증키와 키 재료는
각각 `synthetic:key:operator-decision:` 및 `synthetic:operator-secret:` 접두어를
강제한다.

## 검증과 실패 폐쇄

- 패킷·봉투 만료와 30초를 초과한 미래시각을 거부한다.
- 패킷 ID·다이제스트·범위·결정값·필수 확인사항 불일치를 거부한다.
- 미등록·만료·철회·위변조 키와 HMAC 서명을 거부한다.
- 동일 봉투의 정확한 재전송만 멱등 처리하고 payload 충돌을 차단한다.
- 다른 봉투의 nonce 재사용과 nonce 색인 위변조를 차단한다.
- 평가 ID와 append-only 평가 사슬을 재계산하며, 검증 전후 패킷은 변경하지 않는다.

## 권한 경계

최대 상태는 `SYNTHETIC_PATCH_DECISION_VALIDATED`다. 이는 합성 계약시험
결과일 뿐 실제 승인·보류·거절 기록이 아니다. 운영 서명, 결정 영속화,
패치본문 생성, 코드 변경·적용, 결제·자금이동, 병합·배포·운영승격 기능은 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_patch_operator_decision_intake -v
PYTHONPATH=src python scripts/run_patch_operator_decision_intake_evidence.py
```

CI 통과는 실제 운영자 승인이나 법적 효력을 의미하지 않는다.
