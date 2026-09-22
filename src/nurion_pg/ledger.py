"""Append-only balanced ledger and settlement/payout domain rules."""
from __future__ import annotations
from dataclasses import dataclass,replace
from enum import StrEnum
from hashlib import sha256
import json,re
from typing import Protocol

CURRENCY=re.compile(r"^[A-Z]{3}$")
class LedgerError(ValueError):pass
class Side(StrEnum):DEBIT="debit";CREDIT="credit"
@dataclass(frozen=True)
class Entry:account:str;side:Side;amount:int
@dataclass(frozen=True)
class Journal:
 journal_id:str;merchant_id:str;currency:str;kind:str;reference_id:str;entries:tuple[Entry,...];reversal_of:str|None=None
 def validate(self)->None:
  if not self.merchant_id or not CURRENCY.fullmatch(self.currency):raise LedgerError("invalid journal identity")
  if len(self.entries)<2 or any(isinstance(e.amount,bool) or e.amount<=0 for e in self.entries):raise LedgerError("invalid entries")
  debit=sum(e.amount for e in self.entries if e.side==Side.DEBIT);credit=sum(e.amount for e in self.entries if e.side==Side.CREDIT)
  if debit!=credit:raise LedgerError("journal is not balanced")
 def digest(self)->str:
  self.validate();return sha256(json.dumps({"merchant":self.merchant_id,"currency":self.currency,"kind":self.kind,"reference":self.reference_id,"reversal_of":self.reversal_of,"entries":[(e.account,e.side,e.amount) for e in self.entries]},separators=(",",":"),sort_keys=True).encode()).hexdigest()

def capture_journal(journal_id:str,merchant_id:str,currency:str,reference_id:str,amount:int,platform_fee:int,pg_fee:int)->Journal:
 merchant=amount-platform_fee-pg_fee
 if min(amount,merchant)>=1 and min(platform_fee,pg_fee)>=0:
  entries=[Entry("provider_receivable",Side.DEBIT,amount),Entry("merchant_payable",Side.CREDIT,merchant)]
  if platform_fee:entries.append(Entry("platform_fee_revenue",Side.CREDIT,platform_fee))
  if pg_fee:entries.append(Entry("pg_fee_payable",Side.CREDIT,pg_fee))
  result=Journal(journal_id,merchant_id,currency,"capture",reference_id,tuple(entries));result.validate();return result
 raise LedgerError("fees exceed capture")
def refund_journal(journal_id:str,merchant_id:str,currency:str,reference_id:str,amount:int)->Journal:
 result=Journal(journal_id,merchant_id,currency,"refund",reference_id,(Entry("merchant_payable",Side.DEBIT,amount),Entry("provider_receivable",Side.CREDIT,amount)));result.validate();return result
def reversal(journal_id:str,original:Journal)->Journal:
 entries=tuple(Entry(e.account,Side.CREDIT if e.side==Side.DEBIT else Side.DEBIT,e.amount) for e in original.entries)
 result=Journal(journal_id,original.merchant_id,original.currency,"reversal",original.reference_id,entries,original.journal_id);result.validate();return result

class SettlementState(StrEnum):DRAFT="draft";REVIEW="review";APPROVED="approved";PAYABLE="payable";PAID="paid";HELD="held";ADJUSTED="adjusted";CANCELED="canceled"
@dataclass(frozen=True)
class Settlement:
 settlement_id:str;merchant_id:str;currency:str;amount:int;reserve:int;state:SettlementState=SettlementState.DRAFT;version:int=1;hold_reason:str|None=None
 @property
 def payable_amount(self)->int:return self.amount-self.reserve
 def transition(self,target:SettlementState,*,reconciliation_clear:bool=True)->"Settlement":
  allowed={SettlementState.DRAFT:{SettlementState.REVIEW,SettlementState.CANCELED},SettlementState.REVIEW:{SettlementState.APPROVED,SettlementState.HELD,SettlementState.CANCELED},SettlementState.APPROVED:{SettlementState.PAYABLE,SettlementState.HELD},SettlementState.PAYABLE:{SettlementState.PAID,SettlementState.HELD},SettlementState.HELD:{SettlementState.ADJUSTED,SettlementState.CANCELED},SettlementState.ADJUSTED:{SettlementState.REVIEW,SettlementState.CANCELED}}
  if target not in allowed.get(self.state,set()):raise LedgerError("invalid settlement transition")
  if target in {SettlementState.APPROVED,SettlementState.PAYABLE,SettlementState.PAID} and not reconciliation_clear:raise LedgerError("reconciliation difference requires hold")
  return replace(self,state=target,version=self.version+1,hold_reason=None)
 def hold(self,reason:str)->"Settlement":
  if self.state not in {SettlementState.REVIEW,SettlementState.APPROVED,SettlementState.PAYABLE}:raise LedgerError("settlement cannot be held")
  return replace(self,state=SettlementState.HELD,version=self.version+1,hold_reason=reason)

@dataclass(frozen=True)
class PayoutRequest:
 payout_id:str;settlement_id:str;merchant_id:str;currency:str;amount:int;requested_by:str;idempotency_key:str;approvals:tuple[str,...]=();state:str="pending_approval"
 def approve(self,principal_id:str)->"PayoutRequest":
  if principal_id==self.requested_by:raise LedgerError("self approval is forbidden")
  if principal_id in self.approvals:return self
  approvals=self.approvals+(principal_id,);return replace(self,approvals=approvals,state="approved" if len(approvals)>=2 else self.state)
 def mark_paid(self)->"PayoutRequest":raise LedgerError("bank payout adapter is not connected")

def available_balance(merchant_payable:int,pending:int,reserve:int,hold:int)->int:return max(0,merchant_payable-pending-reserve-hold)
