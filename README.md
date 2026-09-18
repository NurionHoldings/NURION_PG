# NURION PG

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

자세한 내용은 [ARKAON 통제형 부트스트랩](docs/01-arkaon-governed-bootstrap.md)을 참고합니다.

## 로컬 검증

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/validate_governance.py
PYTHONPATH=src python scripts/run_bootstrap_evidence.py
```

CI 성공은 등록, 계약, 운영승인, 병합 또는 배포 승인을 의미하지 않습니다.

규제 Registry에 기록된 내용은 설계 초안의 근거일 뿐 법률자문이나 운영승인이 아닙니다.
