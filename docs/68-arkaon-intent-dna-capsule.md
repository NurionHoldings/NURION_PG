# 68 — ARKAON Intent DNA Lock Capsule

Foundry `apf.public.intent-dna-lock`를 PG 합성 평가용 선언형 캡슐로 결속한다.

- 승인된 intent fingerprint 없이는 검증 상태를 만들지 않는다.
- 캡슐 자체 SHA-256 결속으로 정책 변조를 실패 폐쇄한다.
- 최대 상태는 `SYNTHETIC_INTENT_DNA_CAPSULE_VALIDATED`이다.
- 운영, 결제, 네트워크, 배포, 병합 권한을 만들지 않는다.
