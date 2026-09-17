# 기능 #027 — Patch Draft Shadow 독립심사 대장

이 기능은 기능 #026이 만든 `PROPOSED_FOR_ETERNIAN_REVIEW` 평가만 합성 SQLite에
보존하고, 에테르니언의 독립심사를 별도 증거로 고정한다. ARKAON의 자기심사와
자기승격은 허용하지 않는다.

## 상태

- `PENDING_ETERNIAN_REVIEW`
- `READY_FOR_PATCH_DRAFT_OPERATOR_DECISION`
- `HELD`
- `REJECTED`

`PASS`의 최대 결과도 운영자 판단 준비 상태일 뿐이다. 운영자 승인, 패치나 diff
생성, 소스·파일 변경, 자동 적용, 안전기준 완화, 실행, 네트워크 접근, 결제·송금,
운영 활성화 권한은 전혀 부여하지 않는다.

## 실패 폐쇄 조건

- Shadow 평가·항목 다이제스트 또는 append-only 감사 사슬 불일치
- `HUMAN_REVIEW`·`BLOCKED` Shadow 결과 제출
- 항목 하나라도 `PASS`가 아닌 경우
- 제출·심사 시간 역전, ID 충돌 또는 재전송 내용 변경
- 합성 전용이 아닌 SQLite 경로
- 저장된 평가 JSON, 심사 다이제스트 또는 상태 결합 위변조

## 증거와 재시작

평가 원문, Shadow 다이제스트, 심사자·판정·소견 다이제스트, 시간 및 결과 상태를
저장한다. 동일 입력 재전송은 멱등이고 다른 내용의 충돌은 차단한다. 재시작 뒤에도
상태와 다이제스트가 동일해야 하며, 다음 계층은 `PASS` 결과를 읽기 전용으로만
조회할 수 있다.
