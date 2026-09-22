"""Versioned PostgreSQL foundation and transaction-safe outbox."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any
from uuid import uuid4

SCHEMA_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
MIGRATION_VERSION = 4
MIGRATION_LOCK = 73192003


def _schema(value: str) -> str:
    if not SCHEMA_NAME.fullmatch(value):
        raise ValueError("invalid PostgreSQL schema name")
    return value


def migration_v1_sql(schema: str) -> str:
    s = _schema(schema)
    return f"""
CREATE TABLE {s}.merchants (merchant_id text PRIMARY KEY,status text NOT NULL CHECK (status IN ('active','suspended')),created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE {s}.principals (principal_id text PRIMARY KEY,merchant_id text NOT NULL REFERENCES {s}.merchants(merchant_id),status text NOT NULL CHECK (status IN ('active','disabled')),roles jsonb NOT NULL CHECK (jsonb_typeof(roles) = 'array'),created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE {s}.api_keys (key_id text PRIMARY KEY,principal_id text NOT NULL REFERENCES {s}.principals(principal_id),secret_sha256 char(64) NOT NULL CHECK (secret_sha256 ~ '^[0-9a-f]{{64}}$'),active boolean NOT NULL DEFAULT true,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE {s}.access_audit (audit_id uuid PRIMARY KEY,principal_id text,merchant_id text,action text NOT NULL,outcome text NOT NULL CHECK (outcome IN ('allowed','denied')),correlation_id text NOT NULL,occurred_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE {s}.outbox_events (event_id uuid PRIMARY KEY,aggregate_type text NOT NULL,aggregate_id text NOT NULL,event_type text NOT NULL,payload jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),published_at timestamptz);
CREATE INDEX outbox_events_unpublished_idx ON {s}.outbox_events(created_at) WHERE published_at IS NULL;
"""


def migration_v2_sql(schema: str) -> str:
    s = _schema(schema)
    return f"""
ALTER TABLE {s}.outbox_events
 ADD COLUMN available_at timestamptz NOT NULL DEFAULT now(),
 ADD COLUMN attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
 ADD COLUMN lease_owner text, ADD COLUMN leased_at timestamptz, ADD COLUMN last_error text,
 ADD CONSTRAINT outbox_lease_pair CHECK ((lease_owner IS NULL) = (leased_at IS NULL));
DROP INDEX {s}.outbox_events_unpublished_idx;
CREATE INDEX outbox_events_dispatch_idx ON {s}.outbox_events(available_at,created_at) WHERE published_at IS NULL;
"""


def migration_v3_sql(schema: str) -> str:
    s = _schema(schema)
    statuses="'requires_authorization','authorization_pending','authorized','capture_pending','partially_captured','captured','cancel_pending','canceled','refund_pending','partially_refunded','refunded','failed'"
    return f"""
CREATE TABLE {s}.payment_intents (
 payment_intent_id uuid PRIMARY KEY, merchant_id text NOT NULL REFERENCES {s}.merchants(merchant_id),
 amount bigint NOT NULL CHECK (amount > 0), currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{{3}}$'),
 status text NOT NULL CHECK (status IN ({statuses})),
 authorized_amount bigint NOT NULL DEFAULT 0 CHECK (authorized_amount >= 0 AND authorized_amount <= amount),
 captured_amount bigint NOT NULL DEFAULT 0 CHECK (captured_amount >= 0 AND captured_amount <= authorized_amount),
 refunded_amount bigint NOT NULL DEFAULT 0 CHECK (refunded_amount >= 0 AND refunded_amount <= captured_amount),
 version integer NOT NULL DEFAULT 1 CHECK (version > 0), external_reference text,
 metadata jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (merchant_id,payment_intent_id)
);
CREATE INDEX payment_intents_merchant_created_idx ON {s}.payment_intents(merchant_id,created_at DESC);
CREATE TABLE {s}.payment_operations (
 operation_id uuid PRIMARY KEY, payment_intent_id uuid NOT NULL, merchant_id text NOT NULL,
 operation_type text NOT NULL CHECK (operation_type IN ('authorize','capture','cancel','refund')),
 amount bigint CHECK (amount > 0), status text NOT NULL CHECK (status IN ('pending','succeeded','failed')),
 idempotency_key text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 FOREIGN KEY (merchant_id,payment_intent_id) REFERENCES {s}.payment_intents(merchant_id,payment_intent_id),
 UNIQUE (merchant_id,idempotency_key)
);
CREATE TABLE {s}.payment_command_receipts (
 merchant_id text NOT NULL REFERENCES {s}.merchants(merchant_id), idempotency_key text NOT NULL,
 command_type text NOT NULL, request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{{64}}$'),
 response jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (merchant_id,idempotency_key)
);
"""

def migration_v4_sql(schema:str)->str:
    s=_schema(schema)
    return f"""ALTER TABLE {s}.payment_operations ADD COLUMN provider_name text, ADD COLUMN provider_payment_key text, ADD COLUMN provider_status text, ADD COLUMN provider_error_code text;
CREATE INDEX payment_operations_provider_key_idx ON {s}.payment_operations(provider_name,provider_payment_key) WHERE provider_payment_key IS NOT NULL;
"""


def _checksum(version: int) -> str:
    sql = {1:migration_v1_sql,2:migration_v2_sql,3:migration_v3_sql,4:migration_v4_sql}[version]("nurion_pg_checksum")
    return sha256(sql.encode()).hexdigest()


def migration_up_sql(schema: str) -> str:
    """Complete fresh-install SQL retained as the public migration contract."""
    s = _schema(schema)
    return f"""CREATE SCHEMA IF NOT EXISTS {s};
CREATE TABLE IF NOT EXISTS {s}.schema_migrations (version integer PRIMARY KEY,checksum char(64) NOT NULL,applied_at timestamptz NOT NULL DEFAULT now());
{migration_v1_sql(s)}
INSERT INTO {s}.schema_migrations(version,checksum) VALUES (1,'{_checksum(1)}');
{migration_v2_sql(s)}
INSERT INTO {s}.schema_migrations(version,checksum) VALUES (2,'{_checksum(2)}');
{migration_v3_sql(s)}
INSERT INTO {s}.schema_migrations(version,checksum) VALUES (3,'{_checksum(3)}');
{migration_v4_sql(s)}
INSERT INTO {s}.schema_migrations(version,checksum) VALUES (4,'{_checksum(4)}');
"""


def migration_down_sql(schema: str) -> str:
    s = _schema(schema)
    return f"""DROP TABLE IF EXISTS {s}.payment_command_receipts;
DROP TABLE IF EXISTS {s}.payment_operations;
DROP TABLE IF EXISTS {s}.payment_intents;
DROP TABLE IF EXISTS {s}.outbox_events;
DROP TABLE IF EXISTS {s}.access_audit;
DROP TABLE IF EXISTS {s}.api_keys;
DROP TABLE IF EXISTS {s}.principals;
DROP TABLE IF EXISTS {s}.merchants;
DROP TABLE IF EXISTS {s}.schema_migrations;
DROP SCHEMA IF EXISTS {s};
"""


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    attempt_count: int


@dataclass(frozen=True)
class OutboxRepository:
    connection: Any
    schema: str = "nurion_pg"

    def __post_init__(self) -> None:
        _schema(self.schema)
        if not self.connection.autocommit:
            raise ValueError("OutboxRepository requires an autocommit connection")

    def claim(self, worker_id: str, limit: int = 100, lease_seconds: int = 60) -> list[OutboxEvent]:
        if not worker_id or not 1 <= limit <= 1000 or not 1 <= lease_seconds <= 3600:
            raise ValueError("invalid outbox claim parameters")
        sql = f"""WITH candidates AS (
 SELECT event_id FROM {self.schema}.outbox_events WHERE published_at IS NULL AND available_at<=now()
 AND (leased_at IS NULL OR leased_at < now()-(%s*interval '1 second'))
 ORDER BY available_at,created_at,event_id FOR UPDATE SKIP LOCKED LIMIT %s
) UPDATE {self.schema}.outbox_events o SET lease_owner=%s,leased_at=now(),attempt_count=attempt_count+1
FROM candidates c WHERE o.event_id=c.event_id
RETURNING o.event_id,o.aggregate_type,o.aggregate_id,o.event_type,o.payload,o.attempt_count"""
        with self.connection.transaction():
            rows = self.connection.execute(sql, (lease_seconds, limit, worker_id)).fetchall()
        return [OutboxEvent(str(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in rows]

    def mark_published(self, event_id: str, worker_id: str) -> bool:
        with self.connection.transaction():
            row = self.connection.execute(
                f"UPDATE {self.schema}.outbox_events SET published_at=now(),lease_owner=NULL,leased_at=NULL,last_error=NULL WHERE event_id=%s AND published_at IS NULL AND lease_owner=%s RETURNING event_id",
                (event_id, worker_id),
            ).fetchone()
        return row is not None

    def mark_failed(self, event_id: str, worker_id: str, error: str, retry_seconds: int = 30) -> bool:
        if not error or not 0 <= retry_seconds <= 86400:
            raise ValueError("invalid outbox failure parameters")
        with self.connection.transaction():
            row = self.connection.execute(
                f"UPDATE {self.schema}.outbox_events SET available_at=now()+(%s*interval '1 second'),lease_owner=NULL,leased_at=NULL,last_error=%s WHERE event_id=%s AND published_at IS NULL AND lease_owner=%s RETURNING event_id",
                (retry_seconds, error[:4000], event_id, worker_id),
            ).fetchone()
        return row is not None


@dataclass(frozen=True)
class PostgresFoundation:
    connection: Any
    schema: str = "nurion_pg"

    def __post_init__(self) -> None:
        _schema(self.schema)
        if not self.connection.autocommit:
            raise ValueError("PostgresFoundation requires an autocommit connection; writes use explicit transaction blocks")

    def migrate_up(self) -> bool:
        changed = False
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
            self.connection.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
            self.connection.execute(f"CREATE TABLE IF NOT EXISTS {self.schema}.schema_migrations (version integer PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())")
            columns = {r[0] for r in self.connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name='schema_migrations'", (self.schema,)).fetchall()}
            if "checksum" not in columns:
                self.connection.execute(f"ALTER TABLE {self.schema}.schema_migrations ADD COLUMN checksum char(64)")
                self.connection.execute(f"UPDATE {self.schema}.schema_migrations SET checksum=%s WHERE version=1", (_checksum(1),))
            rows = dict(self.connection.execute(f"SELECT version,checksum FROM {self.schema}.schema_migrations ORDER BY version").fetchall())
            unknown = set(rows) - {1, 2, 3, 4}
            if unknown:
                raise RuntimeError(f"unsupported database migration versions: {sorted(unknown)}")
            for version, sql in ((1, migration_v1_sql(self.schema)), (2, migration_v2_sql(self.schema)), (3, migration_v3_sql(self.schema)), (4,migration_v4_sql(self.schema))):
                expected = _checksum(version)
                if version in rows:
                    if rows[version].strip() != expected:
                        raise RuntimeError(f"migration checksum drift at version {version}")
                    continue
                self.connection.execute(sql)
                self.connection.execute(f"INSERT INTO {self.schema}.schema_migrations(version,checksum) VALUES (%s,%s)", (version, expected))
                changed = True
            self.connection.execute(f"ALTER TABLE {self.schema}.schema_migrations ALTER COLUMN checksum SET NOT NULL")
        return changed

    def rollback(self) -> None:
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
            self.connection.execute(migration_down_sql(self.schema))

    def provision_principal(self, merchant_id: str, principal_id: str, key_id: str, secret_sha256: str, roles: list[str]) -> str:
        event_id = str(uuid4())
        with self.connection.transaction():
            self.connection.execute(f"INSERT INTO {self.schema}.merchants(merchant_id,status) VALUES (%s,'active')", (merchant_id,))
            self.connection.execute(f"INSERT INTO {self.schema}.principals(principal_id,merchant_id,status,roles) VALUES (%s,%s,'active',%s::jsonb)", (principal_id, merchant_id, json.dumps(roles)))
            self.connection.execute(f"INSERT INTO {self.schema}.api_keys(key_id,principal_id,secret_sha256) VALUES (%s,%s,%s)", (key_id, principal_id, secret_sha256))
            self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'principal',%s,'principal.provisioned',%s::jsonb)", (event_id, principal_id, json.dumps({"merchant_id": merchant_id,"principal_id": principal_id,"key_id": key_id,"roles": roles})))
        return event_id
