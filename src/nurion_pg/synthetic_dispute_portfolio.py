"""Integrated synthetic dispute portfolio #353-#365; no operational effects."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from decimal import Decimal
from .arkaon.governance import GovernanceRejected,canonical_digest
def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
@dataclass(frozen=True)
class Artifact:feature:int;state:str;payload:dict[str,object];previous_digest:str;digest:str
@dataclass
class DisputePortfolio:
 case_id:str;merchant_ref:str;currency:str;disputed_minor:int;frozen_digest:str;review_digest:str
 artifacts:list[Artifact]=field(default_factory=list)
 def __post_init__(self):
  if not self.case_id.startswith("synthetic:") or not self.merchant_ref.startswith("synthetic:") or len(self.currency)!=3 or self.disputed_minor<=0 or not _d(self.frozen_digest) or not _d(self.review_digest):raise GovernanceRejected("complete synthetic dispute lineage required")
 def _add(self,feature,state,payload):
  expected=353+len(self.artifacts)
  if feature!=expected:raise GovernanceRejected("continuous dispute feature required")
  prev=self.artifacts[-1].digest if self.artifacts else self.review_digest
  value={"feature":feature,"state":state,"payload":payload,"previous_digest":prev}
  a=Artifact(feature,state,payload,prev,canonical_digest(value));self.artifacts.append(a);return a
 def supplement(self,old_refs,new_refs,request_digest):
  if not _d(request_digest) or not old_refs or not new_refs or set(old_refs)&set(new_refs) or tuple(sorted(set(old_refs+new_refs)))!=tuple(sorted(old_refs+new_refs)) or any(not _d(x) for x in old_refs+new_refs):raise GovernanceRejected("append-only evidence supplement required")
  return self._add(353,"SUPPLEMENT_FROZEN",{"old":old_refs,"added":new_refs,"set_digest":canonical_digest(tuple(sorted(old_refs+new_refs))),"request_digest":request_digest})
 def merchant_response(self,codes,deadline_valid):
  if not deadline_valid or not codes or tuple(sorted(set(codes)))!=codes or any(x not in {"SERVICE_PROVIDED","CUSTOMER_AUTHORIZED","REFUND_ALREADY_ISSUED","NO_SUPPORT"} for x in codes):raise GovernanceRejected("allowlisted timely response codes required")
  return self._add(354,"MERCHANT_RESPONSE_PACKAGE_DRAFTED",{"codes":codes,"content_absent":True})
 def sla(self,received_at,deadline,now):
  if any(x.tzinfo is None for x in (received_at,deadline,now)) or not received_at<=now or deadline<=received_at:raise GovernanceRejected("deterministic aware SLA times required")
  status="EXPIRED" if now>deadline else "AT_RISK" if (deadline-now).total_seconds()<86400 else "ON_TIME"
  return self._add(355,"SLA_ASSESSED",{"status":status,"received":received_at.isoformat(),"deadline":deadline.isoformat(),"as_of":now.isoformat()})
 def relationship(self,other_case_id,other_merchant,other_currency,identity_match):
  if not other_case_id.startswith("synthetic:") or other_case_id==self.case_id:raise GovernanceRejected("distinct synthetic comparison case required")
  result="RELATED" if identity_match and other_merchant==self.merchant_ref and other_currency==self.currency else "DISTINCT"
  return self._add(356,"CASE_RELATIONSHIP_ASSESSED",{"other":other_case_id,"result":result,"automatic_merge":False})
 def liability(self,customer_pct,merchant_pct,provider_pct,matrix_digest):
  if not _d(matrix_digest) or any(type(x) is not int or x<0 for x in (customer_pct,merchant_pct,provider_pct)) or customer_pct+merchant_pct+provider_pct!=100:raise GovernanceRejected("integer liability allocation totaling 100 required")
  vals={"customer_minor":self.disputed_minor*customer_pct//100,"merchant_minor":self.disputed_minor*merchant_pct//100};vals["provider_minor"]=self.disputed_minor-vals["customer_minor"]-vals["merchant_minor"]
  return self._add(357,"LIABILITY_SIMULATION_DRAFTED",{**vals,"matrix_digest":matrix_digest})
 def financial_impact(self,fee_minor,reserve_minor,policy_digest):
  if not _d(policy_digest) or type(fee_minor) is not int or type(reserve_minor) is not int or min(fee_minor,reserve_minor)<0 or fee_minor+reserve_minor>self.disputed_minor:raise GovernanceRejected("bounded minor-unit impact required")
  return self._add(358,"DISPUTE_FINANCIAL_IMPACT_DRAFTED",{"fee_minor":fee_minor,"reserve_minor":reserve_minor,"currency":self.currency})
 def resolution_packet(self,issuer_ref,reviewer_ref):
  if not issuer_ref.startswith("synthetic:issuer:") or issuer_ref==reviewer_ref or not reviewer_ref.startswith("synthetic:reviewer:"):raise GovernanceRejected("separate synthetic issuer required")
  return self._add(359,"RESOLUTION_PACKET_DRAFTED",{"issuer":issuer_ref,"reviewer":reviewer_ref,"dependencies":[x.digest for x in self.artifacts]})
 def verify_packet(self,verifier_ref,issuer_ref,checks):
  if not verifier_ref.startswith("synthetic:verifier:") or verifier_ref==issuer_ref or checks!=("DIGESTS","ROLES","AMOUNTS","SAFETY"):raise GovernanceRejected("independent complete verification required")
  return self._add(360,"RESOLUTION_PACKET_VERIFIED",{"verifier":verifier_ref,"checks":checks,"approval_token_present":False})
 def ledger_preview(self,debit_minor,credit_minor):
  if type(debit_minor) is not int or debit_minor<=0 or debit_minor!=credit_minor or debit_minor>self.disputed_minor:raise GovernanceRejected("balanced bounded preview required")
  return self._add(361,"LEDGER_ADJUSTMENT_PREVIEWED",{"debit_minor":debit_minor,"credit_minor":credit_minor,"currency":self.currency,"posted":False})
 def envelope_lint(self,schema_digest,fields):
  if not _d(schema_digest) or tuple(sorted(fields))!=fields or any(x not in {"case_digest","currency","evidence_set_digest","recommended_minor"} for x in fields):raise GovernanceRejected("static allowlisted envelope required")
  return self._add(362,"SUBMISSION_ENVELOPE_LINTED",{"schema_digest":schema_digest,"fields":fields,"network_used":False,"submission_allowed":False})
 def reversal(self,reason_code):
  if reason_code not in {"NEW_EVIDENCE","CALCULATION_ERROR","POLICY_REVIEW"}:raise GovernanceRejected("allowlisted reversal reason required")
  return self._add(363,"REVERSAL_SIMULATION_DRAFTED",{"reason":reason_code,"mutation_applied":False})
 def reconcile_closure(self):
  if tuple(x.feature for x in self.artifacts)!=tuple(range(353,364)):raise GovernanceRejected("complete dispute lineage required")
  return self._add(364,"CLOSURE_RECONCILED",{"invariants_valid":True,"external_side_effects":False})
 def complete(self):
  if tuple(x.feature for x in self.artifacts)!=tuple(range(353,365)):raise GovernanceRejected("ordered portfolio required")
  return self._add(365,"SYNTHETIC_DISPUTE_PORTFOLIO_COMPLETED",{"features":[x.feature for x in self.artifacts],"root_digest":canonical_digest([x.digest for x in self.artifacts]),"promotion_allowed":False})
 def evidence(self):
  if not self.artifacts or self.artifacts[-1].feature!=365:raise GovernanceRejected("completed portfolio required")
  v={"schema":"nurion.pg.synthetic-dispute-portfolio.v1","case_id":self.case_id,"artifacts":[{"feature":x.feature,"state":x.state,"digest":x.digest} for x in self.artifacts],"maximum_state":"SYNTHETIC_DISPUTE_PORTFOLIO_COMPLETED","synthetic_only":True,"external_submission_allowed":False,"ledger_posting_allowed":False,"refund_allowed":False,"network_used":False,"credentials_accessed":False,"real_money_moved":False,"production_activation_allowed":False};return {**v,"report_digest":canonical_digest(v)}
