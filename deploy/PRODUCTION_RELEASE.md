# NURION PG 운영 배포 게이트

이 문서는 API 배포 절차를 정의합니다. 현재 공개 Netlify 화면은 합성 데이터 미리보기이며, 이 API와 연결되어 있지 않습니다.

1. `main`에 아직 반영되지 않은 OPS 브랜치를 검토하고 CI를 최종 HEAD에서 실행합니다. CI가 통과하기 전에는 병합하거나 배포하지 않습니다.
2. 사업 모델, 계약·등록, 외부 PG/VAN 연동 승인, 보안·개인정보 책임 경계, 운영 인프라와 키 관리 주체를 확정합니다. 확정 전에는 실제 결제 기능을 열지 않습니다.
3. staging의 격리된 PostgreSQL 백업·복구를 검증하고, 동일 이미지의 독립된 1회성 작업에서 `NURION_PG_MIGRATION_JOB=approved-one-off`와 `NURION_PG_DATABASE_URL`을 제공해 `python scripts/migrate_ops_database.py`를 실행합니다. 작업의 DB 계정만 DDL 권한을 가지며 운영 API 프로세스에는 migration 권한을 부여하지 않습니다.
4. `health/ready`가 현재 migration checksum과 DB 연결을 확인하는지 검사합니다. 실패하면 새 인스턴스는 트래픽을 받지 않습니다. 이전 이미지 digest로 되돌리고 원인을 기록합니다.
5. 운영 환경의 제한 운용 정책, 가맹점 범위, 한도, 승인 증빙과 비밀키는 별도 검증합니다. 비밀값은 저장소·로그·브라우저에 두지 않습니다.
6. Netlify 미리보기와 운영 API의 origin·인증·접근권한을 분리합니다. 공개 대시보드에 합성 지표를 실제 거래처럼 표시하지 않습니다.

이 파일은 배포 실행 또는 외부 결제 승인 증빙이 아닙니다.
