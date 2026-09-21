"""Versioned PostgreSQL foundation for operational data."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any
from uuid import uuid4


SCHEMA_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
MIGRATION_VERSION = 1


def _schema(value: str) -> str:
    if not SCHEMA_NAME.fullmatch(value):
        raise ValueError("invalid PostgreSQL schema name")
    return value


def migration_up_sql(schema: str) -> str:
    s=_schema(schema)
    return f"""
CREATE SCHEMA IF NOT EXISTS {s};
CREATE TABLE IF NOT EXISTS {s}.schema_migrations (
  version integer PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE {s}.merchants (
  merchant_id text PRIMARY KEY,
  status text NOT NULL CHECK (status IN ('active','suspended')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE {s}.principals (
  principal_id text PRIMARY KEY,
  merchant_id text NOT NULL REFERENCES {s}.merchants(merchant_id),
  status text NOT NULL CHECK (status IN ('active','disabled')),
  roles jsonb NOT NULL CHECK (jsonb_typeof(roles) = 'array'),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE {s}.api_keys (
  key_id text PRIMARY KEY,
  principal_id text NOT NULL REFERENCES {s}.principals(principal_id),
  secret_sha256 char(64) NOT NULL CHECK (secret_sha256 ~ '^[0-9a-f]{{64}}$'),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE {s}.access_audit (
  audit_id uuid PRIMARY KEY,
  principal_id text,
  merchant_id text,
  action text NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('allowed','denied')),
  correlation_id text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE {s}.outbox_events (
  event_id uuid PRIMARY KEY,
  aggregate_type text NOT NULL,
  aggregate_id text NOT NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
CREATE INDEX outbox_events_unpublished_idx ON {s}.outbox_events(created_at) WHERE published_at IS NULL;
INSERT INTO {s}.schema_migrations(version) VALUES ({MIGRATION_VERSION});
"""


def migration_down_sql(schema: str) -> str:
    s=_schema(schema)
    return f"""
DROP TABLE IF EXISTS {s}.outbox_events;
DROP TABLE IF EXISTS {s}.access_audit;
DROP TABLE IF EXISTS {s}.api_keys;
DROP TABLE IF EXISTS {s}.principals;
DROP TABLE IF EXISTS {s}.merchants;
DROP TABLE IF EXISTS {s}.schema_migrations;
DROP SCHEMA IF EXISTS {s};
"""


@dataclass(frozen=True)
class PostgresFoundation:
    connection: Any
    schema: str = "nurion_pg"

    def __post_init__(self) -> None:_schema(self.schema)

    def migrate_up(self) -> bool:
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(%s)",(73192003,))
            self.connection.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
            self.connection.execute(f"CREATE TABLE IF NOT EXISTS {self.schema}.schema_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            found=self.connection.execute(f"SELECT 1 FROM {self.schema}.schema_migrations WHERE version=%s",(MIGRATION_VERSION,)).fetchone()
            if found:return False
            self.connection.execute(migration_up_sql(self.schema))
        return True

    def rollback(self) -> None:
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(%s)",(73192003,))
            self.connection.execute(migration_down_sql(self.schema))

    def provision_principal(self,merchant_id:str,principal_id:str,key_id:str,secret_sha256:str,roles:list[str])->str:
        event_id=str(uuid4())
        with self.connection.transaction():
            self.connection.execute(f"INSERT INTO {self.schema}.merchants(merchant_id,status) VALUES (%s,'active')",(merchant_id,))
            self.connection.execute(f"INSERT INTO {self.schema}.principals(principal_id,merchant_id,status,roles) VALUES (%s,%s,'active',%s::jsonb)",(principal_id,merchant_id,json.dumps(roles)))
            self.connection.execute(f"INSERT INTO {self.schema}.api_keys(key_id,principal_id,secret_sha256) VALUES (%s,%s,%s)",(key_id,principal_id,secret_sha256))
            self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'principal',%s,'principal.provisioned',%s::jsonb)",(event_id,principal_id,json.dumps({"merchant_id":merchant_id,"principal_id":principal_id,"key_id":key_id,"roles":roles})))
        return event_id
