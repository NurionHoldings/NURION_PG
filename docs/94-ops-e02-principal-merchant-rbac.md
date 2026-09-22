# OPS-E02 — Principal, merchant tenancy, and RBAC boundary

## Delivered boundary

OPS-E02 adds fail-closed authentication and authorization to the executable API runtime. It does not add payment mutation, provider connectivity, persistent credentials, or production deployment.

- API keys resolve to an immutable principal, merchant tenant, and role set.
- Only SHA-256 secret digests are loaded; plaintext API-key secrets are not stored or returned.
- inactive, malformed, unknown, and incorrect credentials return `401`.
- a principal cannot access another merchant tenant; cross-tenant requests return `403`.
- authentication and authorization decisions emit metadata-only audit logs without API-key values.
- liveness and readiness probes remain public for orchestrator use.

## Provisioning format

The environment registry remains available for isolated development. Operational persistence is supplied by `PostgresAuthRepository`, which resolves active API keys only when the key, principal, and merchant are all active:

```json
[
  {
    "key_id": "merchant-key-1",
    "secret_sha256": "<64 lowercase hexadecimal characters>",
    "principal_id": "operator-1",
    "merchant_id": "merchant-1",
    "roles": ["merchant_admin"],
    "active": true
  }
]
```

Accepted roles are `merchant_admin`, `payment_operator`, and `auditor`. A presented credential has the form `npg_<key_id>_<secret>` and is sent in `x-api-key`. The plaintext secret must be generated and delivered outside this repository.

## Protected contracts

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/auth/context` | Return the authenticated principal's non-secret context |
| `GET /v1/merchants/{merchant_id}/context` | Prove same-tenant authorization and role enforcement |

The merchant context route is an authorization proof route, not a payment operation.

## Rollback and next gate

OPS-E02 is complete against the ten machine-checked criteria in `config/auth-rbac-closure-v1.json`. The PostgreSQL integration gate proves persistent resolution, wrong-key rejection, rotation, old-key invalidation, revocation, durable audit, and transactional outbox creation. Rollback remains a code/schema rollback; no payment or provider action is authorized.
