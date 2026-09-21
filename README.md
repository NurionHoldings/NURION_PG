# NURION PG

## Synthetic design controls

- [#3901~#4300 전자문서 협상·적합성 계층](docs/12-synthetic-document-negotiation-conformance-3901-4300.md)

Latest synthetic control extension: #2101-#2500 proposal feasibility assessment
and observation-only review portfolio. See
`docs/09-synthetic-proposal-feasibility-2101-2500.md`.

Synthetic canary readiness docket controls #1501-#1700 are documented in
[`docs/12-synthetic-canary-readiness-docket-1501-1700.md`](docs/12-synthetic-canary-readiness-docket-1501-1700.md).

누리온PG의 결제·정산 기반과 ARKAON 통제형 개발 체계를 위한 저장소입니다.

현재 단계는 `UNREGISTERED_SYNTHETIC_ONLY`입니다. 실제 결제, 승인, 취소, 환불,
송금, 정산, 가맹점 승인, 계약 체결, 운영 자격증명 접근 및 배포를 수행하지 않습니다.

## 최초 기능 묶음

- ARKAON 능력 프로필과 권한 경계
- `Baseline → Proposal → Synthetic Shadow → 에테르니언 심사 → 운영자 승인 → 제한 승격 → Rollback`
- 공식 근거의 출처·조회일·유효기간·SHA-256 고정
- 인터넷 자료를 비신뢰 입력으로 취급
- append-only SHA-256 증거 사슬
- 합성 데이터 전용 벤치마크와 GitHub CI
- 규제·금융기관·보안·정산 외부 차단조건의 실패 폐쇄
- 공식 규제근거 Registry와 상충·만료·미완전 근거 차단
- 균형·멱등·불변성을 강제하는 합성 원장 및 정산 계산
- 낙관적 버전·멱등 명령·원장 연결을 갖춘 합성 결제 생명주기
- 서명·재전송·순서역전·PII를 차단하는 합성 웹훅 격리 수신
- 재시작·동시성·rollback을 검증하는 합성 SQLite 웹훅 수신함
- 수락 웹훅을 자동 적용하지 않는 사람 검토용 합성 명령 제안
- ARKAON 제안과 에테르니언 심사를 분리하는 합성 영속 검토대장
- 결제·원장·웹훅·제안·검토대장을 잇는 읽기 전용 합성 정합성 감시
- 정합성 불일치를 자동수정 없이 에테르니언에게 넘기는 합성 사건 검토대장
- 확인된 사건을 실행 불가능한 조사·시험 보완안으로 구조화하는 ARKAON 초안
- 보완안 원문과 독립심사를 고정하고 합성 Shadow 준비까지만 허용하는 영속 검토대장
- 검토된 보완안을 실제 변경 없이 합성 fixture로 평가해 재심사 후보만 만드는 Shadow 평가
- 합성 Shadow 결과와 에테르니언 심사를 고정해 운영자 판단 준비까지만 허용하는 영속 대장
- 정책·외부 차단조건·심사 증거를 묶되 승인권은 갖지 않는 운영자 판단 패킷
- 합성 운영자 결정 봉투의 서명·만료·nonce만 검증하고 실제 결정은 기록하지 않는 수신계층
- 검증된 합성 결정 의사를 실제 승인과 분리해 보관하는 위변조 탐지 영속 수신대장
- 승인 의사 합성 수신증에서 비실행성 구현제안 골격만 만드는 ARKAON 초안 계층
- 구현제안 원문과 에테르니언 심사를 고정해 합성 패치 Shadow 준비까지만 허용하는 영속 대장
- 실제 패치 내용·파일 변경 없이 범위별 다이제스트와 합성 시험만 평가하는 패치 Shadow
- 패치 Shadow 결과와 독립심사를 고정해 운영자 판단 준비까지만 허용하는 영속 대장
- 검토된 패치 Shadow와 거버넌스 증거를 묶되 승인권은 갖지 않는 운영자 판단 패킷
- 합성 패치 결정 봉투의 서명·만료·nonce만 검증하고 실제 결정을 기록하지 않는 수신계층
- 검증된 합성 패치 결정 의사를 실제 승인과 분리해 보관하는 위변조 탐지 영속 수신대장
- 합성 패치 수신증에서 코드·diff 없이 범위와 대상 다이제스트만 만드는 ARKAON 초안 Manifest
- 합성 패치 Manifest 원문과 에테르니언 심사를 고정해 Patch Draft Shadow 준비까지만 허용하는 영속 대장
- 검토된 패치 Manifest를 코드·diff 생성 없이 합성 fixture로 평가하는 Patch Draft Shadow
- Patch Draft Shadow 결과와 독립심사를 영속 고정해 운영자 재판단 준비까지만 허용하는 대장
- 검토된 Patch Draft Shadow와 거버넌스 증거를 묶되 제한승격 승인권은 갖지 않는 운영자 판단 패킷
- 서명된 합성 Patch Draft 제한승격 의사의 계약만 검증하고 실제 결정을 기록하지 않는 수신계층
- 검증된 Patch Draft 제한승격 의사를 실제 승인과 분리해 보관하는 위변조 탐지 영속 수신대장
- 합성 제한승격 수신증에서 평가군·관찰창·rollback을 제한한 비실행 계획만 만드는 ARKAON 초안 계층
- 합성 제한승격 계획 원문과 에테르니언 심사를 고정해 별도 Shadow 준비까지만 허용하는 영속 대장
- 심사된 제한승격 계획을 활성화 없이 합성 관찰값으로 평가하고 이상 시 rollback 필요만 판정하는 Shadow
- 제한승격 Shadow 원문과 에테르니언 재심사를 고정하고 안전 결과와 rollback 결과를 분리하는 영속 대장
- 심사된 안전 결과와 현재 차단조건을 묶되 재확인권은 갖지 않는 운영자 재확인 패킷
- 서명된 합성 제한승격 재확인 의사의 계약만 검증하고 실제 재확인을 기록하지 않는 수신계층
- 검증된 제한승격 재확인 의사를 실제 승인과 분리해 보관하는 위변조 탐지 영속 수신대장
- 재확인 수신증과 검토 계보를 묶되 활성화권은 갖지 않는 합성 활성화 사전점검 Manifest
- 활성화 Manifest 원문과 에테르니언 최종심사를 고정하고 운영자 판단 준비까지만 허용하는 영속 대장
- 최종심사를 통과한 활성화 Manifest와 현재 차단조건을 묶되 승인권은 갖지 않는 운영자 판단 패킷
- 서명된 합성 활성화 의사의 계약만 검증하고 운영자 결정이나 활성화를 기록하지 않는 수신계층
- 검증된 합성 활성화 의사를 실제 승인·활성화와 분리해 보관하는 위변조 탐지 영속 수신대장
- 활성화 수신증과 현재 패킷에서 정확한 합성 Dry-run 범위만 고정하는 비실행 초안
- 합성 활성화 초안과 에테르니언 독립심사를 고정해 Dry-run 설계 준비까지만 허용하는 검토대장
- 통과한 활성화 초안 심사에서 범위·관찰·rollback 안전 게이트만 고정하는 비실행 Dry-run 설계
- 합성 활성화 Dry-run 설계를 독립심사해 fixture 제안 준비까지만 허용하는 검토대장
- 통과한 설계 심사에서 fixture 내용 없이 schema·입력·기대결과 digest만 만드는 비생성 제안
- 비생성 fixture 제안을 독립심사해 fixture 초안 준비까지만 허용하는 검토대장
- 통과한 제안 심사에서 fixture를 물질화하지 않고 blueprint digest만 고정하는 비실행 초안
- 비물질화 fixture 초안을 독립심사해 물질화 계획 준비까지만 허용하는 검토대장
- 통과한 fixture 초안 심사에서 내용·bytes·파일 없이 물질화 대상 digest만 고정하는 비실행 계획
- 비실행 fixture 물질화 계획을 독립심사해 specification 준비까지만 허용하는 검토대장
- 통과한 물질화 계획 심사에서 내용·bytes·경로 없이 specification digest만 고정하는 비실행 초안
- 비실행 물질화 specification을 독립심사해 별도 Dry-run 계획 준비까지만 허용하는 검토대장
- 통과한 specification 심사에서 실행 없이 materialization Dry-run contract digest만 고정하는 계획
- 비실행 materialization Dry-run 계획을 독립심사해 내용 없는 scenario 준비까지만 허용하는 검토대장
- 통과한 계획 심사에서 관찰값·내용 없이 미실행 scenario digest만 고정하는 초안
- 내용 없는 materialization Dry-run scenario를 독립심사해 expectation 준비까지만 허용하는 검토대장
- 통과한 scenario 심사에서 관찰값·결과 없이 expectation digest만 고정하는 초안
- 관찰값 없는 expectation을 독립심사해 assertion 준비까지만 허용하는 검토대장
- 통과한 expectation 심사에서 평가·결과 없이 assertion digest만 고정하는 초안
- 미평가 assertion 체인과 비실행 경계를 읽기 전용으로 검증하는 독립 경계감사
- assertion 감사 결과를 원본과 재대조해 append-only로 고정하는 비권한 증거대장
- 감사 증거대장의 레코드 수·끝점·evidence digest를 고정하는 읽기 전용 체크포인트
- Pattern Foundry Release Manifest Binding을 비배포 clean-room manifest 초안으로 적용
- 생산자·공격자·판정자·승인자를 분리하고 critical failure를 veto하는 합성 benchmark
- benchmark 영수증의 memory·in-memory SQLite 계약 동등성을 검증하는 합성 parity harness
- 운영자 의향 수신증의 비권한·무부작용·무자격증명 경계를 독립 검증하고 append-only 체크포인트로 봉인하는 읽기 전용 감사
- 운영자 의향 감사 체크포인트의 memory·in-memory SQLite 계약 동등성과 변조·재전송·동시성 통제를 검증하는 합성 registry parity
- PostgreSQL 권위 저장소 구현 전 요구사항·충돌·아키텍처·스키마·마이그레이션·패리티·수용기준을 고정하는 Planning Lock
- 외부 I/O 없이 append-only 체인·멱등·동시성·변조탐지를 구현한 memory 및 in-memory SQLite 합성 저장소 어댑터
- #501~#700을 계약·스키마·마이그레이션·저장소 의미·동시성·무결성·DB 패리티·CI 감사의 8개 PostgreSQL readiness workstream으로 고정
- #701~#900을 backpressure·중복판단·패킷갱신·단일경고·종료상태 정리·검증후 재개의 합성 delivery control로 구현
- #901~#1100을 우선순위 스케줄링·최대 30개 배치·완료중복 보관·복구가능 보관·relay 안정화·최대 50개 gap·독립복구검증·감사증거의 합성·메모리 전용 control로 구현
- #1101~#1300을 복구격리·최대 20개 탐침배치·독립검토·냉각시간·해제증명·재사용차단·emergency hold·감사증거의 합성·메모리 전용 control로 구현
- #1301~#1500을 제한 카나리 관찰·오류율·지연·회귀 자동보류·완료영수증·감사증거의 합성·메모리 전용 control로 구현
- #1501~#1700을 카나리 준비도 접수·최대 20개 포트폴리오·지표집계·독립검토·준비도 docket·감사증거의 합성·메모리 전용 control로 구현
- #1701~#1900을 readiness docket 접수·최대 20개 intent 배치·operator 초안·독립검토·비인가 경계·자동보류·receipt 재사용차단·감사증거의 합성·메모리 전용 control로 구현
- #1901~#2100을 합성 결정 의향에서 비실행 계획 제안을 작성·독립검토·영수증화하는 메모리 전용 control로 구현
- #2101~#2500을 구현제안 타당성 평가와 최대 20개 독립 관찰 포트폴리오로 묶는 합성·메모리 전용 control로 구현
- #2501~#2700을 타당성 포트폴리오 접수·최대 20개 결정대장 배치·source digest/version 결속·독립검토·비권한 영수증·capability-gap 자기점검의 합성·메모리 전용 control로 구현
- #2701~#2900을 최종 decision docket 검증·최대 20개 포트폴리오·결정분포·보류/기록 분리·4역할 독립감사·재사용차단의 합성·메모리 전용 control로 구현
- #2901~#3100을 기록된 decision portfolio에서 고정된 쉬운 문구·내부 증적 ID·역할분리·승인 비기록 경계를 갖는 비권한 운영자 브리핑으로 변환하는 합성·메모리 전용 control로 구현
- #3101~#3500을 용어·신뢰경계·토큰화 데이터/개념 자금흐름·복식원장 불변식·결제/환불/정산 상태기계·대사예외·멱등/웹훅·권한·감사/DR/SLO·포털 IA·공식근거 추적성의 16개 P0 설계 기준선 RFC workstream으로 구현
- #3501~#3900을 P0 설계검증과 입주사/대행업체 → NURION PG → 본 PG사의 양방향 전자문서·비실행 adapter 초안 추적성 16개 workstream으로 구현
- #3901~#4300을 3자 전자문서 schema 협상·mapping AST·400개 conformance case·독립 검토 receipt의 합성 계층으로 구현
- #4301~#4700을 4방향 전자문서·비실행 adapter artifact 28개 조립·route manifest·400개 mock acceptance case·독립 검토 receipt의 합성 계층으로 구현
- #9901~#10300을 응답 접수 원장을 독립 검토하고 반박기회·정정요청 경로를 파생하되 해결·수락하지 않는 합성 hold 계층으로 구현
- #10301~#10700을 4개 N/A marker·8개 반박·8개 정정 제출물의 출처·영수증·즉시부모 계보를 검증하고 인간 재심사 hold까지만 허용하는 합성 계층으로 구현
- #10701~#11100을 위 20개 제출물의 독립 재검토 계층으로 구현: 4개 N/A marker를 보존하고 8개 반박·8개 정정을 결론·수락·해결 없이 인간 재심사 대기 docket과 16개 append-only hold로만 고정
- #11101~#11500을 독립 재심사 관찰·쟁점 기록 계층으로 구현: 원천 actor 32명·이전 재심사자 16명·compiler/validator 계보를 보존하고 4개 N/A, 8개 반박 finding, 8개 정정 finding을 결론·추천·수락·해결 없이 `HUMAN FINDING REVIEW PENDING`과 16개 append-only hold로만 고정
- #11501~#11900을 독립 finding 검토·판단준비 계층으로 구현: 전체 원천 역할 계보를 재계산하고 4개 N/A를 보존하며 8개 반박·8개 정정 finding을 16개 append-only hold로 유지한다. 아르카온은 주장·증거·반증·불확실성·보류조건, 2개 이상 대안의 효과·위험·비용·가역성, 수락 기준·잔여위험·책임자·인간승인 gate, 원인 제거·수정·부정테스트·회귀·재발방지·rollback/재개조건으로 구성된 content-addressed 판단준비 패킷만 생성하며 결론·추천·수락·해결 권한은 갖지 않는다.
- #11901~#12300을 `반사실 판단준비 스트레스테스트` 계층으로 구현: 앞선 판단준비 패킷의 원천·전 역할 계보를 보존하고, 16개 routed finding 각각에 대해 원천결속된 2개 선택지와 명시적 미검증 가정·반증시험·중단조건·검증기준·잔여위험·escalation/rollback을 고정한다. 선택지 순위화·선택·결론·추천·수락·해결·승인 권한은 없으며 4개 N/A와 16개 인간판단 hold를 유지한다.
- #12301~#12700을 `원천결속 극복방법론 독립챌린지` 계층으로 구현: 16개 routed 사례의 32개 선택지 각각에 수정방향·극복방법·가정·반증시험·중단조건·검증기준·잔여위험·escalation·rollback을 하나의 content-addressed 카드로 결속한다. 4개 N/A와 16개 append-only 인간판단 hold를 보존하고 순위화·선택·결론·추천·수락·해결·승인·실행 권한은 갖지 않는다.
- #12701~#13100을 `단계별 교훈 스냅샷·가이드형 복구경로 감사` 계층으로 구현: 단계 범위·registry/manifest·선행 snapshot·원천 docket을 content-addressed snapshot으로 고정하고, 16개 routed 사례마다 실패 원인·비구속 안전후보·2개 극복안과 각 안의 가정·반증시험·중단/검증·잔여위험·비용/위험/가역성·escalation·rollback/재개조건을 결속한다. 4개 N/A와 16개 append-only 인간판단 hold를 유지하며 추천·선택·결론·수락·해결·승인·실행 권한은 갖지 않는다.
- #13101~#13500을 `자동 스냅샷 체인·미확정 원인 진단 프리플라이트` 계층으로 구현: stage mapping 전체의 중복·공백·lesson 회귀를 자동 fail-closed 검증한다. source guidance·challenge·snapshot과 probe 상태를 cause evidence로 결속하며 probe 미실행 상태는 억지 분류 없이 `CAUSE_UNDETERMINED`로 hold한다. 16개 routed 사례마다 진단 최소안·독립 재검증안과 읽기 전용 preflight를 제공하고, 4개 N/A, 16개 append-only 인간판단 hold, 전체 actor lineage와 비실행 경계를 유지한다.
- #13501~#13900을 `내용 없는 합성 관찰계약·독립 검증게이트` 계층으로 구현: NOT_RUN probe에 source-bound fixture/input identity, 기대 PASS/FAIL 전제, evidence completeness, 독립 verifier gate를 결속하되 관찰값과 판정은 만들지 않는다. 모호·상충 결과는 자동 승격하지 않고 hold하며 계약보수·독립 재관찰 계획의 2개 극복경로와 비용·위험·가역성·중단·검증·rollback·재개조건을 제공한다. 4개 N/A, 16개 append-only 인간판단 hold, 전체 actor lineage와 비실행 경계를 유지한다.
- #13901~#14300을 `비실행 관찰준비 매니페스트·독립 승인게이트` 계층으로 구현: source-bound 관찰계약마다 resource budget, privacy/data classification, determinism, isolation, timeout, side-effect prohibition, plan-only receipt schema와 materialization/execution 분리 승인 게이트를 하나의 content-addressed 계획으로 결속한다. 계획보수·전면 재구성의 2개 가이드형 복구경로를 제공하지만 fixture materialization, probe, 관찰값, PASS/FAIL, 원인 확정은 모두 금지한다. 4개 N/A, 16개 append-only 인간판단 hold, 전체 actor lineage와 비실행 경계를 유지한다.
- #14301~#14700을 `복합계획 신원·이중 승인인텐트 봉투 게이트` 계층으로 구현: plan_id·flow·kind·source contract·readiness manifest를 하나의 content-addressed identity로 결속하고, materialization과 execution을 서로 다른 actor·sequence·predecessor·nonce/replay scope의 PENDING 봉투로 분리한다. receipt 발급·materialization·execution은 금지하며 실패 원인, 비용·위험·가역성·검증·중단·재개·rollback을 포함한 두 복구경로와 공통 final-docket 불변식을 제공한다.
- #14701~#15100을 `비발급 승인영수증 스키마·독립 멱등키 계약` 계층으로 구현: 40개 PENDING intent 각각에 source identity·actor slots·순서·predecessor·nonce와 독립 idempotency key/payload scope를 결속한다. 동일 key·payload는 직렬/병렬 수렴하고 변경 payload·교차 key identity 재사용은 fail-closed하며, 실제 receipt 발급·materialization·execution·observation·PASS/FAIL·승인 권한은 모두 금지한다.
- #15101~#15500을 `발급 전 검증 패킷·이중 서명입력 계약` 계층으로 구현: 40개 receipt schema마다 source identity·idempotency scope·sequence·predecessor·nonce와 issuer/verifier의 독립 actor, domain, challenge, audience, purpose, policy, 결정적 합성 expiry를 결속한 80개 서명 입력 digest를 만든다. 실제 서명값·키·자격증명·receipt·원장·실행·관찰·승인 권한은 생성하거나 읽지 않는다.
- #15501~#15900을 `비발급 검증결과 봉인·원자적 멱등예약 계약` 계층으로 구현: 40개 preissuance packet마다 비암호학적 결과후보와 봉인입력, 독립 owner/validator, 결정적 expiry, source scope·서명입력·policy v1·sequence·predecessor·nonce를 결속한 원자적 예약을 하나씩 만든다. commit·서명·receipt·DB/원장·PG/API·실행·관찰·승인 권한은 모두 0으로 유지한다.
- #15901~#16300을 `PostgreSQL 비발급 예약원장 스키마·트랜잭션 증명 계약` 계층으로 구현: 정규화 schema AST에서 결정적 quoted DDL을 만들고 40개 append-only row 계획에 six-way unique target, source/result/seal/policy/time/lineage/actor 결속과 crash 전후 retry/read-back 의미를 부여한다. 사전 구성 PostgreSQL이 없어 실제 DB proof는 명시적 SKIP이며 DB URL·credential·쓰기·commit·receipt·PG/금융·승인·배포는 0이다.
- #16301~#16700을 `격리형 PostgreSQL fixture·migration·repository proof 계약` 계층으로 구현: 운영 host/database를 거부하고 `nurion_pg_ci`의 접두사 제한 disposable schema에서만 up/down migration, exact column·nullability·6 unique·check introspection, 20-way barrier 수렴, changed-payload/cross-key 충돌, aborted transaction rollback/new transaction, response-loss read-back, narrow cleanup을 실증한다. 일반 단위 CI는 정직한 SKIP, 별도 PostgreSQL service job은 test-only PASS를 생성하며 운영 DB 쓰기·receipt·서명·키·금융·승인·배포는 0이다.
- #16701~#17100을 `PostgreSQL bounded retry·commit-unknown recovery proof 계약` 계층으로 구현: 실제 disposable PostgreSQL의 SERIALIZABLE write-skew에서 SQLSTATE 40001 정확히 1회 후 attempt 2 성공과 실제 57014 timeout 1회·비재시도를 증명한다. 최대 3회와 exhaustion fail-closed는 `UNIT_INJECTED_SQLSTATE_SEQUENCE` 단위 계약이며 실제 DB exhaustion은 주장하지 않는다. commit-unknown은 실제 commit 뒤 하네스가 주입한 response loss임을 공개하고 fresh read에서 `EXISTING_SAME_PAYLOAD`와 exact digest만 허용한다. 실제 network partition·deadlock 실증은 주장하지 않으며 운영 DB 쓰기·receipt·서명·키·금융·승인·배포는 0이다.
- #17101~#17500을 `PostgreSQL actual deadlock·lock contention proof 계약` 계층으로 구현: disposable PostgreSQL의 두 backend가 두 행을 반대 순서로 잠가 실제 SQLSTATE 40P01 피해자 정확히 1개와 승자 1개를 만들고, 실패 transaction rollback·backend close 뒤 fresh backend의 attempt 2 성공을 증명한다. 별도 blocked-row lock timeout은 실제 55P03 1회·비재시도로 고정하며 actual/unit/harness provenance를 분리한다. deadlock_timeout 설정 불가 환경은 PASS가 아닌 명시적 실패이고 network partition·failover는 미주장하며 운영 쓰기·승인·발급·병합·배포는 0이다.
- #17501~#17900을 `PostgreSQL actual backend termination·commit outcome reconciliation proof 계약` 계층으로 구현: disposable PostgreSQL worker PID를 별도 admin 연결의 `pg_terminate_backend`로 실제 종료하고 57P01/08006 allowlist만 수락한다. pre-commit 종료는 fresh read-only 연결에서 정확한 row absence를 확인하고 blind retry 없이 HOLD하며, acknowledged commit 뒤 종료는 exact idempotency key와 payload digest를 새 read-only 연결로 확인한다. 이는 실제 network partition·failover 또는 COMMIT response loss의 증명이 아니며 권한·SQLSTATE 환경 차이는 fail-closed, 운영 쓰기·승인·발급·병합·배포는 0이다.
- #17901~#18300을 `PostgreSQL append-only recovery quarantine proof 계약` 계층으로 구현: pre-commit connection-loss의 `HOLD_NOT_COMMITTED`를 자동 재시도하지 않고 별도 disposable schema의 비실행 quarantine case로 전환한다. source event·idempotency key·payload·SQLSTATE·provenance·observed time·sequence·state를 결정적 case identity에 결속하며 동일 envelope는 1행으로 수렴하고 변경 payload·교차 key는 fail-closed한다. fresh read-only operator packet/view로만 조회하며 payment·receipt·retry·approval 권한과 source write/retry는 0이다. 실제 network partition·failover·운영처리는 미주장한다.
- #18301~#18700을 `PostgreSQL post-quarantine recovery disposition proof 계약` 계층으로 구현: 인간 검토 결과를 exact quarantine case digest에 결속한 append-only `HOLD_FOR_MANUAL_RECOVERY_NON_EXECUTABLE` 처분으로 기록한다. 동일 envelope는 1행으로 수렴하고 변경 payload·교차 key는 fail-closed하며 quarantine 원본과 operator view는 수정 불가다. payment·receipt·retry·approval·execution 권한은 모두 false이고, multi-node failover는 실제 수행하지 않은 명시적 preflight 계약으로만 남긴다.
- #18701~#19100을 `PostgreSQL append-only recovery supersession proof 계약` 계층으로 구현: base 처분은 수정하지 않고 exact predecessor digest에 결속된 successor만 추가한다. DB 복합 FK·partial unique index가 단일 genesis, 단일 successor, 단조 version/sequence, 단일 current head를 강제하며 변경 payload·교차 key·fork·stale head·predecessor alias는 fail-closed한다. operator view와 원장은 수정 불가이고 모든 payment·receipt·retry·approval·execution 권한은 false다. 실제 network partition·failover·fault injection은 주장하지 않는다.
- #19101~#19500을 `PostgreSQL exact current-head review snapshot·receipt proof 계약` 계층으로 구현: 검토 시작 시점의 exact current head `(case, supersession, digest, version)`를 append-only snapshot으로 봉인하고 독립 reviewer와 result digest를 단일 비실행 receipt에 결속한다. stale head·변경 snapshot·cross-case·receipt 변조는 fail-closed하고 snapshot·receipt·operator view의 UPDATE/DELETE/DML을 거부한다. 이 receipt는 결제·영수증 발급·재시도·승인·실행 권한을 생성하지 않으며 실제 network partition·failover·fault injection은 주장하지 않는다.
- #19501~#19900을 `PostgreSQL recovery recommendation·independent concurrence proof 계약` 계층으로 구현: exact review receipt에 action/risk digest와 독립 author를 결속한 비실행 recommendation을 기록하고, author와 다른 reviewer들의 concurrence 또는 conflict verdict를 append-only로 보존한다. reviewer별 단일 verdict를 강제하고 하나라도 conflict가 있으면 HOLD를 유지하며, recommendation과 concurrence는 결제·영수증 발급·재시도·승인·실행 권한을 만들지 않는다.
- #19901~#20300을 `PostgreSQL append-only conflict-resolution docket·rereview lineage proof 계약` 계층으로 구현: recommendation의 정확한 conflict 집합을 canonical digest로 봉인하고 resolution docket과 predecessor-bound 재검토 round를 추가한다. 단일 genesis·단일 successor, actor separation, stale/fork 차단과 append-only를 유지하며 resolution 기록만으로 승인·결제·재시도·실행 권한은 생성되지 않는다.
- 에테르니언 감사 교훈은 [ARKAON 감사 재발방지 지도사항](docs/70-arkaon-audit-recurrence-prevention.md)과 기계검증 정책으로 환류
- 에테르니언 보완 커밋은 versioned lesson registry의 entry·ack·부정 테스트·재검증 증적이 없으면 전용 evidence 생성이 fail-closed

자세한 내용은 [ARKAON 통제형 부트스트랩](docs/01-arkaon-governed-bootstrap.md)을 참고합니다.

## 로컬 검증

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/validate_governance.py
PYTHONPATH=src python scripts/run_bootstrap_evidence.py
```

CI 성공은 등록, 계약, 운영승인, 병합 또는 배포 승인을 의미하지 않습니다.

규제 Registry에 기록된 내용은 설계 초안의 근거일 뿐 법률자문이나 운영승인이 아닙니다.
