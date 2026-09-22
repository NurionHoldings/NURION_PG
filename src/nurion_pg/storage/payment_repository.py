"""PostgreSQL Payment Intent repository with atomic idempotency and Outbox writes."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4,uuid5,NAMESPACE_URL

from nurion_pg.payments import PaymentCommand,PaymentIntent,PaymentProblem,PaymentStatus,PENDING_STATUS,validate_command
from .postgres import _schema
from nurion_pg.providers import ProviderCommand


class PostgresPaymentRepository:
    def __init__(self,connection:Any,schema:str="nurion_pg",ledger_repository:Any|None=None)->None:
        if not connection.autocommit:raise ValueError("PostgresPaymentRepository requires autocommit")
        self.connection=connection;self.schema=_schema(schema);self.ledger_repository=ledger_repository

    @staticmethod
    def _intent(row:tuple[Any,...])->PaymentIntent:
        return PaymentIntent(str(row[0]),row[1],row[2],row[3].strip(),PaymentStatus(row[4]),row[5],row[6],row[7],row[8],row[9],row[10])

    def _get(self,merchant_id:str,payment_intent_id:str,lock:bool=False)->PaymentIntent|None:
        suffix=" FOR UPDATE" if lock else ""
        row=self.connection.execute(f"SELECT payment_intent_id,merchant_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,external_reference,metadata FROM {self.schema}.payment_intents WHERE merchant_id=%s AND payment_intent_id=%s{suffix}",(merchant_id,payment_intent_id)).fetchone()
        return self._intent(row) if row else None

    def get(self,merchant_id:str,payment_intent_id:str)->PaymentIntent|None:return self._get(merchant_id,payment_intent_id)

    def operation_for_provider(self,merchant_id:str,operation_id:str)->ProviderCommand:
        row=self.connection.execute(f"SELECT o.operation_id,o.payment_intent_id,o.operation_type,CASE WHEN o.operation_type='authorize' THEN p.amount ELSE o.amount END,p.currency,p.external_reference,o.provider_payment_key FROM {self.schema}.payment_operations o JOIN {self.schema}.payment_intents p ON p.payment_intent_id=o.payment_intent_id WHERE o.operation_id=%s AND o.merchant_id=%s AND o.status='pending'",(operation_id,merchant_id)).fetchone()
        if row is None:raise PaymentProblem(404,"PAYMENT_OPERATION_NOT_FOUND","Pending payment operation was not found")
        return ProviderCommand(str(row[0]),str(row[1]),PaymentCommand(row[2]),row[3],row[4].strip(),row[5] or str(row[1]),row[6])

    def bind_provider_payment_key(self,merchant_id:str,operation_id:str,payment_key:str,order_id:str|None=None,amount:int|None=None,*,principal_id:str|None=None)->None:
        """Bind the browser-returned opaque key before dispatch; it is never exposed publicly."""
        if not payment_key or len(payment_key)>200:raise PaymentProblem(422,"INVALID_PROVIDER_PAYMENT_KEY","Provider payment key is invalid")
        with self.connection.transaction():
            expected=self.connection.execute(f"SELECT COALESCE(p.external_reference,p.payment_intent_id::text),p.amount,o.operation_type,o.provider_payment_key FROM {self.schema}.payment_operations o JOIN {self.schema}.payment_intents p ON p.payment_intent_id=o.payment_intent_id WHERE o.operation_id=%s AND o.merchant_id=%s AND o.status='pending' FOR UPDATE",(operation_id,merchant_id)).fetchone()
            if not expected or (order_id is not None and order_id!=expected[0]) or (amount is not None and amount!=expected[1]) or expected[2]!="authorize":raise PaymentProblem(409,"PROVIDER_CALLBACK_MISMATCH","Provider callback does not match the pending payment")
            if expected[3] is not None:
                if expected[3]==payment_key:return
                raise PaymentProblem(409,"PROVIDER_BIND_CONFLICT","Another provider key is already bound")
            row=self.connection.execute(f"UPDATE {self.schema}.payment_operations SET provider_payment_key=%s WHERE operation_id=%s AND merchant_id=%s AND status='pending' AND provider_payment_key IS NULL RETURNING operation_id",(payment_key,operation_id,merchant_id)).fetchone()
            if row is None:raise PaymentProblem(409,"PROVIDER_BIND_CONFLICT","Provider key cannot be bound to this operation")
            payload={"operation_id":operation_id,"merchant_id":merchant_id,"order_id":expected[0]};self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'payment_operation',%s,'payment_operation.provider_key_bound',%s::jsonb)",(str(uuid4()),operation_id,json.dumps(payload)))
            if principal_id:self.connection.execute(f"INSERT INTO {self.schema}.access_audit(audit_id,principal_id,merchant_id,action,outcome,correlation_id) VALUES (%s,%s,%s,'payment.provider_callback','allowed',%s)",(str(uuid4()),principal_id,merchant_id,operation_id))

    def claim_provider_operations(self,worker_id:str,limit:int=20,lease_seconds:int=60)->list[tuple[str,str]]:
        sql=f"""WITH c AS (SELECT operation_id FROM {self.schema}.payment_operations WHERE status='pending' AND dead_lettered_at IS NULL AND next_attempt_at<=now() AND provider_payment_key IS NOT NULL AND (leased_at IS NULL OR leased_at<now()-(%s*interval '1 second')) ORDER BY next_attempt_at,created_at FOR UPDATE SKIP LOCKED LIMIT %s) UPDATE {self.schema}.payment_operations o SET lease_owner=%s,leased_at=now(),dispatch_attempts=dispatch_attempts+1 FROM c WHERE o.operation_id=c.operation_id RETURNING o.merchant_id,o.operation_id"""
        with self.connection.transaction():rows=self.connection.execute(sql,(lease_seconds,limit,worker_id)).fetchall()
        return [(r[0],str(r[1])) for r in rows]

    def defer_provider_operation(self,merchant_id:str,operation_id:str,worker_id:str,error:str,max_attempts:int=8)->None:
        reconcile=error in {"TRANSPORT_UNKNOWN","ALREADY_PROCESSED_PAYMENT","PROVIDER_RESPONSE_MISMATCH","PROVIDER_STATUS_MISMATCH"}
        with self.connection.transaction():
            row=self.connection.execute(f"UPDATE {self.schema}.payment_operations SET next_attempt_at=now()+(LEAST(3600,power(2,LEAST(dispatch_attempts,10))) * interval '1 second'),last_dispatch_error=%s,reconciliation_required=reconciliation_required OR %s,lease_owner=NULL,leased_at=NULL,dead_lettered_at=CASE WHEN dispatch_attempts>=%s THEN now() ELSE dead_lettered_at END WHERE operation_id=%s AND merchant_id=%s AND status='pending' AND lease_owner=%s RETURNING dead_lettered_at",(error[:200],reconcile,max_attempts,operation_id,merchant_id,worker_id)).fetchone()
            if row:
                event="payment_operation.dead_lettered" if row[0] is not None else "payment_operation.deferred";payload={"operation_id":operation_id,"merchant_id":merchant_id,"error_code":error[:200]}
                self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'payment_operation',%s,%s,%s::jsonb)",(str(uuid4()),operation_id,event,json.dumps(payload)))

    def reconciliation_required(self,merchant_id:str,operation_id:str)->bool:
        row=self.connection.execute(f"SELECT reconciliation_required FROM {self.schema}.payment_operations WHERE operation_id=%s AND merchant_id=%s AND status='pending'",(operation_id,merchant_id)).fetchone();return bool(row and row[0])

    def _replay(self,merchant_id:str,key:str,command_type:str,digest:str)->PaymentIntent|None:
        row=self.connection.execute(f"SELECT command_type,request_digest,response FROM {self.schema}.payment_command_receipts WHERE merchant_id=%s AND idempotency_key=%s",(merchant_id,key)).fetchone()
        if not row:return None
        if row[0]!=command_type or row[1].strip()!=digest:raise PaymentProblem(409,"IDEMPOTENCY_CONFLICT","Idempotency-Key was already used with another request")
        value=row[2];return PaymentIntent(value["payment_intent_id"],value["merchant_id"],value["amount"],value["currency"],PaymentStatus(value["status"]),value["authorized_amount"],value["captured_amount"],value["refunded_amount"],value["version"],value.get("external_reference"),value.get("metadata") or {})

    def _receipt(self,merchant_id:str,key:str,command_type:str,digest:str,intent:PaymentIntent)->None:
        self.connection.execute(f"INSERT INTO {self.schema}.payment_command_receipts(merchant_id,idempotency_key,command_type,request_digest,response) VALUES (%s,%s,%s,%s,%s::jsonb)",(merchant_id,key,command_type,digest,json.dumps(intent.public_view())))

    def create(self,merchant_id:str,amount:int,currency:str,idempotency_key:str,request_digest:str,external_reference:str|None,metadata:dict[str,Any])->tuple[PaymentIntent,bool]:
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(f"{merchant_id}:{idempotency_key}",))
            replay=self._replay(merchant_id,idempotency_key,"create",request_digest)
            if replay:return replay,True
            payment_id=str(uuid4());event_id=str(uuid4())
            row=self.connection.execute(f"INSERT INTO {self.schema}.payment_intents(payment_intent_id,merchant_id,amount,currency,status,external_reference,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING payment_intent_id,merchant_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,external_reference,metadata",(payment_id,merchant_id,amount,currency,PaymentStatus.REQUIRES_AUTHORIZATION.value,external_reference,json.dumps(metadata))).fetchone()
            intent=self._intent(row)
            self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'payment_intent',%s,'payment_intent.created',%s::jsonb)",(event_id,payment_id,json.dumps(intent.public_view())))
            self._receipt(merchant_id,idempotency_key,"create",request_digest,intent)
        return intent,False

    def request(self,merchant_id:str,payment_intent_id:str,command:PaymentCommand,amount:int|None,expected_version:int,idempotency_key:str,request_digest:str)->tuple[PaymentIntent,bool]:
        with self.connection.transaction():
            self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(f"{merchant_id}:{idempotency_key}",))
            replay=self._replay(merchant_id,idempotency_key,command.value,request_digest)
            if replay:return replay,True
            intent=self._get(merchant_id,payment_intent_id,True)
            if intent is None:raise PaymentProblem(404,"PAYMENT_INTENT_NOT_FOUND","Payment Intent was not found")
            if intent.version!=expected_version:raise PaymentProblem(409,"VERSION_CONFLICT","Payment Intent version has changed")
            amount=validate_command(intent,command,amount);next_status=PENDING_STATUS[command]
            operation_id=str(uuid4());event_id=str(uuid4())
            row=self.connection.execute(f"UPDATE {self.schema}.payment_intents SET status=%s,version=version+1,updated_at=now() WHERE payment_intent_id=%s AND merchant_id=%s AND version=%s RETURNING payment_intent_id,merchant_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,external_reference,metadata",(next_status.value,payment_intent_id,merchant_id,expected_version)).fetchone()
            if row is None:raise PaymentProblem(409,"VERSION_CONFLICT","Payment Intent version has changed")
            updated=self._intent(row)
            self.connection.execute(f"INSERT INTO {self.schema}.payment_operations(operation_id,payment_intent_id,merchant_id,operation_type,amount,status,idempotency_key) VALUES (%s,%s,%s,%s,%s,'pending',%s)",(operation_id,payment_intent_id,merchant_id,command.value,amount,idempotency_key))
            if command in {PaymentCommand.CANCEL,PaymentCommand.REFUND}:
                self.connection.execute(f"UPDATE {self.schema}.payment_operations o SET provider_payment_key=(SELECT provider_payment_key FROM {self.schema}.payment_operations prior WHERE prior.payment_intent_id=%s AND prior.provider_payment_key IS NOT NULL ORDER BY prior.created_at DESC LIMIT 1) WHERE o.operation_id=%s",(payment_intent_id,operation_id))
            payload={"operation_id":operation_id,"payment_intent_id":payment_intent_id,"merchant_id":merchant_id,"operation_type":command.value,"amount":amount,"version":updated.version}
            self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'payment_intent',%s,%s,%s::jsonb)",(event_id,payment_intent_id,f"payment_intent.{command.value}_requested",json.dumps(payload)))
            if command==PaymentCommand.CANCEL and intent.status==PaymentStatus.REQUIRES_AUTHORIZATION:
                self.connection.execute(f"UPDATE {self.schema}.payment_operations SET status='succeeded',completed_at=now() WHERE operation_id=%s",(operation_id,))
                row=self.connection.execute(f"UPDATE {self.schema}.payment_intents SET status=%s,version=version+1,updated_at=now() WHERE payment_intent_id=%s RETURNING payment_intent_id,merchant_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,external_reference,metadata",(PaymentStatus.CANCELED.value,payment_intent_id)).fetchone();updated=self._intent(row)
                complete_payload={**payload,"operation_status":"succeeded","payment_status":updated.status.value,"version":updated.version,"local_only":True}
                self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'payment_intent',%s,'payment_intent.cancel_succeeded',%s::jsonb)",(str(uuid4()),payment_intent_id,json.dumps(complete_payload)))
            self._receipt(merchant_id,idempotency_key,command.value,request_digest,updated)
        return updated,False

    def apply_provider_result(self,merchant_id:str,payment_intent_id:str,operation_id:str,succeeded:bool,*,provider_name:str|None=None,provider_payment_key:str|None=None,provider_status:str|None=None,provider_error_code:str|None=None,provider_settled:bool=False)->PaymentIntent:
        """Internal adapter boundary; no public route can fabricate provider success."""
        with self.connection.transaction():
            intent=self._get(merchant_id,payment_intent_id,True)
            op=self.connection.execute(f"SELECT operation_type,amount,status FROM {self.schema}.payment_operations WHERE operation_id=%s AND payment_intent_id=%s AND merchant_id=%s FOR UPDATE",(operation_id,payment_intent_id,merchant_id)).fetchone()
            if intent is None or op is None:raise PaymentProblem(404,"PAYMENT_OPERATION_NOT_FOUND","Payment operation was not found")
            if op[2]!="pending":return intent
            command=PaymentCommand(op[0]);amount=op[1]
            expected_pending=PENDING_STATUS[command]
            if intent.status!=expected_pending:raise PaymentProblem(409,"PROVIDER_RESULT_STATE_CONFLICT","Payment Intent is not awaiting this provider result")
            authorized=intent.authorized_amount;captured=intent.captured_amount;refunded=intent.refunded_amount
            if not succeeded:
                if command==PaymentCommand.AUTHORIZE:status=PaymentStatus.REQUIRES_AUTHORIZATION
                elif command==PaymentCommand.CAPTURE:status=PaymentStatus.PARTIALLY_CAPTURED if captured else PaymentStatus.AUTHORIZED
                elif command==PaymentCommand.CANCEL:status=PaymentStatus.AUTHORIZED if authorized else PaymentStatus.REQUIRES_AUTHORIZATION
                else:status=PaymentStatus.PARTIALLY_REFUNDED if refunded else (PaymentStatus.CAPTURED if captured==authorized else PaymentStatus.PARTIALLY_CAPTURED)
            elif command==PaymentCommand.AUTHORIZE:
                authorized=intent.amount;captured=intent.amount if provider_settled else intent.captured_amount;refunded=intent.refunded_amount
                status=PaymentStatus.CAPTURED if provider_settled else PaymentStatus.AUTHORIZED
            elif command==PaymentCommand.CAPTURE:captured=intent.captured_amount+amount;authorized=intent.authorized_amount;refunded=intent.refunded_amount;status=PaymentStatus.CAPTURED if captured==authorized else PaymentStatus.PARTIALLY_CAPTURED
            elif command==PaymentCommand.CANCEL:status=PaymentStatus.CANCELED;authorized=intent.authorized_amount;captured=intent.captured_amount;refunded=intent.refunded_amount
            else:refunded=intent.refunded_amount+amount;authorized=intent.authorized_amount;captured=intent.captured_amount;status=PaymentStatus.REFUNDED if refunded==captured else PaymentStatus.PARTIALLY_REFUNDED
            operation_status="succeeded" if succeeded else "failed"
            self.connection.execute(f"UPDATE {self.schema}.payment_operations SET status=%s,completed_at=now(),provider_name=%s,provider_payment_key=COALESCE(%s,provider_payment_key),provider_status=%s,provider_error_code=%s WHERE operation_id=%s",(operation_status,provider_name,provider_payment_key,provider_status,provider_error_code,operation_id))
            row=self.connection.execute(f"UPDATE {self.schema}.payment_intents SET status=%s,authorized_amount=%s,captured_amount=%s,refunded_amount=%s,version=version+1,updated_at=now() WHERE payment_intent_id=%s RETURNING payment_intent_id,merchant_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,external_reference,metadata",(status.value,authorized,captured,refunded,payment_intent_id)).fetchone()
            updated=self._intent(row)
            payload={"operation_id":operation_id,"payment_intent_id":payment_intent_id,"merchant_id":merchant_id,"operation_type":command.value,"operation_status":operation_status,"payment_status":updated.status.value,"version":updated.version}
            self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'payment_intent',%s,%s,%s::jsonb)",(str(uuid4()),payment_intent_id,f"payment_intent.{command.value}_{operation_status}",json.dumps(payload)))
            if succeeded and self.ledger_repository is not None and (command==PaymentCommand.REFUND or command==PaymentCommand.AUTHORIZE and provider_settled):
                from nurion_pg.ledger import capture_journal,refund_journal
                journal_id=str(uuid5(NAMESPACE_URL,"nurion-pg:operation:"+operation_id));journal=(capture_journal(journal_id,merchant_id,intent.currency,operation_id,intent.amount,0,0) if command==PaymentCommand.AUTHORIZE else refund_journal(journal_id,merchant_id,intent.currency,operation_id,amount));self.ledger_repository.post(journal)
        return updated
