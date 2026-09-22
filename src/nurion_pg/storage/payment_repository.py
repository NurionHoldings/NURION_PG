"""PostgreSQL Payment Intent repository with atomic idempotency and Outbox writes."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from nurion_pg.payments import PaymentCommand,PaymentIntent,PaymentProblem,PaymentStatus,PENDING_STATUS,validate_command
from .postgres import _schema


class PostgresPaymentRepository:
    def __init__(self,connection:Any,schema:str="nurion_pg")->None:
        if not connection.autocommit:raise ValueError("PostgresPaymentRepository requires autocommit")
        self.connection=connection;self.schema=_schema(schema)

    @staticmethod
    def _intent(row:tuple[Any,...])->PaymentIntent:
        return PaymentIntent(str(row[0]),row[1],row[2],row[3].strip(),PaymentStatus(row[4]),row[5],row[6],row[7],row[8],row[9],row[10])

    def _get(self,merchant_id:str,payment_intent_id:str,lock:bool=False)->PaymentIntent|None:
        suffix=" FOR UPDATE" if lock else ""
        row=self.connection.execute(f"SELECT payment_intent_id,merchant_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,external_reference,metadata FROM {self.schema}.payment_intents WHERE merchant_id=%s AND payment_intent_id=%s{suffix}",(merchant_id,payment_intent_id)).fetchone()
        return self._intent(row) if row else None

    def get(self,merchant_id:str,payment_intent_id:str)->PaymentIntent|None:return self._get(merchant_id,payment_intent_id)

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
            payload={"operation_id":operation_id,"payment_intent_id":payment_intent_id,"merchant_id":merchant_id,"operation_type":command.value,"amount":amount,"version":updated.version}
            self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'payment_intent',%s,%s,%s::jsonb)",(event_id,payment_intent_id,f"payment_intent.{command.value}_requested",json.dumps(payload)))
            self._receipt(merchant_id,idempotency_key,command.value,request_digest,updated)
        return updated,False

    def apply_provider_result(self,merchant_id:str,payment_intent_id:str,operation_id:str,succeeded:bool)->PaymentIntent:
        """Internal adapter boundary; no public route can fabricate provider success."""
        with self.connection.transaction():
            intent=self._get(merchant_id,payment_intent_id,True)
            op=self.connection.execute(f"SELECT operation_type,amount,status FROM {self.schema}.payment_operations WHERE operation_id=%s AND payment_intent_id=%s AND merchant_id=%s FOR UPDATE",(operation_id,payment_intent_id,merchant_id)).fetchone()
            if intent is None or op is None:raise PaymentProblem(404,"PAYMENT_OPERATION_NOT_FOUND","Payment operation was not found")
            if op[2]!="pending":return intent
            command=PaymentCommand(op[0]);amount=op[1]
            if not succeeded:status=PaymentStatus.FAILED;authorized=intent.authorized_amount;captured=intent.captured_amount;refunded=intent.refunded_amount
            elif command==PaymentCommand.AUTHORIZE:status=PaymentStatus.AUTHORIZED;authorized=intent.amount;captured=intent.captured_amount;refunded=intent.refunded_amount
            elif command==PaymentCommand.CAPTURE:captured=intent.captured_amount+amount;authorized=intent.authorized_amount;refunded=intent.refunded_amount;status=PaymentStatus.CAPTURED if captured==authorized else PaymentStatus.PARTIALLY_CAPTURED
            elif command==PaymentCommand.CANCEL:status=PaymentStatus.CANCELED;authorized=intent.authorized_amount;captured=intent.captured_amount;refunded=intent.refunded_amount
            else:refunded=intent.refunded_amount+amount;authorized=intent.authorized_amount;captured=intent.captured_amount;status=PaymentStatus.REFUNDED if refunded==captured else PaymentStatus.PARTIALLY_REFUNDED
            self.connection.execute(f"UPDATE {self.schema}.payment_operations SET status=%s,completed_at=now() WHERE operation_id=%s",("succeeded" if succeeded else "failed",operation_id))
            row=self.connection.execute(f"UPDATE {self.schema}.payment_intents SET status=%s,authorized_amount=%s,captured_amount=%s,refunded_amount=%s,version=version+1,updated_at=now() WHERE payment_intent_id=%s RETURNING payment_intent_id,merchant_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,external_reference,metadata",(status.value,authorized,captured,refunded,payment_intent_id)).fetchone()
        return self._intent(row)
