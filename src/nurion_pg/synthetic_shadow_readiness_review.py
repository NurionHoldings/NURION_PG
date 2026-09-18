"""Synthetic shadow readiness review #411-#425; never authorizes rollout."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from .arkaon.governance import GovernanceRejected,canonical_digest
def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _s(v,p="synthetic:"):return isinstance(v,str) and v.startswith(p)
@dataclass(frozen=True)
class ReviewStage:feature:int;state:str;payload:dict[str,object];previous_digest:str;digest:str;key:str
@dataclass
class ShadowReadinessReview:
 validation_digest:str;policy_digest:str
 stages:list[ReviewStage]=field(default_factory=list);_keys:dict[str,tuple[str,ReviewStage]]=field(default_factory=dict)
 def __post_init__(self):
  if not _d(self.validation_digest) or not _d(self.policy_digest):raise GovernanceRejected("immutable validation and policy required")
 def _add(self,f,state,payload,key,v):
  if not _s(key,"synthetic:key:"):raise GovernanceRejected("synthetic idempotency key required")
  fp=canonical_digest({"feature":f,"payload":payload})
  if key in self._keys:
   old,item=self._keys[key]
   if old!=fp:raise GovernanceRejected("idempotency conflict")
   return item
  if v!=len(self.stages) or f!=411+len(self.stages):raise GovernanceRejected("ordered current version required")
  prev=self.stages[-1].digest if self.stages else self.validation_digest;item=ReviewStage(f,state,payload,prev,canonical_digest({"feature":f,"state":state,"payload":payload,"previous_digest":prev}),key);self.stages.append(item);self._keys[key]=(fp,item);return item
 def admit(self,state,recommendation,criteria_passed,rollback_observed,key,v=0):
  if state!="SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED" or recommendation not in {"HOLD","REVISE","ELIGIBLE_DRAFT"} or type(criteria_passed) is not bool or type(rollback_observed) is not bool or recommendation=="ELIGIBLE_DRAFT" and (not criteria_passed or rollback_observed):raise GovernanceRejected("consistent completed shadow validation required")
  return self._add(411,"SHADOW_VALIDATION_ADMITTED",{"recommendation":recommendation,"criteria_passed":criteria_passed,"rollback_observed":rollback_observed},key,v)
 def blockers(self,codes,key,v):
  allowed={"CRITERIA_FAILED","ROLLBACK_TRIGGERED","FAIRNESS_CONCERN","CAPACITY_CONCERN","NONE"}
  if tuple(sorted(codes))!=codes or not codes or len(codes)!=len(set(codes)) or not set(codes)<=allowed or ("NONE" in codes and len(codes)!=1):raise GovernanceRejected("unique coherent blocker codes required")
  rec=self.stages[0].payload["recommendation"]
  if rec=="ELIGIBLE_DRAFT" and codes!=("NONE",):raise GovernanceRejected("eligible draft cannot carry blockers")
  return self._add(412,"BLOCKER_DOCKET_FIXED",{"codes":codes},key,v)
 def evidence_matrix(self,checks,key,v):
  required=("CRITERIA","FAIRNESS","FINANCIAL","ROLLBACK","SENSITIVITY")
  if checks!=required:raise GovernanceRejected("complete fixed evidence matrix required")
  return self._add(413,"EVIDENCE_MATRIX_VERIFIED",{"checks":checks},key,v)
 def consistency(self,reported_code,key,v):
  expected=self.stages[0].payload["recommendation"]
  if reported_code!=expected:raise GovernanceRejected("recommendation lineage mismatch")
  return self._add(414,"OUTCOME_CONSISTENCY_VERIFIED",{"code":reported_code},key,v)
 def fairness(self,gap_bp,ceiling_bp,key,v):
  if any(type(x) is not int for x in (gap_bp,ceiling_bp)) or not 0<=gap_bp<=10000 or not 0<=ceiling_bp<=10000 or gap_bp>ceiling_bp:raise GovernanceRejected("bounded passing fairness review required")
  return self._add(415,"FAIRNESS_READINESS_CHECKED",{"gap_bp":gap_bp,"ceiling_bp":ceiling_bp,"protected_data_used":False},key,v)
 def financial(self,impact_minor,ceiling_minor,key,v):
  if any(type(x) is not int for x in (impact_minor,ceiling_minor)) or min(impact_minor,ceiling_minor)<0 or impact_minor>ceiling_minor:raise GovernanceRejected("bounded financial readiness required")
  return self._add(416,"FINANCIAL_READINESS_CHECKED",{"impact_minor":impact_minor,"ceiling_minor":ceiling_minor,"posted":False},key,v)
 def rollback(self,triggers,rehearsed,key,v):
  if tuple(sorted(triggers))!=triggers or not triggers or len(triggers)!=len(set(triggers)) or set(rehearsed)!=set(triggers):raise GovernanceRejected("all unique rollback triggers must be rehearsed")
  return self._add(417,"ROLLBACK_READINESS_VERIFIED",{"triggers":triggers,"rehearsed":tuple(sorted(rehearsed)),"execution_enabled":False},key,v)
 def capacity(self,arrival,service,backlog_ceiling,key,v):
  if any(type(x) is not int for x in (arrival,service,backlog_ceiling)) or min(arrival,service,backlog_ceiling)<0 or arrival>service+backlog_ceiling:raise GovernanceRejected("bounded synthetic capacity required")
  return self._add(418,"CAPACITY_READINESS_SIMULATED",{"arrival":arrival,"service":service,"backlog_ceiling":backlog_ceiling,"live_telemetry_used":False},key,v)
 def window(self,start,end,key,v):
  if any(x.tzinfo is None for x in (start,end)) or end<=start:raise GovernanceRejected("aware fixed review window required")
  return self._add(419,"REVIEW_WINDOW_FIXED",{"start":start.isoformat(),"end":end.isoformat(),"activation_scheduled":False},key,v)
 def roles(self,author,reviewer,operator,key,v):
  if not _s(author,"synthetic:actor:") or not _s(reviewer,"synthetic:actor:") or not _s(operator,"synthetic:operator:") or len({author,reviewer,operator})!=3:raise GovernanceRejected("independent synthetic roles required")
  return self._add(420,"READINESS_ROLES_SEPARATED",{"author":author,"reviewer":reviewer,"operator":operator},key,v)
 def alternatives(self,codes,key,v):
  required=("HOLD","REQUEST_REVISION","SUBMIT_FOR_OPERATOR_REVIEW")
  if codes!=required:raise GovernanceRejected("complete non-authorizing alternatives required")
  return self._add(421,"DECISION_ALTERNATIVES_FIXED",{"codes":codes,"automatic_selection":False},key,v)
 def packet(self,operator,selected,key,v):
  assigned=self.stages[9].payload["operator"] if len(self.stages)>9 else None
  if operator!=assigned or selected not in self.stages[10].payload["codes"]:raise GovernanceRejected("assigned operator and allowlisted selection required")
  if selected=="SUBMIT_FOR_OPERATOR_REVIEW" and self.stages[1].payload["codes"]!=("NONE",):raise GovernanceRejected("blockers prevent review submission")
  return self._add(422,"OPERATOR_READINESS_PACKET_DRAFTED",{"operator":operator,"selected":selected,"authorization_token":None},key,v)
 def verify(self,verifier,checks,key,v):
  assigned={self.stages[9].payload[x] for x in ("author","reviewer","operator")}
  if not _s(verifier,"synthetic:verifier:") or verifier in assigned or checks!=("DIGESTS","ROLES","BLOCKERS","SAFETY"):raise GovernanceRejected("independent complete verification required")
  return self._add(423,"READINESS_PACKET_VERIFIED",{"verifier":verifier,"checks":checks,"approval_granted":False},key,v)
 def seal(self,previous,key,v):
  if previous is not None and not _d(previous) or tuple(x.feature for x in self.stages)!=tuple(range(411,424)):raise GovernanceRejected("complete readiness lineage required")
  return self._add(424,"READINESS_REVIEW_SNAPSHOT_SEALED",{"digests":tuple(x.digest for x in self.stages),"previous":previous},key,v)
 def complete(self,controls,key,v):
  required=("NO_ACTIVATION","NO_AUTHORIZATION","READ_ONLY","SYNTHETIC_ONLY")
  if controls!=required or tuple(x.feature for x in self.stages)!=tuple(range(411,425)):raise GovernanceRejected("fixed completion controls required")
  return self._add(425,"SYNTHETIC_SHADOW_READINESS_REVIEW_COMPLETED",{"controls":controls},key,v)
 def evidence(self):
  if not self.stages or self.stages[-1].feature!=425:raise GovernanceRejected("completed readiness review required")
  out={"schema":"nurion.pg.synthetic-shadow-readiness-review.v1","features":[x.feature for x in self.stages],"states":[x.state for x in self.stages],"validation_digest":self.validation_digest,"policy_digest":self.policy_digest,"maximum_state":"SYNTHETIC_SHADOW_READINESS_REVIEW_COMPLETED","synthetic_only":True,"read_only":True,"authorization_granted":False,"activation_allowed":False,"promotion_allowed":False,"live_traffic_used":False,"merchant_blocking_allowed":False,"notification_allowed":False,"card_network_submission_allowed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"external_api_used":False,"deployment_allowed":False,"production_credentials_accessed":False,"automatic_policy_change_allowed":False}
  return {**out,"report_digest":canonical_digest(out)}
