# Operator Audit Repository Planning Lock (#471–#485)

Status: `PLANNING_LOCK` / `UNREGISTERED_SYNTHETIC_ONLY`

## Scope

The future repository may persist only the already-sealed synthetic operator-intent audit checkpoint. This document authorizes no implementation, migration execution, database connection, deployment, or production use.

## Locked architecture

- Domain port isolated from storage adapters
- PostgreSQL adapter as the future authoritative implementation target
- SQLite adapter for regression and SQLite-after-PG verification only
- Alembic migration with fresh upgrade and downgrade→re-upgrade verification
- Append-only evidence export with content-addressed digests

## Locked invariants

- immutable rows and monotonic sequence
- unique checkpoint and idempotency keys
- previous-digest chain verification
- serializable or locked-equivalent single-winner writes
- tamper detection and role-separated review

## Acceptance gates

A later implementation PR must pass concurrency, fresh-schema, idempotency, rollback, tamper, and PostgreSQL/SQLite type-parity tests. It must use synthetic fixtures without PII or operating credentials.

## Exclusions

No live traffic, external API, card network, money movement, ledger posting, policy mutation, persistent production data, merge, or deployment is authorized.
