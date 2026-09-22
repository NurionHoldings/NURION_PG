from __future__ import annotations
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import psycopg
from nurion_pg.storage.postgres import OutboxRepository,PostgresFoundation,migration_v1_sql
from nurion_pg.payments import PaymentCommand,PaymentService
from nurion_pg.storage.payment_repository import PostgresPaymentRepository


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
        assert connection.execute(f"SELECT version,length(trim(checksum)) FROM {SCHEMA}.schema_migrations ORDER BY version").fetchall()==[(1,64),(2,64),(3,64),(4,64)]
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
        payments=PostgresPaymentRepository(connection,SCHEMA);service=PaymentService(payments)
        created,replayed=service.create("merchant-ci",12500,"KRW","create-payment-1","order-ci",{"channel":"test"})
        assert replayed is False and created.version==1 and created.status.value=="requires_authorization"
        same,replayed=service.create("merchant-ci",12500,"KRW","create-payment-1","order-ci",{"channel":"test"})
        assert replayed is True and same.payment_intent_id==created.payment_intent_id
        try:service.create("merchant-ci",13000,"KRW","create-payment-1","order-ci",{})
        except Exception as exc:assert getattr(exc,"code",None)=="IDEMPOTENCY_CONFLICT"
        else:raise AssertionError("changed idempotent request must conflict")
        pending,replayed=service.request("merchant-ci",created.payment_intent_id,PaymentCommand.AUTHORIZE,None,1,"authorize-payment-1")
        assert replayed is False and pending.status.value=="authorization_pending" and pending.version==2
        try:service.request("merchant-ci",created.payment_intent_id,PaymentCommand.CANCEL,None,2,"cancel-during-authorize")
        except Exception as exc:assert getattr(exc,"code",None)=="INVALID_PAYMENT_STATE"
        else:raise AssertionError("cancel must not overtake an in-flight authorization")
        operation_id=str(connection.execute(f"SELECT operation_id FROM {SCHEMA}.payment_operations WHERE payment_intent_id=%s",(created.payment_intent_id,)).fetchone()[0])
        payments.bind_provider_payment_key("merchant-ci",operation_id,"sandbox-payment-key")
        provider_command=payments.operation_for_provider("merchant-ci",operation_id)
        assert provider_command.amount==12500 and provider_command.payment_key=="sandbox-payment-key" and provider_command.order_id=="order-ci"
        authorized=payments.apply_provider_result("merchant-ci",created.payment_intent_id,operation_id,True,provider_name="toss_payments",provider_payment_key="sandbox-payment-key",provider_status="DONE")
        assert authorized.status.value=="authorized" and authorized.authorized_amount==12500 and authorized.version==3
        provider_row=connection.execute(f"SELECT provider_name,provider_payment_key,provider_status FROM {SCHEMA}.payment_operations WHERE operation_id=%s",(operation_id,)).fetchone()
        assert provider_row==("toss_payments","sandbox-payment-key","DONE")
        capture,_=service.request("merchant-ci",created.payment_intent_id,PaymentCommand.CAPTURE,5000,3,"capture-payment-1")
        capture_operation=str(connection.execute(f"SELECT operation_id FROM {SCHEMA}.payment_operations WHERE payment_intent_id=%s AND operation_type='capture'",(created.payment_intent_id,)).fetchone()[0])
        captured=payments.apply_provider_result("merchant-ci",created.payment_intent_id,capture_operation,True)
        assert capture.status.value=="capture_pending" and captured.status.value=="partially_captured" and captured.captured_amount==5000
        refund,_=service.request("merchant-ci",created.payment_intent_id,PaymentCommand.REFUND,2000,captured.version,"refund-payment-1")
        refund_operation=str(connection.execute(f"SELECT operation_id FROM {SCHEMA}.payment_operations WHERE payment_intent_id=%s AND operation_type='refund'",(created.payment_intent_id,)).fetchone()[0])
        refunded=payments.apply_provider_result("merchant-ci",created.payment_intent_id,refund_operation,True)
        assert refund.status.value=="refund_pending" and refunded.status.value=="partially_refunded" and refunded.refunded_amount==2000
        events=connection.execute(f"SELECT event_type FROM {SCHEMA}.outbox_events WHERE aggregate_type='payment_intent' ORDER BY created_at,event_id").fetchall()
        assert len(events)==7
        assert {row[0] for row in events} >= {"payment_intent.authorize_succeeded","payment_intent.capture_succeeded","payment_intent.refund_succeeded"}
        barrier=Barrier(2)
        def concurrent_create():
            worker=psycopg.connect(connect_timeout=5,autocommit=True)
            try:
                barrier.wait()
                return PaymentService(PostgresPaymentRepository(worker,SCHEMA)).create("merchant-ci",777,"KRW","concurrent-create",None,{})
            finally:worker.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _value:concurrent_create(),range(2)))
        assert results[0][0].payment_intent_id==results[1][0].payment_intent_id
        assert sorted(result[1] for result in results)==[False,True]
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
