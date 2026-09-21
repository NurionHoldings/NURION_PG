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

Until OPS-E03 supplies a persistent repository, the service reads a hash-only JSON registry from `NURION_PG_API_KEYS_JSON`:

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

OPS-E02 has no schema or external side effects. Rollback is a code revert and service restart. OPS-E03 must replace the environment registry with a versioned PostgreSQL principal/API-key repository and durable append-only access audit while preserving these fail-closed contracts.
