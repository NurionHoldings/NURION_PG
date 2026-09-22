# Disaster recovery

목표는 RPO 5분, RTO 30분이다. 운영 PostgreSQL은 WAL archive/PITR, AES-256급 저장 암호화, 별도 계정·별도 리전 object lock, 최소권한 복구계정과 보존정책을 인프라에서 구성해야 한다. 저장소는 클라우드 백업이나 암호화를 구성했다고 주장하지 않는다.

장애 선언 후 쓰기 차단, 마지막 정상 WAL/backup 확인, 격리 환경 PITR, migration checksum·schema/data count·Payment 상태·Outbox·원장 균형 검증, 승인 후 DNS/traffic 전환 순으로 failover한다. Failback도 새 backup과 동일 검증 후 수행한다. 모든 명령·승인자·시간·digest를 incident 감사기록에 남긴다.

비밀 회전은 새 자격증명 발급→병행 검증→배포→구 자격증명 폐기→감사 확인 순서이며 로그에 비밀값을 기록하지 않는다.
