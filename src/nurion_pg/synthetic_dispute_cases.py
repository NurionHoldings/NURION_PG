"""Synthetic dispute intake and evidence freeze; no external submission."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from enum import StrEnum
from .arkaon.governance import GovernanceRejected,canonical_digest
def _digest(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
class DisputeState(StrEnum):DRAFT="DRAFT";ELIGIBILITY_VERIFIED="ELIGIBILITY_VERIFIED";EVIDENCE_FROZEN="EVIDENCE_FROZEN"
@dataclass(frozen=True)
class DisputeEvent:sequence:int;case_id:str;version:int;state:DisputeState;payload_digest:str;previous_digest:str;event_digest:str
@dataclass
class DisputeCase:
 case_id:str;intent_id:str;merchant_ref:str;reason_code:str;disputed_minor:int;currency:str;deadline:datetime;policy_digest:str;snapshot_digest:str
 state:DisputeState=DisputeState.DRAFT;version:int=1;evidence_refs:tuple[str,...]=()
 def __post_init__(self):
  if not all(isinstance(v,str) and v.startswith("synthetic:") for v in (self.case_id,self.intent_id,self.merchant_ref)) or not self.reason_code or self.disputed_minor<=0 or len(self.currency)!=3 or self.currency!=self.currency.upper() or self.deadline.tzinfo is None or not _digest(self.policy_digest) or not _digest(self.snapshot_digest):raise GovernanceRejected("complete synthetic dispute required")
@dataclass
class SyntheticDisputeBook:
 cases:dict[str,DisputeCase]=field(default_factory=dict);events:list[DisputeEvent]=field(default_factory=list);keys:dict[str,str]=field(default_factory=dict)
 def _command(self,key,payload):
  if not isinstance(key,str) or not key.startswith("synthetic:"):raise GovernanceRejected("synthetic idempotency key required")
  digest=canonical_digest(payload);old=self.keys.get(key)
  if old and old!=digest:raise GovernanceRejected("idempotency payload conflict")
  if old:return False
  self.keys[key]=digest;return True
 def open(self,case:DisputeCase,*,available_minor:int,snapshot_valid:bool,now:datetime,idempotency_key:str):
  payload={"case_id":case.case_id,"snapshot":case.snapshot_digest,"amount":case.disputed_minor}
  if not self._command(idempotency_key,payload):return self.cases[case.case_id]
  if case.case_id in self.cases or now.tzinfo is None or case.deadline<=now or not snapshot_valid or available_minor<case.disputed_minor:raise GovernanceRejected("eligible captured synthetic amount required")
  self.cases[case.case_id]=case;self._emit(case,payload);return case
 def verify(self,case_id:str,*,expected_version:int,idempotency_key:str):
  case=self._get(case_id);payload={"case_id":case_id,"version":expected_version,"command":"verify"}
  if not self._command(idempotency_key,payload):return case
  if case.version!=expected_version or case.state is not DisputeState.DRAFT:raise GovernanceRejected("draft version required")
  case.state=DisputeState.ELIGIBILITY_VERIFIED;case.version+=1;self._emit(case,payload);return case
 def freeze(self,case_id:str,refs:tuple[str,...],*,expected_version:int,idempotency_key:str):
  case=self._get(case_id);payload={"case_id":case_id,"version":expected_version,"refs":refs}
  if not self._command(idempotency_key,payload):return case
  if case.version!=expected_version or case.state is not DisputeState.ELIGIBILITY_VERIFIED or not refs or tuple(sorted(set(refs)))!=refs or any(not _digest(x) for x in refs):raise GovernanceRejected("ordered unique evidence digests required")
  case.evidence_refs=refs;case.state=DisputeState.EVIDENCE_FROZEN;case.version+=1;self._emit(case,payload);return case
 def _get(self,case_id):
  try:return self.cases[case_id]
  except KeyError as e:raise GovernanceRejected("unknown dispute") from e
 def _emit(self,case,payload):
  prev=self.events[-1].event_digest if self.events else "0"*64;seq=len(self.events)+1;pd=canonical_digest(payload);v={"sequence":seq,"case_id":case.case_id,"version":case.version,"state":case.state.value,"payload_digest":pd,"previous_digest":prev};self.events.append(DisputeEvent(seq,case.case_id,case.version,case.state,pd,prev,canonical_digest(v)))
 def evidence(self):
  v={"schema":"nurion.pg.synthetic-dispute-evidence.v1","cases":[{"case_id":c.case_id,"state":c.state.value,"version":c.version,"evidence_set_digest":canonical_digest(c.evidence_refs)} for c in self.cases.values()],"event_digests":[e.event_digest for e in self.events],"maximum_state":"SYNTHETIC_EVIDENCE_FROZEN","synthetic_only":True,"read_only_source":True,"provider_adapter_present":False,"external_submission_allowed":False,"real_money_moved":False,"production_activation_allowed":False};return {**v,"report_digest":canonical_digest(v)}
