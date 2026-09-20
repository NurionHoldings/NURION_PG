# #4301~#4700 합성 연동 패키지 조립·모의 인수 검증

#3901~#4300의 3자 전자문서 협상 결과와 독립 검토 receipt를 입력 기준선으로 봉인한다. 입주사/대행업체↔NURION PG↔본 PG사 4방향 흐름마다 전자문서 template, adapter contract, token fixture, request/response mock, retry·replay·ordering vector를 비실행 산출물로 조립하고 정확히 400개 합성 인수 case와 독립 검토 receipt로 검증한다.

## 16×25 통제

1. negotiation receipt anchor
2. tenant package manifest
3. electronic document template set
4. adapter contract scaffold
5. token fixture catalog
6. request/response mock pairs
7. error/retry mock matrix
8. idempotency/replay harness
9. sequence/concurrency harness
10. schema drift impact graph
11. tenant/upstream route binding
12. package reproducibility
13. mock acceptance cases
14. independent acceptance review
15. partial package hold chain
16. operator release gate boundary

각 workstream은 동일한 25개 관점으로 #4301~#4700을 누락·중복 없이 덮는다. 7개 artifact 유형×4개 흐름의 정확히 28개 산출물만 허용하며, 각 artifact의 party는 해당 흐름의 고정 송신 주체와 일치해야 한다. 부분 자료, 중복 유형·흐름, 계보 단절, 역할 충돌, 400 case 미완성은 fail-closed 한다.

독립 감사 보완으로 assembler identity를 manifest digest에 직접 포함한다. 네 route digest는 tenant·NURION PG·upstream·flow의 정규 tuple에서 매번 재계산하며, 사후 무결성 검사에서도 package/tenant/upstream/assembler namespace를 재검증한다. acceptance receipt는 `accepted_for_review=true`를 명시적으로 강제한다.

입력은 source bundle, 최신 negotiation round, 400-case set, 독립 review receipt digest에 결속된다. manifest 최대 상태는 `MOCK_ACCEPTANCE_REQUIRED`, receipt 최대 상태는 `ACCEPTANCE_REVIEWED_NOT_RELEASED`다. 네트워크 transport, 전자서명, 실행 adapter, 본 PG API, 카드망, 실금융·원장·운영 자격증명·배포·운영 정책 변경 능력은 포함하지 않는다.

독립 감사 교훈의 일반화와 다음 단계 재발 방지 기준은 [ARKAON 감사 재발방지 지도사항](70-arkaon-audit-recurrence-prevention.md)을 따른다.
이번 단계 evidence는 누적 lesson registry를 먼저 검증하고 registry version·digest·적용 lesson ID를 포함해야만 생성된다.
