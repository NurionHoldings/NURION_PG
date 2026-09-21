# NURION_PG #15501~#15900 ETHERNian 독립검수 요청

## 검수 대상

- `src/nurion_pg/synthetic_nonissuance_result_seal_reservation.py`
- `tests/test_synthetic_nonissuance_result_seal_reservation.py`
- `scripts/run_synthetic_nonissuance_result_seal_reservation_evidence.py`
- lesson registry, remediation manifest, stage snapshot validator, CI, README

## 필수 판정 질문

1. 400 controls와 40 reservation이 정확한가?
2. 직렬 및 routed materialization/execution 20-way 요청이 같은 객체로 수렴하는가?
3. changed payload, cross-key ID/token/scope/nonce reuse, actor alias, order swap, expired epoch가 fail-closed인가?
4. policy v1 exact gate가 완전 downstream 변경에도 유지되는가?
5. result candidate가 cryptographic verdict로 오인될 권한을 갖지 않는가?
6. commit·receipt·signature·DB/ledger·PG/API·실행·관찰·PASS/FAIL·승인·배포가 모두 0인가?
7. 15단계 직접 증거계보와 #7501 historical snapshot이 미래 레지스트리 추가에도 불변인가?
8. `issued_at ≤ observed ≤ expires_at`의 양 경계만 수락하고 범위 밖 및 완전 재해시 공격을 거부하는가?
9. snapshot sequence가 API와 사후 integrity에서 모두 positive non-bool integer인가?

## HOLD 시 요청 형식

원인, 권장 해결, 대안, 비용·위험·가역성, 검증 절차, 중단·재개·rollback을 함께 제시해 주기 바란다.
