"""Independent synthetic dispute recommendation drafts; never final decisions."""
from __future__ import annotations
from dataclasses import dataclass,field
from enum import StrEnum
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
class ReviewState(StrEnum):OPEN="OPEN";ASSIGNED="ASSIGNED";UNDER_REVIEW="UNDER_REVIEW";RECOMMENDATION_DRAFTED="RECOMMENDATION_DRAFTED"
class Recommendation(StrEnum):ACCEPT_DRAFT="ACCEPT_DRAFT";REJECT_DRAFT="REJECT_DRAFT";PARTIAL_DRAFT="PARTIAL_DRAFT";MORE_EVIDENCE_REQUIRED="MORE_EVIDENCE_REQUIRED"
@dataclass
class Docket:
 docket_id:str;case_id:str;frozen_case_digest:str;evidence_set_digest:str;intake_actor_ref:str;disputed_minor:int;policy_digest:str
 state:ReviewState=ReviewState.OPEN;version:int=1;reviewer_ref:str|None=None;recommendation:Recommendation|None=None;recommended_minor:int|None=None;rationale_code:str|None=None
 def __post_init__(self):
  if not all(isinstance(v,str) and v.startswith("synthetic:") for v in (self.docket_id,self.case_id,self.intake_actor_ref)) or self.disputed_minor<=0 or not all(_d(v) for v in (self.frozen_case_digest,self.evidence_set_digest,self.policy_digest)):raise GovernanceRejected("complete frozen synthetic dispute source required")
@dataclass
class ReviewBook:
 dockets:dict[str,Docket]=field(default_factory=dict);keys:dict[str,str]=field(default_factory=dict);events:list[str]=field(default_factory=list);_lock:RLock=field(default_factory=RLock,repr=False)
 def _once(self,key,p):
  if not key.startswith("synthetic:"):raise GovernanceRejected("synthetic key required")
  d=canonical_digest(p);old=self.keys.get(key)
  if old and old!=d:raise GovernanceRejected("idempotency conflict")
  if old:return False
  self.keys[key]=d;return True
 def open(self,d:Docket,*,source_frozen:bool,key:str):
  with self._lock:
   p={"open":d.docket_id,"case":d.case_id,"frozen":d.frozen_case_digest}
   if not self._once(key,p):return self.dockets[d.docket_id]
   if not source_frozen or d.docket_id in self.dockets or any(x.case_id==d.case_id and x.state is not ReviewState.RECOMMENDATION_DRAFTED for x in self.dockets.values()):raise GovernanceRejected("one active frozen-case docket required")
   self.dockets[d.docket_id]=d;self._event(d,p);return d
 def assign(self,docket_id,reviewer_ref,*,expected_version,key):
  with self._lock:
   d=self._get(docket_id);p={"assign":docket_id,"reviewer":reviewer_ref,"version":expected_version}
   if not self._once(key,p):return d
   if d.version!=expected_version or d.state is not ReviewState.OPEN or not reviewer_ref.startswith("synthetic:reviewer:") or reviewer_ref==d.intake_actor_ref:raise GovernanceRejected("separate reviewer required")
   d.reviewer_ref=reviewer_ref;d.state=ReviewState.ASSIGNED;d.version+=1;self._event(d,p);return d
 def start(self,docket_id,reviewer_ref,*,expected_version,key):
  with self._lock:
   d=self._get(docket_id);p={"start":docket_id,"reviewer":reviewer_ref,"version":expected_version}
   if not self._once(key,p):return d
   if d.version!=expected_version or d.state is not ReviewState.ASSIGNED or d.reviewer_ref!=reviewer_ref:raise GovernanceRejected("assigned reviewer required")
   d.state=ReviewState.UNDER_REVIEW;d.version+=1;self._event(d,p);return d
 def draft(self,docket_id,reviewer_ref,recommendation,recommended_minor,rationale_code,*,expected_version,key):
  with self._lock:
   d=self._get(docket_id);p={"draft":docket_id,"reviewer":reviewer_ref,"recommendation":recommendation.value,"amount":recommended_minor,"rationale":rationale_code,"version":expected_version}
   if not self._once(key,p):return d
   if d.version!=expected_version or d.state is not ReviewState.UNDER_REVIEW or d.reviewer_ref!=reviewer_ref or rationale_code not in {"VALID_EVIDENCE","INVALID_EVIDENCE","PARTIAL_SUPPORT","MORE_DIGESTS_REQUIRED"}:raise GovernanceRejected("valid independent draft required")
   if recommendation is Recommendation.ACCEPT_DRAFT and recommended_minor!=d.disputed_minor or recommendation is Recommendation.REJECT_DRAFT and recommended_minor!=0 or recommendation is Recommendation.PARTIAL_DRAFT and not 0<recommended_minor<d.disputed_minor or recommendation is Recommendation.MORE_EVIDENCE_REQUIRED and recommended_minor!=0:raise GovernanceRejected("recommendation amount mismatch")
   d.recommendation=recommendation;d.recommended_minor=recommended_minor;d.rationale_code=rationale_code;d.state=ReviewState.RECOMMENDATION_DRAFTED;d.version+=1;self._event(d,p);return d
 def _get(self,x):
  try:return self.dockets[x]
  except KeyError as e:raise GovernanceRejected("unknown docket") from e
 def _event(self,d,p):self.events.append(canonical_digest({"sequence":len(self.events)+1,"docket":d.docket_id,"version":d.version,"state":d.state.value,"payload":canonical_digest(p),"previous":self.events[-1] if self.events else "0"*64}))
 def evidence(self):
  v={"schema":"nurion.pg.synthetic-dispute-review-evidence.v1","dockets":[{"docket_id":d.docket_id,"state":d.state.value,"version":d.version,"role_separated":d.reviewer_ref!=d.intake_actor_ref,"recommendation":d.recommendation.value if d.recommendation else None} for d in self.dockets.values()],"event_digests":self.events,"maximum_state":"SYNTHETIC_DISPUTE_RECOMMENDATION_DRAFTED","synthetic_only":True,"decision_final":False,"external_submission_allowed":False,"ledger_adjustment_allowed":False,"refund_allowed":False,"network_used":False,"credentials_accessed":False,"real_money_moved":False};return {**v,"report_digest":canonical_digest(v)}
