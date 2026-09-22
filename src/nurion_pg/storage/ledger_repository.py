"""PostgreSQL append-only ledger repository."""
from __future__ import annotations
from typing import Any
from nurion_pg.ledger import CURRENCY,Journal,LedgerError,SettlementState
from nurion_pg.storage.postgres import _schema

class PostgresLedgerRepository:
 def __init__(self,connection:Any,schema:str="nurion_pg")->None:
  if not connection.autocommit:raise ValueError("PostgresLedgerRepository requires autocommit")
  self.connection=connection;self.schema=_schema(schema)
 def post(self,journal:Journal)->tuple[str,bool]:
  journal.validate();digest=journal.digest()
  with self.connection.transaction():
   self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(f"ledger:{journal.merchant_id}:{journal.reference_id}:{journal.kind}",))
   existing=self.connection.execute(f"SELECT journal_id,journal_digest FROM {self.schema}.ledger_journals WHERE merchant_id=%s AND reference_id=%s AND kind=%s",(journal.merchant_id,journal.reference_id,journal.kind)).fetchone()
   if existing:
    if existing[1].strip()!=digest:raise LedgerError("journal idempotency conflict")
    return str(existing[0]),True
   self.connection.execute(f"INSERT INTO {self.schema}.ledger_journals(journal_id,merchant_id,currency,kind,reference_id,reversal_of,journal_digest) VALUES (%s,%s,%s,%s,%s,%s,%s)",(journal.journal_id,journal.merchant_id,journal.currency,journal.kind,journal.reference_id,journal.reversal_of,digest))
   for sequence,e in enumerate(journal.entries,1):self.connection.execute(f"INSERT INTO {self.schema}.ledger_entries(journal_id,sequence,account,side,amount) VALUES (%s,%s,%s,%s,%s)",(journal.journal_id,sequence,e.account,e.side.value,e.amount))
   self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (gen_random_uuid(),'ledger_journal',%s,'ledger.journal_posted',jsonb_build_object('journal_id',%s,'merchant_id',%s,'currency',%s,'kind',%s))",(journal.journal_id,journal.journal_id,journal.merchant_id,journal.currency,journal.kind))
  return journal.journal_id,False
 def balance(self,merchant_id:str,currency:str,account:str)->int:
  row=self.connection.execute(f"SELECT COALESCE(sum(CASE WHEN e.side='credit' THEN e.amount ELSE -e.amount END),0) FROM {self.schema}.ledger_entries e JOIN {self.schema}.ledger_journals j USING(journal_id) WHERE j.merchant_id=%s AND j.currency=%s AND e.account=%s",(merchant_id,currency,account)).fetchone();return row[0]

