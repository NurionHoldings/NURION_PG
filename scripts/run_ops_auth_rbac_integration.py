from __future__ import annotations
from hashlib import sha256
import psycopg
from nurion_pg.storage import PostgresFoundation
from nurion_pg.storage.auth_repository import PostgresAuthRepository

SCHEMA="nurion_pg_ops_e02_auth_ci"

def main()->None:
    connection=psycopg.connect(connect_timeout=5,autocommit=True);foundation=PostgresFoundation(connection,SCHEMA);foundation.rollback()
    try:
        foundation.migrate_up();foundation.provision_principal("merchant-ci","principal-ci","key-old",sha256(b"old-secret").hexdigest(),["merchant_admin"])
        repository=PostgresAuthRepository(connection,SCHEMA)
        principal=repository.authenticate("npg_key-old_old-secret");assert principal and principal.merchant_id=="merchant-ci"
        assert repository.authenticate("npg_key-old_wrong") is None
        repository.record_audit(principal.principal_id,principal.merchant_id,"tenant:read","allowed","corr-1")
        repository.rotate_key("principal-ci","key-old","key-new",sha256(b"new-secret").hexdigest())
        assert repository.authenticate("npg_key-old_old-secret") is None
        assert repository.authenticate("npg_key-new_new-secret") is not None
        assert repository.revoke_key("principal-ci","key-new") is True
        assert repository.authenticate("npg_key-new_new-secret") is None
        audit=connection.execute(f"SELECT action,outcome,correlation_id FROM {SCHEMA}.access_audit").fetchone();assert audit==("tenant:read","allowed","corr-1")
        event=connection.execute(f"SELECT event_type FROM {SCHEMA}.outbox_events WHERE event_type='api_key.rotated'").fetchone();assert event==("api_key.rotated",)
    finally:foundation.rollback();connection.close()
    print("OPS-E02 persistent auth/RBAC integration: PASS")

if __name__=="__main__":main()
