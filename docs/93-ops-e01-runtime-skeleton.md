# OPS-E01 — API runtime skeleton

## Delivered boundary

OPS-E01 introduces an executable HTTP service boundary for the production build track. It does **not** authorize or execute payments, cancellations, refunds, settlements, provider calls, or production deployment.

The runtime provides:

- a FastAPI application factory;
- liveness and readiness probes;
- correlation-ID generation and propagation;
- a stable, non-sensitive internal-error envelope;
- environment validation and production-disabled interactive documentation;
- a non-root container image definition;
- CI installation and API smoke coverage.

## Local run

```bash
python -m pip install ".[test]"
NURION_PG_ENV=development nurion-pg-api
```

The default listener is `127.0.0.1:8080`. Override it with `NURION_PG_HOST` and `NURION_PG_PORT`.

## Health contract

| Endpoint | Success | Failure meaning |
| --- | --- | --- |
| `GET /health/live` | `200`, process is serving HTTP | No response means the process is unavailable |
| `GET /health/ready` | `200`, runtime is accepting traffic | `503` means a dependency or controlled startup gate is not ready |

Every HTTP response carries `x-correlation-id`. A valid caller-supplied ASCII value of 1–128 characters is preserved; invalid input is replaced.

## Container verification

```bash
docker build -t nurion-pg-api:ops-e01 .
docker run --rm -p 8080:8080 nurion-pg-api:ops-e01
```

## Rollback

No schema, external system, or payment state is changed by OPS-E01. Rollback is therefore limited to stopping the service or reverting this commit. The previous synthetic evidence tooling remains intact.

## Next gate

OPS-E02 may add authenticated principal, merchant tenancy, and role boundaries. Payment mutation routes remain prohibited until the identity, persistence, and provider-adapter gates are separately reviewed.

## Runtime closure

The OPS-E01 runtime scope is complete against the ten machine-checked criteria in `config/runtime-closure-v1.json`: executable entrypoint, validated settings, three health probes, correlation propagation, stable errors, request-size bounds, security headers, secret-free runtime metadata, graceful termination, and a non-root health-checked container. `scripts/validate_runtime_closure.py` enforces this boundary in CI. Runtime completion does not imply payment execution or production deployment readiness.