class PostgresSettlementRepository:
 def __init__(self,connection:Any,schema:str="nurion_pg")->None:
  if not connection.autocommit:raise ValueError("PostgresSettlementRepository requires autocommit")
  self.connection=connection;self.schema=_schema(schema)
 def available(self,merchant_id:str,currency:str)->int:
  payable=self.connection.execute(f"SELECT COALESCE(sum(CASE WHEN e.side='credit' THEN e.amount ELSE -e.amount END),0) FROM {self.schema}.ledger_entries e JOIN {self.schema}.ledger_journals j USING(journal_id) WHERE j.merchant_id=%s AND j.currency=%s AND e.account='merchant_payable'",(merchant_id,currency)).fetchone()[0]
  committed=self.connection.execute(f"SELECT COALESCE(sum(amount),0) FROM {self.schema}.payout_requests WHERE merchant_id=%s AND currency=%s AND state IN ('pending_approval','approved')",(merchant_id,currency)).fetchone()[0]
  reserves=self.connection.execute(f"SELECT COALESCE(sum(CASE WHEN state='held' THEN amount ELSE reserve END),0) FROM {self.schema}.settlements WHERE merchant_id=%s AND currency=%s AND state NOT IN ('paid','canceled')",(merchant_id,currency)).fetchone()[0]
  return max(0,payable-committed-reserves)
 def create_draft(self,settlement_id:str,merchant_id:str,currency:str,cycle_start:str,cycle_end:str,amount:int,reserve:int)->None:
  if not CURRENCY.fullmatch(currency) or cycle_end<cycle_start or amount<0 or reserve<0 or reserve>amount:raise LedgerError("invalid settlement draft")
  with self.connection.transaction():self.connection.execute(f"INSERT INTO {self.schema}.settlements(settlement_id,merchant_id,currency,cycle_start,cycle_end,amount,reserve,state) VALUES (%s,%s,%s,%s,%s,%s,%s,'draft')",(settlement_id,merchant_id,currency,cycle_start,cycle_end,amount,reserve))
 def transition(self,settlement_id:str,merchant_id:str,target:SettlementState,expected_version:int,*,reconciliation_difference:int=0,reason:str|None=None)->str:
  if target==SettlementState.PAID:raise LedgerError("bank payout adapter is not connected")
  allowed={"draft":{"review","canceled"},"review":{"approved","held","canceled"},"approved":{"payable","held"},"payable":{"paid","held"},"held":{"adjusted","canceled"},"adjusted":{"review","canceled"}}
  with self.connection.transaction():
   row=self.connection.execute(f"SELECT state,version FROM {self.schema}.settlements WHERE settlement_id=%s AND merchant_id=%s FOR UPDATE",(settlement_id,merchant_id)).fetchone()
   if not row or row[1]!=expected_version:raise LedgerError("settlement version conflict")
   actual=SettlementState.HELD.value if reconciliation_difference else target.value
   if actual not in allowed.get(row[0],set()):raise LedgerError("invalid settlement transition")
   hold=(reason or "RECONCILIATION_DIFFERENCE") if actual=="held" else None
   self.connection.execute(f"UPDATE {self.schema}.settlements SET state=%s,version=version+1,hold_reason=%s WHERE settlement_id=%s",(actual,hold,settlement_id))
   self.connection.execute(f"INSERT INTO {self.schema}.outbox_events(event_id,aggregate_type,aggregate_id,event_type,payload) VALUES (gen_random_uuid(),'settlement',%s,%s,jsonb_build_object('settlement_id',%s,'merchant_id',%s,'state',%s,'version',%s))",(settlement_id,f"settlement.{actual}",settlement_id,merchant_id,actual,expected_version+1))
  return actual
 def create_payout(self,payout_id:str,settlement_id:str,merchant_id:str,currency:str,amount:int,requested_by:str,key:str,roles:set[str])->tuple[str,bool]:
  if "payout_requester" not in roles:raise PermissionError("payout requester role required")
  if amount<=0:raise LedgerError("invalid payout amount")
  with self.connection.transaction():
   self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",(f"payout:{merchant_id}:{currency}",))
   existing=self.connection.execute(f"SELECT payout_id,settlement_id,amount,requested_by FROM {self.schema}.payout_requests WHERE merchant_id=%s AND idempotency_key=%s",(merchant_id,key)).fetchone()
   if existing:
    if (str(existing[1]),existing[2],existing[3])!=(settlement_id,amount,requested_by):raise LedgerError("payout idempotency conflict")
    return str(existing[0]),True
   state=self.connection.execute(f"SELECT state,currency,amount,reserve FROM {self.schema}.settlements WHERE settlement_id=%s AND merchant_id=%s FOR UPDATE",(settlement_id,merchant_id)).fetchone()
   if not state or state[0]!="payable":raise LedgerError("settlement is not payable")
   if state[1].strip()!=currency:raise LedgerError("settlement currency mismatch")
   prior=self.connection.execute(f"SELECT COALESCE(sum(amount),0) FROM {self.schema}.payout_requests WHERE settlement_id=%s AND state IN ('pending_approval','approved')",(settlement_id,)).fetchone()[0]
   if amount>state[2]-state[3]-prior:raise LedgerError("payout exceeds settlement remainder")
   if amount>self.available(merchant_id,currency):raise LedgerError("insufficient available balance")
   self.connection.execute(f"INSERT INTO {self.schema}.payout_requests(payout_id,settlement_id,merchant_id,currency,amount,requested_by,idempotency_key,state) VALUES (%s,%s,%s,%s,%s,%s,%s,'pending_approval')",(payout_id,settlement_id,merchant_id,currency,amount,requested_by,key))
  return payout_id,False
 def approve_payout(self,payout_id:str,merchant_id:str,principal_id:str,roles:set[str])->str:
  if "payout_approver" not in roles:raise PermissionError("payout approver role required")
  with self.connection.transaction():
   row=self.connection.execute(f"SELECT requested_by,state FROM {self.schema}.payout_requests WHERE payout_id=%s AND merchant_id=%s FOR UPDATE",(payout_id,merchant_id)).fetchone()
   if not row:raise LedgerError("payout not found")
   if row[1] not in {"pending_approval","approved"}:raise LedgerError("payout is not approvable")
   if row[0]==principal_id:raise LedgerError("self approval is forbidden")
   self.connection.execute(f"INSERT INTO {self.schema}.payout_approvals(payout_id,principal_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",(payout_id,principal_id))
   count=self.connection.execute(f"SELECT count(*) FROM {self.schema}.payout_approvals WHERE payout_id=%s",(payout_id,)).fetchone()[0]
   state="approved" if count>=2 else "pending_approval";self.connection.execute(f"UPDATE {self.schema}.payout_requests SET state=%s WHERE payout_id=%s",(state,payout_id));return state
 def mark_paid(self,*_args,**_kwargs):raise LedgerError("bank payout adapter is not connected")
