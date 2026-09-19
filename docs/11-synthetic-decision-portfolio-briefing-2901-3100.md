# Synthetic Decision Portfolio Briefing (#2901~#3100)

기록 완료된 합성 Decision Portfolio를 일반 운영자가 이해할 수 있는 고정 문구의
브리핑으로 변환하는 메모리 전용 통제 계층이다. 브리핑은 승인이나 실행이 아니며
항상 `operator_action_required=true`, `approval_recorded=false`를 유지한다.

## 통제 범위

- 8개 workstream × 25개 통제 = 정확히 200개
- typed source와 원문 digest/version을 다시 검증
- 최대 20개 source, 포트폴리오/구성원 trace와 내부 evidence ID 제공
- 상태·결정 분포를 고정된 쉬운 문구로만 변환하고 자유 prompt 생성을 금지
- curator, briefing author, reviewer, verifier, auditor 역할 분리
- 멱등성, 충돌, 재전송, 동시성, append-only chain과 의미 변조 탐지
- 재해시된 source도 집계값·requested limit·member 의미를 다시 검증
- review·receipt·event·hold의 첨부 증적과 역할 provenance를 결속
- 최대 상태 `SYNTHETIC_BRIEFING_RECORDED`

승인 버튼, 실제 승인, 결제·정산·송금, 외부 URL/API 호출, 원장 반영,
운영 자격증명 및 정책·Prompt·가중치 변경은 구현하지 않는다.
