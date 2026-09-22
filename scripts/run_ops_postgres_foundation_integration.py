from __future__ import annotations
from hashlib import sha256
import psycopg
from nurion_pg.storage.postgres import OutboxRepository,PostgresFoundation,migration_v1_sql


SCHEMA="nurion_pg_ops_e03_ci"


def main()->None:
    connection=psycopg.connect(connect_timeout=5,autocommit=True)
    foundation=PostgresFoundation(connection,SCHEMA)
    foundation.rollback()
    try:
        with connection.transaction():
            connection.execute(f"CREATE SCHEMA {SCHEMA}")
            connection.execute(f"CREATE TABLE {SCHEMA}.schema_migrations (version integer PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())")
            connection.execute(migration_v1_sql(SCHEMA))
            connection.execute(f"INSERT INTO {SCHEMA}.schema_migrations(version) VALUES (1)")
        assert foundation.migrate_up() is True
        assert foundation.migrate_up() is False
        assert connection.execute(f"SELECT version,length(trim(checksum)) FROM {SCHEMA}.schema_migrations ORDER BY version").fetchall()==[(1,64),(2,64)]
        event_id=foundation.provision_principal("merchant-ci","principal-ci","key-ci",sha256(b"ci-secret").hexdigest(),["merchant_admin"])
        principal=connection.execute(f"SELECT merchant_id,status,roles FROM {SCHEMA}.principals WHERE principal_id='principal-ci'").fetchone()
        event=connection.execute(f"SELECT aggregate_id,event_type,payload,published_at FROM {SCHEMA}.outbox_events WHERE event_id=%s",(event_id,)).fetchone()
        assert principal[0:2]==("merchant-ci","active")
        assert principal[2]==["merchant_admin"]
        assert event[0:2]==("principal-ci","principal.provisioned") and event[3] is None
        try:
            foundation.provision_principal("merchant-rollback","principal-ci","key-rollback",sha256(b"other").hexdigest(),["auditor"])
        except psycopg.errors.UniqueViolation:pass
        else:raise AssertionError("duplicate principal must fail")
        assert connection.execute(f"SELECT count(*) FROM {SCHEMA}.merchants WHERE merchant_id='merchant-rollback'").fetchone()[0]==0
        repository=OutboxRepository(connection,SCHEMA)
        foundation.provision_principal("merchant-ci-2","principal-ci-2","key-ci-2",sha256(b"ci-secret-2").hexdigest(),["auditor"])
        first=repository.claim("worker-a",1);second=repository.claim("worker-b",1)
        assert len(first)==len(second)==1 and first[0].event_id!=second[0].event_id
        assert repository.mark_published(first[0].event_id,"worker-b") is False
        assert repository.mark_published(first[0].event_id,"worker-a") is True
        assert repository.mark_published(first[0].event_id,"worker-a") is False
        assert repository.mark_failed(second[0].event_id,"worker-b","temporary",0) is True
        retry=repository.claim("worker-c",1)
        assert retry[0].event_id==second[0].event_id and retry[0].attempt_count==2
        assert repository.mark_published(retry[0].event_id,"worker-c") is True
        connection.execute(f"UPDATE {SCHEMA}.schema_migrations SET checksum=%s WHERE version=1",("0"*64,))
        try:foundation.migrate_up()
        except RuntimeError:pass
        else:raise AssertionError("migration checksum drift must fail closed")
    finally:
        foundation.rollback();connection.close()
    verify=psycopg.connect(connect_timeout=5,autocommit=True)
    assert verify.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s",(SCHEMA,)).fetchone() is None
    verify.close()
    print("OPS-E03 PostgreSQL foundation integration: PASS")


if __name__=="__main__":main()
