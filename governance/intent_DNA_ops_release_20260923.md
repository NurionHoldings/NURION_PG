# NURION PG 운영 배포 보완 기록 · 2026-09-23

## 조사

- 공개 `nurionpg.netlify.app`는 합성 데이터 전용 정적 미리보기다. 운영 API가 배포된 주소가 아니다.
- 저장소 `main`은 초기 README만 있고, 운영 코드가 포함된 `ops/e10-operator-console-limited-readiness`는 `main`보다 975개 커밋 앞서 있다.
- 기존 API 시작 경로가 각 인스턴스에서 `migrate_up()`을 실행했다. readiness는 설정 문자열만으로 참이 될 수 있었고, 처리되지 않은 예외는 traceback을 로그에 출력했다.

## 결정과 변경

- API 시작 시 DB를 변경하지 않고 migration checksum을 읽기 전용으로 검증한다. DB 또는 schema가 유효하지 않으면 시작/준비 상태를 실패 폐쇄한다.
- migration은 독립된 명시적 일회성 작업으로 분리한다. 운영 API DB 계정에는 DDL 권한을 주지 않는다.
- 요청 처리 예외의 상세 정보는 응답과 서버 로그에 출력하지 않는다.
- 운영 배포 절차와 외부 차단조건은 `deploy/PRODUCTION_RELEASE.md`에 기록한다.

## 검증

- `test_api_runtime.py`: 12 PASS.
- `test_ops_deployment_readiness.py`: 2 PASS.
- 관련 Python 컴파일과 `git diff --check`: PASS.
- 실제 PostgreSQL, 전 범위 CI, 운영 인프라 배포는 미실행. 신규 코드가 운영 배포 가능 판정을 의미하지 않는다.

## 외부 차단조건과 실패 원인

- `main`에 운영 코드 미통합, 실제 PG/VAN 계약·인증 및 운영 인프라·키 관리 주체 미확정.
- 공개 사이트는 정적 업로드이며 운영 API와 분리되어 있다. 이를 결제 운영 환경으로 전환해서는 안 된다.
- 구현 커밋: `02a679d` (`fix(ops): separate database migrations from API readiness`).
- CI·배포 결과: 미실행. 운영 통합 및 외부 차단조건이 충족되지 않아 병합·운영 배포를 보류한다.
