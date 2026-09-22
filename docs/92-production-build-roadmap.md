# NURION_PG 운영 플랫폼 전환 로드맵

## 실행 원칙

- 신규 공정 표기는 `OPS-E01`부터 다시 시작한다.
- 각 epic은 운영 코드, DB migration, API contract, 부정 테스트, 관측 지표, rollback을 함께 납품한다.
- provider가 확정되기 전에는 adapter interface와 인증 없는 sandbox fake까지만 구현한다.
- 실제 자격증명·실결제·운영 배포는 별도 사용자 승인과 외부 계약 확인 전 금지한다.
- 기존 synthetic 자산은 해당 운영 기능의 수용기준으로 연결한다.

## 우선순위

| Epic | 범위 | 핵심 산출물 | 완료 기준 | 예상 비중 |
|---|---|---|---|---:|
| OPS-E01 | 운영 애플리케이션 골격 | API server, settings, health/readiness, 오류계약 | 로컬 서버·CI·구조화 로그 | 8% |
| OPS-E02 | Principal·가맹점·권한 | merchant tenant, API key/OAuth boundary, RBAC | cross-tenant 차단·감사로그 | 10% |
| OPS-E03 | 운영 PostgreSQL 기반 | migration, repository, transaction, outbox | fresh/upgrade/rollback DB CI | 12% |
| OPS-E04 | Payment Intent API | create/get/authorize/capture/cancel/refund | 멱등·version·금액 불변식 E2E | 14% |
| OPS-E05 | Provider adapter | provider port, sandbox adapter, error mapping | timeout·duplicate·unknown outcome E2E | 14% |
| OPS-E06 | Webhook inbox·적용 | signature, durable inbox, outbox, reconciliation | 재전송·역순·변조·crash recovery | 10% |
| OPS-E07 | Ledger·settlement | double-entry ledger, fee, settlement batch, reversal | 원장 균형·마감·재실행 E2E | 12% |
| OPS-E08 | 운영 콘솔 | 거래검색, HOLD queue, 수동검토, audit export | **완료: 권한분리·민감값 비노출·이력** | 8% |
| OPS-E09 | 보안·관측·DR | secret/KMS port, metrics, alerts, backup/restore | SLO·복구훈련·보안점검 | 8% |
| OPS-E10 | 제한 운영 전환 | sandbox certification, runbook, canary, rollback | **구현 완료: 외부 승인 전 트래픽 차단** | 4% |

## 첫 구현 묶음: OPS-E01

1. 프레임워크와 런타임 의존성 확정
2. `app` factory와 `/health/live`, `/health/ready`
3. 환경별 settings와 secret 값 출력 금지
4. 표준 오류 envelope·correlation ID·구조화 로그
5. 운영 코드와 synthetic harness 디렉터리 분리
6. API 단위시험과 프로세스 smoke test
7. Dockerfile 또는 명시적 실행 패키지

OPS-E01은 돈을 움직이지 않는다. 그러나 이 단계부터 산출물은 문서나 합성 모델이 아니라 실제 실행 가능한 서비스가 된다.

## 사용자 결정이 필요한 외부 항목

- 목표 역할: 자체 PG, 하위 PG/결제중계, 가맹점 통합 게이트웨이 중 어느 모델인지
- 1차 연동 대상 PG/VAN과 sandbox 제공 여부
- 초기 결제수단: 카드, 계좌이체, 가상계좌, 간편결제 범위
- 운영 인프라: 클라우드·리전·KMS·DB 운영 주체
- 개인정보·카드정보 보유 여부와 tokenization 책임 경계

외부 항목이 미확정이어도 OPS-E01~E04의 provider-neutral 코어는 진행할 수 있다. 실제 adapter·실결제·운영 배포는 확정 후 진행한다.
