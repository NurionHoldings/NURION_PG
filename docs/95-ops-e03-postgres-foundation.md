# OPS-E03 — PostgreSQL, transaction, and Outbox closure (100%)

## Delivered boundary

OPS-E03 adds the first versioned operational schema and atomic repository transaction. It remains isolated from payment execution and external providers.

The migration creates:

- `schema_migrations` for exact version tracking;
- `merchants`, `principals`, and hash-only `api_keys` with foreign keys and status constraints;
- append-oriented `access_audit` metadata;
- transactional `outbox_events` with an unpublished partial index.
- immutable migration checksums and v1→v2 upgrades;
- lease, retry, attempt, and error metadata for reliable dispatch.

## Guarantees

- Migration application is serialized with a PostgreSQL transaction advisory lock.
- Connections must use autocommit mode; every write path opens its own explicit transaction block, preventing caller reads from silently widening transaction scope.
- Reapplying the current migration is idempotent and reports no change.
- Merchant, principal, API-key digest, and provisioning outbox event commit in one transaction.
- A uniqueness or constraint failure rolls the entire provisioning transaction back.
- Rollback removes dependent tables in foreign-key-safe order and then removes the isolated schema.
- Schema identifiers are strictly validated before interpolation; record values use bound parameters.
- Concurrent workers claim disjoint batches with `FOR UPDATE SKIP LOCKED`.
- Publish and failure transitions require lease ownership; expired leases are recoverable.

## CI proof

`scripts/run_ops_postgres_foundation_integration.py` uses the ephemeral PostgreSQL service to prove:

1. historical v1 to v2 upgrade and idempotent reapplication;
2. atomic principal provisioning and outbox creation;
3. full rollback after a duplicate-principal failure;
4. disjoint worker claims, retry/requeue, ownership enforcement, and idempotent publish;
5. checksum-drift rejection and schema removal by the down migration.

## Safety and next gate

No plaintext API key is persisted and no payment state exists. This closure proves the database and delivery mechanics; it does not authorize production deployment or financial operations.
