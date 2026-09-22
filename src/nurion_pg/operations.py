"""Merchant-scoped operations console and fail-closed limited-operation gate."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any
from .storage.postgres import _schema

IDENTIFIER=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")

@dataclass(frozen=True)
class LimitedOperationPolicy:
 enabled:bool=False
 allowed_merchants:frozenset[str]=frozenset()
 max_amount:int=0
 approval_receipt_sha256:str=""
 @classmethod
 def from_values(cls,enabled:bool,merchants:str,max_amount:int,receipt:str):
  values=frozenset(x.strip() for x in merchants.split(",") if x.strip())
  if enabled and (not values or any(not IDENTIFIER.fullmatch(x) for x in values) or max_amount<=0 or not re.fullmatch(r"[0-9a-f]{64}",receipt)):raise ValueError("limited-operation certification evidence is incomplete")
  return cls(enabled,values,max_amount,receipt)
 def require(self,merchant_id:str,amount:int|None=None)->None:
  if not self.enabled:raise PermissionError("limited operation is disabled")
  if merchant_id not in self.allowed_merchants:raise PermissionError("merchant is outside the certified cohort")
  if amount is not None and amount>self.max_amount:raise PermissionError("amount exceeds the certified limit")
 def public_view(self)->dict[str,object]:return {"enabled":self.enabled,"cohort_size":len(self.allowed_merchants),"max_amount":self.max_amount if self.enabled else 0,"approval_evidence_present":bool(self.approval_receipt_sha256),"live_money_movement":False}

class PostgresOperationsRepository:
 def __init__(self,connection:Any,schema:str="nurion_pg")->None:self.connection=connection;self.schema=_schema(schema)
 @staticmethod
 def _limit(value:int,maximum:int=100)->int:
  if not 1<=value<=maximum:raise ValueError("invalid limit")
  return value
 def payments(self,merchant_id:str,status:str|None=None,limit:int=50)->list[dict]:
  limit=self._limit(limit)
  rows=self.connection.execute(f"SELECT payment_intent_id,amount,currency,status,authorized_amount,captured_amount,refunded_amount,version,created_at,updated_at FROM {self.schema}.payment_intents WHERE merchant_id=%s AND (%s IS NULL OR status=%s) ORDER BY created_at DESC,payment_intent_id DESC LIMIT %s",(merchant_id,status,status,limit)).fetchall()
  return [{"payment_intent_id":str(r[0]),"amount":r[1],"currency":r[2].strip(),"status":r[3],"authorized_amount":r[4],"captured_amount":r[5],"refunded_amount":r[6],"version":r[7],"created_at":r[8].isoformat(),"updated_at":r[9].isoformat()} for r in rows]
 def webhooks(self,merchant_id:str,state:str="quarantined",limit:int=50)->list[dict]:
  limit=self._limit(limit)
  if state not in {"pending","resolved","quarantined"}:raise ValueError("invalid webhook state")
  rows=self.connection.execute(f"SELECT inbox_id,provider,event_type,provider_status,state,attempt_count,last_error,received_at,approved_by,approved_at FROM {self.schema}.provider_webhook_inbox WHERE merchant_id=%s AND state=%s ORDER BY received_at DESC LIMIT %s",(merchant_id,state,limit)).fetchall()
  return [{"inbox_id":str(r[0]),"provider":r[1],"event_type":r[2],"provider_status":r[3],"state":r[4],"attempt_count":r[5],"last_error":r[6],"received_at":r[7].isoformat(),"approved_by":r[8],"approved_at":r[9].isoformat() if r[9] else None} for r in rows]
 def settlements(self,merchant_id:str,state:str|None=None,limit:int=50)->list[dict]:
  limit=self._limit(limit)
  rows=self.connection.execute(f"SELECT settlement_id,currency,cycle_start,cycle_end,amount,reserve,state,version,hold_reason,created_at FROM {self.schema}.settlements WHERE merchant_id=%s AND (%s IS NULL OR state=%s) ORDER BY created_at DESC LIMIT %s",(merchant_id,state,state,limit)).fetchall()
  return [{"settlement_id":str(r[0]),"currency":r[1].strip(),"cycle_start":r[2].isoformat(),"cycle_end":r[3].isoformat(),"amount":r[4],"reserve":r[5],"state":r[6],"version":r[7],"hold_reason":r[8],"created_at":r[9].isoformat()} for r in rows]
 def audits(self,merchant_id:str,limit:int=100)->list[dict]:
  limit=self._limit(limit)
  rows=self.connection.execute(f"SELECT audit_id,principal_id,action,outcome,correlation_id,occurred_at FROM {self.schema}.access_audit WHERE merchant_id=%s ORDER BY occurred_at DESC LIMIT %s",(merchant_id,limit)).fetchall()
  return [{"audit_id":str(r[0]),"principal_id":r[1],"action":r[2],"outcome":r[3],"correlation_id":r[4],"occurred_at":r[5].isoformat()} for r in rows]
 def approve_webhook_retry(self,merchant_id:str,inbox_id:str,principal_id:str,correlation_id:str)->bool:
  with self.connection.transaction():
   row=self.connection.execute(f"UPDATE {self.schema}.provider_webhook_inbox SET state='pending',approved_by=%s,approved_at=now(),next_attempt_at=now(),lease_owner=NULL,leased_at=NULL WHERE inbox_id=%s AND merchant_id=%s AND state='quarantined' RETURNING inbox_id",(principal_id,inbox_id,merchant_id)).fetchone()
   if row:self.connection.execute(f"INSERT INTO {self.schema}.access_audit(audit_id,principal_id,merchant_id,action,outcome,correlation_id) VALUES (gen_random_uuid(),%s,%s,'webhook:retry','allowed',%s)",(principal_id,merchant_id,correlation_id))
  return row is not None
