# OPS-E09 배포·관측·DR

환경별 manifest는 `repository@sha256:<digest>`만 허용하고 non-root, read-only rootfs, 최소 capability, startup/readiness/liveness와 graceful rolling update를 정의한다. Migration은 기존 advisory lock 아래 backup 확인→backward-compatible migration→canary→rollout 순서다. 실제 image registry push나 Kubernetes 배포는 수행하지 않았다.

CI는 고정 SHA Action, compile/test, SBOM 생성, manifest/closure 검증, disposable PostgreSQL backup→drop→restore drill 증거를 생성한다. 운영 image build 시 base image digest를 release evidence에 고정해야 하며 source에는 비밀을 포함하지 않는다.

관측 계약은 API latency/error, payment queue/lease/dead-letter, webhook/quarantine, Provider latency/circuit/UNKNOWN, Outbox lag, 원장 불균형, 정산 hold/payout, DB/migration을 포함한다. Alert는 각 Runbook으로 연결된다.

운영 백업은 인프라에서 PITR/WAL, 암호화된 offsite·object-lock·별도 계정으로 구성해야 한다. 저장소는 이를 이미 구성했다고 주장하지 않는다. DR drill은 일회용 PostgreSQL에서 schema/data/checksum/원장/Payment/Outbox 불변식과 RPO/RTO를 검증한다.
