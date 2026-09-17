# 보완안 합성 Shadow 평가

## 목적

에테르니언이 통과시킨 ARKAON 보완안에 대해 실제 코드·결제·운영환경을
변경하지 않고 합성 fixture 결과만 평가한다. 결과는 다시 에테르니언 검토
후보로 제출할 수 있을 뿐 자동 적용이나 운영자 결정으로 이어지지 않는다.

## 입력 경계

- 영속 검토대장의 `READY_FOR_SYNTHETIC_SHADOW` 상태만 입력으로 허용한다.
- 검토대장의 제안·심사·감사 사슬 무결성을 읽기 직전에 재검증한다.
- 각 보완항목에는 정확히 하나의 SHA-256 고정 합성 fixture가 필요하다.
- 항목 다이제스트와 작업 유형이 일치하지 않거나 fixture가 누락·중복·추가되면
  실패 폐쇄한다.

## 평가 기준

모든 항목은 다음을 충족해야 `PASS`다.

1. 합성 조건에서 대상 불일치가 재현됨
2. 실패 폐쇄 안전기준이 유지됨
3. 회귀시험이 통과함
4. SHA-256 증거가 재현됨
5. 후속 에테르니언 검토가 유지됨

하나라도 충족하지 못하면 `HUMAN_REVIEW`다. 결제상태 변경, 자금이동 또는
운영 접근이 관측되면 즉시 `BLOCKED`다. 모든 항목이 통과해도 최종 결과는
`PROPOSED_FOR_ETERNIAN_REVIEW`이며 승인이나 승격이 아니다.

## 통제

- 입력 순서와 무관한 결정론적 항목 결과 및 append-only 평가 사슬
- 동일 제안·동일 fixture의 멱등 재실행과 다른 payload 충돌 차단
- 평가 전후 원본 검토대장 증거 다이제스트 비교
- 코드 변경, 보완안 적용, 안전기준 완화, 운영자 결정, 실제 결제·환불·송금,
  운영승격 메서드 미제공
- 인터넷 자료, 운영 자격증명, 실제 개인정보·거래자료 미사용

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_remediation_synthetic_shadow -v
PYTHONPATH=src python scripts/run_remediation_synthetic_shadow_evidence.py
```

CI 증거는 `build/synthetic-remediation-shadow-evidence.json`과 SHA-256 파일로
고정한다. CI 성공은 병합·배포·운영승인을 의미하지 않는다.
