# 합성 답변·추가자료 접수 검증 계층 (#7501~#7900)

## 목적

직전 인간 심의 질문 도켓을 실제 답변 접수나 의사결정으로 연결하지 않고, 입주사·NURION PG·본 PG 사이의 합성 답변 문서와 추가자료 패키지가 완전성, 출처, 버전, receipt, 의미 상충 및 전체 계보 조건을 만족하는지만 메모리에서 검증한다.

## 통제 구조

- 16개 workstream × 25개 aspect = 정확히 400개 통제
- 4방향 흐름 × 5개 답변 종류 = 20개 합성 answer-material
- 각 answer-material에는 source document, route, 원 질문, answer document, material manifest, source receipt, version, semantic claim이 함께 결속된다.
- semantic claim과 material manifest 자체도 질문·당사자·원본 문서·route·버전에서 순차 파생해 전체 chain 재해시 치환을 차단한다.
- 한 건이라도 누락되거나 상충·구버전·재전송이면 최종 검증 패킷을 만들 수 없다.
- source reviewer 3명, compiler 3명, chair, submitter, intake reviewer, validator를 전체 역할 충돌 집합으로 검사한다.

## 안전 경계

최대 상태는 `ANSWER_MATERIAL_VALIDATION_READY_NOT_ACCEPTED_NOT_DECIDED`이다. 실제 외부 답변 접수, 전자문서 전송, 전자서명, 추천, 동의, 결정, 승인, 활성화, 배포, 외부 PG/API, 카드망, 금융 처리, 원장 기록 및 운영 자격증명 접근 기능은 없다.

## 결정론적 증적

`python scripts/run_synthetic_answer_material_intake_validation_evidence.py`는 학습 registry와 ARP-01~08을 검증한 후 동일 JSON과 SHA-256을 생성한다.
