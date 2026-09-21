from __future__ import annotations
from hashlib import sha256
import os
import psycopg
from nurion_pg.storage.postgres import PostgresFoundation


SCHEMA="nurion_pg_ops_e03_ci"


def main()->None:
    connection=psycopg.connect(connect_timeout=5)
    foundation=PostgresFoundation(connection,SCHEMA)
    foundation.rollback()
    try:
        assert foundation.migrate_up() is True
        assert foundation.migrate_up() is False
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
    finally:
        foundation.rollback();connection.close()
    verify=psycopg.connect(connect_timeout=5)
    assert verify.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s",(SCHEMA,)).fetchone() is None
    verify.close()
    print("OPS-E03 PostgreSQL foundation integration: PASS")


if __name__=="__main__":main()
