"""PostgreSQL webhook inbox, quarantine and operator retry boundary."""
from __future__ import annotations
import json
from typing import Any
from uuid import uuid4
from nurion_pg.payments import PaymentCommand
from nurion_pg.providers import ProviderDisposition
from nurion_pg.storage.postgres import _schema
from nurion_pg.webhook_reconciliation import WebhookEvidence

class PostgresWebhookRepository:
    def __init__(self,connection:Any,payments:Any,schema:str="nurion_pg")->None:
        if not connection.autocommit:raise ValueError("PostgresWebhookRepository requires autocommit")
        self.connection=connection;self.payments=payments;self.schema=_schema(schema)
    def ingest(self,e:WebhookEvidence,sanitized:dict[str,Any])->tuple[str,bool]:
        with self.connection.transaction():
            row=self.connection.execute(f"INSERT INTO {self.schema}.provider_webhook_inbox(inbox_id,merchant_id,provider,event_key,event_type,raw_sha256,payment_key,order_id,provider_status,sanitized_payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(provider,event_key) DO NOTHING RETURNING inbox_id",(str(uuid4()),e.merchant_id,e.provider,e.event_key,e.event_type,e.raw_sha256,e.payment_key,e.order_id,e.provider_status,json.dumps(sanitized))).fetchone()
            if row:return str(row[0]),False
            existing=self.connection.execute(f"SELECT inbox_id,merchant_id,raw_sha256 FROM {self.schema}.provider_webhook_inbox WHERE provider=%s AND event_key=%s",(e.provider,e.event_key)).fetchone()
            if existing[1]!=e.merchant_id or existing[2].strip()!=e.raw_sha256:raise ValueError("webhook idempotency conflict")
            return str(existing[0]),True
    def pending_operation(self,merchant_id:str,payment_key:str)->tuple[str,str,str,int|None,PaymentCommand]|None:
        row=self.connection.execute(f"SELECT o.operation_id,o.payment_intent_id,COALESCE(p.external_reference,p.payment_intent_id::text),p.amount,o.operation_type FROM {self.schema}.payment_operations o JOIN {self.schema}.payment_intents p ON p.payment_intent_id=o.payment_intent_id WHERE o.merchant_id=%s AND o.provider_payment_key=%s AND o.status='pending' ORDER BY o.created_at DESC LIMIT 1",(merchant_id,payment_key)).fetchone()
        return (str(row[0]),str(row[1]),row[2],row[3],PaymentCommand(row[4])) if row else None
    def claim(self,worker_id:str,limit:int=100,lease_seconds:int=60)->list[tuple[str,WebhookEvidence]]:
        if not worker_id or not 1<=limit<=1000 or not 1<=lease_seconds<=3600:raise ValueError("invalid webhook claim")
        sql=f"""WITH candidates AS (SELECT inbox_id FROM {self.schema}.provider_webhook_inbox WHERE state='pending' AND next_attempt_at<=now() AND (leased_at IS NULL OR leased_at<now()-(%s*interval '1 second')) ORDER BY received_at,inbox_id FOR UPDATE SKIP LOCKED LIMIT %s) UPDATE {self.schema}.provider_webhook_inbox i SET lease_owner=%s,leased_at=now(),attempt_count=attempt_count+1 FROM candidates c WHERE i.inbox_id=c.inbox_id RETURNING i.inbox_id,i.merchant_id,i.provider,i.event_key,i.event_type,i.raw_sha256,i.payment_key,i.order_id,i.provider_status,i.received_at"""
        with self.connection.transaction():rows=self.connection.execute(sql,(lease_seconds,limit,worker_id)).fetchall()
        return [(str(r[0]),WebhookEvidence(r[1],r[2],r[3],r[4],r[5].strip(),r[6],r[7],r[8],r[9].isoformat())) for r in rows]
    def resolve(self,inbox_id:str,merchant_id:str,operation_id:str,payment_intent_id:str,result:Any)->None:
        with self.connection.transaction():
            locked=self.connection.execute(f"SELECT state FROM {self.schema}.provider_webhook_inbox WHERE inbox_id=%s AND merchant_id=%s FOR UPDATE",(inbox_id,merchant_id)).fetchone()
            if not locked or locked[0]=="resolved":return
            self.payments.apply_provider_result(merchant_id,payment_intent_id,operation_id,result.disposition==ProviderDisposition.SUCCEEDED,provider_name="toss_payments",provider_payment_key=result.payment_key,provider_status=result.provider_status,provider_error_code=result.code,provider_settled=result.settled)
            self.connection.execute(f"UPDATE {self.schema}.provider_webhook_inbox SET state='resolved',processed_at=now(),last_error=NULL,lease_owner=NULL,leased_at=NULL WHERE inbox_id=%s",(inbox_id,))
    def quarantine(self,inbox_id:str,merchant_id:str,reason:str)->None:
        with self.connection.transaction():self.connection.execute(f"UPDATE {self.schema}.provider_webhook_inbox SET state='quarantined',last_error=%s,next_attempt_at=now()+(LEAST(3600,power(2,LEAST(attempt_count,10))) * interval '1 second'),lease_owner=NULL,leased_at=NULL WHERE inbox_id=%s AND merchant_id=%s AND state!='resolved'",(reason,inbox_id,merchant_id))
    def approve_retry(self,merchant_id:str,inbox_id:str,operator_id:str)->bool:
        if not operator_id:return False
        with self.connection.transaction():
            row=self.connection.execute(f"UPDATE {self.schema}.provider_webhook_inbox SET state='pending',approved_by=%s,approved_at=now(),next_attempt_at=now(),lease_owner=NULL,leased_at=NULL WHERE inbox_id=%s AND merchant_id=%s AND state='quarantined' RETURNING inbox_id",(operator_id,inbox_id,merchant_id)).fetchone()
        return row is not None
