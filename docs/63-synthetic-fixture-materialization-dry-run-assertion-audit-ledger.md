# 기능 #063 — Assertion 감사 증거대장

## 목적

#062의 읽기 전용 경계감사 결과를 원본 assertion 체인과 다시 대조한 뒤 append-only
증거대장에 기록한다. 이 기록은 후속 실행이나 승격의 승인이 아니다.

## 실패폐쇄 조건

- typed assertion book의 체인이 손상되었거나 대상 assertion이 소속되지 않은 경우
- 감사 digest가 원본 assertion에서 재산출한 감사 결과와 일치하지 않는 경우
- 기록 시각이 감사 시각보다 앞서거나 timezone 정보가 없는 경우
- 기존 증거대장의 순서·이전 digest·record digest가 손상된 경우

## 권한 상한

최대 상태는
`SYNTHETIC_FIXTURE_MATERIALIZATION_DRY_RUN_ASSERTION_AUDIT_RECORDED`이다.
평가, Dry-run 실행, fixture 물질화, 활성화, 네트워크 접근, 실제 결제·자금 이동,
운영 자격증명 사용, 자동 병합 및 자동 배포 기능을 제공하지 않는다.
