# NURION_PG 운영 완성도 통합 감사 — #20300 기준선

## 최종 판정

**통제·합성 증명 체계는 고도화됐지만, NURION_PG는 아직 실제 PG 운영 플랫폼이 아니다.**

저장소가 스스로 선언한 현재 상태는 `UNREGISTERED_SYNTHETIC_ONLY`이며 패키지 설명도 `Synthetic-only governed bootstrap for NURION PG`이다. 실제 결제, 승인, 취소, 환불, 송금, 정산, 가맹점 승인, 운영 자격증명 접근과 배포는 모두 의도적으로 차단돼 있다.

## 직접 확인한 저장소 구성

| 항목 | 확인 결과 | 운영 판정 |
|---|---:|---|
| `src/nurion_pg` Python 모듈 | 136개 | 구현량은 큼 |
| `synthetic_*` 모듈 | 105개 | 대부분 합성·비실행 통제 |
| 테스트 파일 | 139개 | 합성 계약 회귀가 강함 |
| 증거 생성 스크립트 | 148개 | 감사 추적성 강함 |
| 런타임 의존성 | 0개 | 운영 서버·DB 클라이언트 패키지 없음 |
| HTTP API/서버 진입점 | 없음 | 운영 서비스 불가 |
| 외부 PG/VAN adapter | 없음 | 실제 승인·취소·환불 불가 |
| 운영 DB migration | 없음 | disposable proof 외 운영 스키마 없음 |
| 배포 구성 | 없음 | 운영 배포 불가 |
| 운영 자격증명·KMS 연동 | 없음 | 실제 서명·provider 인증 불가 |

## 완성도 재산정

공정 번호와 테스트 수는 운영 완성률로 환산하지 않았다. 실제 사용자가 결제 요청을 보내고 외부 PG/VAN 응답을 받아 원장·정산·환불까지 처리할 수 있는지를 기준으로 산정했다.

| 영역 | 비중 | 현재 완성도 | 가중 기여 | 근거 |
|---|---:|---:|---:|---|
| 합성 도메인·상태기계 | 15% | 75% | 11.25% | Payment Intent·원장·웹훅 모델 존재, 전부 synthetic |
| 감사·거버넌스·실패폐쇄 | 15% | 100% | 15% | 동결 범위 종결 계약 10/10, append-only 증거, 역할 분리, PostgreSQL proof |
| 운영 API·인증·인가 | 15% | 0% | 0% | 서버·route·principal/session 없음 |
| 외부 PG/VAN 연동 | 20% | 0% | 0% | provider adapter·credential·network client 없음 |
| 운영 PostgreSQL·migration | 10% | 15% | 1.5% | disposable CI proof만 존재 |
| 결제·취소·환불 실제 실행 | 10% | 0% | 0% | 명시적으로 금지됨 |
| 정산·대사·지급 운영 | 10% | 5% | 0.5% | 합성 계산·감시 모델만 존재 |
| 관측·배포·DR·운영도구 | 5% | 0% | 0% | 런타임·배포·알림 구성 없음 |
| **#20300 당시 운영 완성도** | **100%** |  | **28.25%** | 이후 OPS 구현 진척은 별도 갱신 |

현재 공정률은 다음처럼 분리해 보고한다.

- **합성 통제·감사 연구 공정률: 100%** — 동결 범위의 기계검증 가능한 10개 종결 기준 충족
- **실제 PG 운영 플랫폼 공정률: 약 28%**
- **상용 운영 준비도: 0%** — 계약·등록·보안심사·실사업자 연동·운영승인이 없기 때문

## 이미 자산화된 부분

- 결제 상태기계와 멱등·버전 충돌 원칙
- 복식원장 불변식과 합성 정산 계산
- 웹훅 서명·nonce·순서·PII 차단 계약
- 동시성·재시도·deadlock·connection loss PostgreSQL proof
- append-only 복구·검토·분쟁 계보
- ARKAON 구현과 ETHERNIAN 독립 감사 역할 분리
- content-addressed 증거와 회귀 자동화

이 자산은 폐기 대상이 아니다. 운영 코어를 구현할 때 수용기준과 부정 테스트로 재사용한다.

## 운영 전환을 막는 핵심 공백

1. 실제 서비스 경계가 없다: HTTP API, 인증, 가맹점 tenant, 권한 모델, request validation이 없다.
2. provider 경계가 없다: 승인·매입·취소·환불·망취소 adapter와 오류코드 mapping이 없다.
3. 운영 데이터 계층이 없다: versioned migration, repository, outbox/inbox, ledger transaction boundary가 없다.
4. 실제 자금 흐름이 없다: synthetic state 이름과 계산만 있고 외부 결과 reconciliation이 없다.
5. 보안 운영이 없다: KMS/HSM, secret rotation, mTLS, key custody, PII/tokenization, 접근감사가 없다.
6. 운영 플랫폼이 없다: 배포, 모니터링, 알림, SLO, backup/restore, DR, runbook이 없다.
7. 사업·규제 준비가 없다: PG/VAN 계약, 전자금융 관련 검토, 가맹점 심사, 개인정보·전자금융 보안 통제가 미확정이다.

## 즉시 중단할 방식

- 운영 기능과 연결되지 않은 400개 단위 synthetic stage의 무기한 증가
- 공정 번호 또는 PASS 개수를 운영 완성률로 해석하는 보고
- 비실행 receipt·approval schema를 실제 승인 기능으로 표현하는 보고
- 중첩 PR을 `main` 통합과 동일하게 간주하는 방식

## 통합 기준선

`#19901~#20300`까지의 통제 증명은 안전 연구 기준선으로 동결한다. 이후 신규 작업은 운영 기능 epic과 수용기준으로 번호를 다시 부여하며, 각 epic은 실제 실행 코드를 포함해야 한다. 합성 증명은 새 운영 코드의 안전 게이트로 사용하되 독립적인 공정 확장 목적이 되어서는 안 된다.
