# NURION_PG #16701~#17100 ETHERNian 독립검수 요청

## 검수 대상

- 정확히 400 controls와 #9901~#17100 직접 evidence chain 18단계
- SQLSTATE taxonomy의 retry/commit-unknown/fail-closed 분리
- 최대 3회·rollback/close·fresh connection 및 exhaustion 차단
- 실제 PostgreSQL `40001` 재현의 결정성, 실패/재시도 backend PID 분리
- 실제 `57014` timeout 비재시도
- harness-injected post-commit response loss라는 공개 경계와 exact read-back
- actual network partition/deadlock 미주장
- 실제 DB 증거(`40001` 1회→attempt 2, `57014` 1회)와 unit/harness 주입 증거(exhaustion, response loss)의 exact provenance 분리
- fresh read-back은 `EXISTING_SAME_PAYLOAD`+exact digest만 수락하고 `INSERTED`를 포함한 나머지는 거부
- disposable schema cleanup 및 production writes 0
- HOLD별 원인·권고안·대안·비용·위험·가역성·검증·중단·재개·rollback 완결성

## 권한 경계

receipt·signature·key·credential·금융·승인·배포 권한은 없다. 로컬 PostgreSQL이 없으면 통합실증은 정직하게 SKIP이며, 원격 전용 service job의 artifact가 나오기 전 실제 PostgreSQL PASS를 주장하지 않는다.
