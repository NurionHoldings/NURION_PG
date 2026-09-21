# NURION_PG #17101~#17500 ETHERNian 독립검수 요청

## 검수 대상

- 정확히 400 controls와 #9901~#17500 직접 evidence chain 19단계
- 두 실제 PostgreSQL backend의 반대 행 잠금 순서와 `40P01` exactly-one
- 피해 transaction rollback·backend close·fresh PID attempt 2 성공
- 실제 blocked-row `55P03` exactly-one과 non-retry 분류
- `deadlock_timeout` 설정 권한·환경 차이의 fail-closed 처리
- actual/unit/harness provenance exact 분리
- actual network partition·failover 미주장
- disposable schema narrow cleanup과 production writes 0
- HOLD별 원인·권고안·대안·비용·위험·가역성·검증·중단·재개·rollback 완결성

## 권한 경계

receipt·signature·key·credential·금융·승인·배포 권한은 없다. 로컬 PostgreSQL이 없으면 통합실증은 정직하게 SKIP이며 원격 전용 service job artifact 전에는 actual PASS를 주장하지 않는다.
