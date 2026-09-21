# OPS-E03 — Operational PostgreSQL foundation

## Delivered boundary

OPS-E03 adds the first versioned operational schema and atomic repository transaction. It remains isolated from payment execution and external providers.

The migration creates:

- `schema_migrations` for exact version tracking;
- `merchants`, `principals`, and hash-only `api_keys` with foreign keys and status constraints;
- append-oriented `access_audit` metadata;
- transactional `outbox_events` with an unpublished partial index.

## Guarantees

- Migration application is serialized with a PostgreSQL transaction advisory lock.
- Connections must use autocommit mode; every write path opens its own explicit transaction block, preventing caller reads from silently widening transaction scope.
- Reapplying the current migration is idempotent and reports no change.
- Merchant, principal, API-key digest, and provisioning outbox event commit in one transaction.
- A uniqueness or constraint failure rolls the entire provisioning transaction back.
- Rollback removes dependent tables in foreign-key-safe order and then removes the isolated schema.
- Schema identifiers are strictly validated before interpolation; record values use bound parameters.

## CI proof

`scripts/run_ops_postgres_foundation_integration.py` uses the ephemeral PostgreSQL service to prove:

1. clean rollback and fresh migration;
2. idempotent reapplication;
3. atomic principal provisioning and outbox creation;
4. full rollback after a duplicate-principal failure;
5. schema removal by the down migration.

## Safety and next gate

No route writes these tables yet, no plaintext API key is persisted, and no payment state exists. OPS-E04 may build Payment Intent APIs only after wiring runtime connection lifecycle, repository error mapping, idempotency storage, and tenant-scoped queries onto this foundation.
