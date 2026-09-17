# 기능 #064 — Assertion 감사대장 읽기 전용 체크포인트

## 목적

#063 append-only 감사 증거대장의 레코드 수, 끝점 record digest, 대장 evidence
digest를 하나의 읽기 전용 체크포인트로 고정한다. 체크포인트는 실행 승인이나 상태
승격이 아니다.

## 실패폐쇄 조건

- typed 감사 증거대장이 아니거나 체인이 손상된 경우
- 대장이 비어 있는 경우
- 체크포인트 시각이 마지막 기록 시각보다 앞서거나 timezone 정보가 없는 경우
- 체크포인트 생성 도중 대장 evidence가 달라진 경우
- 생성된 체크포인트 digest가 변조된 경우

## 권한 상한

최대 상태는
`SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_AUDIT_LEDGER_CHECKPOINTED`이다.
평가, Dry-run 실행, fixture 물질화, 활성화, 네트워크 접근, 실제 결제·자금 이동,
운영 자격증명 사용, 자동 병합 및 자동 배포 기능을 제공하지 않는다.
