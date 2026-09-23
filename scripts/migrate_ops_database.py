"""Explicit, one-off database migration step before an API rollout.

Never run this script from the API container entrypoint or a health probe.
"""
from __future__ import annotations

import os

from nurion_pg.storage.postgres import PostgresFoundation


def main() -> None:
    if os.environ.get("NURION_PG_MIGRATION_JOB") != "approved-one-off":
        raise SystemExit("migration job authorization is required")
    url = os.environ.get("NURION_PG_DATABASE_URL", "")
    schema = os.environ.get("NURION_PG_DATABASE_SCHEMA", "nurion_pg")
    if not url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("PostgreSQL URL is required")
    import psycopg

    with psycopg.connect(url, connect_timeout=5, autocommit=True) as connection:
        foundation = PostgresFoundation(connection, schema)
        foundation.migrate_up()
        if not foundation.is_current():
            raise SystemExit("migration verification failed")
    print("database schema verified")


if __name__ == "__main__":
    main()
