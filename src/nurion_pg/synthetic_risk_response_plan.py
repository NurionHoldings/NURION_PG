"""Synthetic dispute risk-response planning #381-#395; proposals only."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from .arkaon.governance import GovernanceRejected,canonical_digest

def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _s(v,p="synthetic:"):return isinstance(v,str) and v.startswith(p)
@dataclass(frozen=True)
class PlanStage:
 feature:int;state:str;payload:dict[str,object];previous_digest:str;digest:str;key:str
@dataclass
class RiskResponsePlan:
 risk_report_digest:str;policy_digest:str
 stages:list[PlanStage]=field(default_factory=list);_keys:dict[str,tuple[str,PlanStage]]=field(default_factory=dict)
 def __post_init__(self):
  if not _d(self.risk_report_digest) or not _d(self.policy_digest):raise GovernanceRejected("immutable report and policy required")
 def _add(self,feature,state,payload,key,version):
  if not _s(key,"synthetic:key:"):raise GovernanceRejected("synthetic idempotency key required")
  fp=canonical_digest({"feature":feature,"payload":payload})
  if key in self._keys:
   old,item=self._keys[key]
   if old!=fp:raise GovernanceRejected("idempotency conflict")
   return item
  if version!=len(self.stages) or feature!=381+len(self.stages):raise GovernanceRejected("ordered current version required")
  prev=self.stages[-1].digest if self.stages else self.risk_report_digest
  item=PlanStage(feature,state,payload,prev,canonical_digest({"feature":feature,"state":state,"payload":payload,"previous_digest":prev}),key);self.stages.append(item);self._keys[key]=(fp,item);return item
 def intake(self,report_state,forbidden_flags,key,version=0):
  if report_state!="SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED" or forbidden_flags or not _d(self.risk_report_digest):raise GovernanceRejected("safe completed risk report required")
  return self._add(381,"RISK_REPORT_INTAKE_ACCEPTED",{"report_digest":self.risk_report_digest},key,version)
 def classify_gaps(self,gaps,key,version):
  allowed={"DEADLINE","CONCENTRATION","COVERAGE","INDEPENDENCE","IMPACT"}
  if tuple(sorted(gaps))!=gaps or not gaps or len(gaps)!=len(set(gaps)) or not set(gaps)<=allowed:raise GovernanceRejected("unique allowlisted gaps required")
  return self._add(382,"CONTROL_GAPS_CLASSIFIED",{"gaps":gaps},key,version)
 def candidates(self,codes,key,version):
  allowed={"REQUEST_METADATA","QUEUE_REVIEW","LOWER_DRAFT_LIMIT","EXTEND_OBSERVATION","NO_ACTION"}
  if tuple(sorted(codes))!=codes or not codes or len(codes)!=len(set(codes)) or not set(codes)<=allowed:raise GovernanceRejected("unique allowlisted candidate codes required")
  return self._add(383,"RESPONSE_CANDIDATES_DRAFTED",{"codes":codes,"executable":False},key,version)
 def impact(self,merchant_ref,currency,affected_minor,ceiling_minor,key,version):
  if not _s(merchant_ref,"synthetic:merchant:") or len(currency)!=3 or any(type(x) is not int for x in (affected_minor,ceiling_minor)) or min(affected_minor,ceiling_minor)<0 or affected_minor>ceiling_minor:raise GovernanceRejected("bounded synthetic merchant impact required")
  return self._add(384,"MERCHANT_IMPACT_SIMULATED",{"merchant_ref":merchant_ref,"currency":currency,"affected_minor":affected_minor,"ceiling_minor":ceiling_minor,"applied":False},key,version)
 def fairness(self,segments,basis_points,key,version):
  if tuple(sorted(segments))!=segments or len(segments)!=len(set(segments)) or not segments or set(basis_points)!={*segments} or any(type(v) is not int or not 0<=v<=10000 for v in basis_points.values()):raise GovernanceRejected("complete unique segment fairness metrics required")
  gap=max(basis_points.values())-min(basis_points.values())
  return self._add(385,"FAIRNESS_CONSTRAINTS_CHECKED",{"segments":segments,"maximum_gap_bp":gap,"protected_data_used":False},key,version)
 def priority(self,ranked_codes,key,version):
  if tuple(sorted(ranked_codes,key=lambda x:x[0]))!=ranked_codes or len({r for r,_ in ranked_codes})!=len(ranked_codes) or len({c for _,c in ranked_codes})!=len(ranked_codes) or any(type(r) is not int or r<1 for r,_ in ranked_codes):raise GovernanceRejected("unique deterministic priority ranks required")
  return self._add(386,"INTERVENTION_PRIORITY_DRAFTED",{"ranked_codes":ranked_codes,"automatic_action":False},key,version)
 def cooling(self,start,end,key,version):
  if any(x.tzinfo is None for x in (start,end)) or end<=start:raise GovernanceRejected("aware positive cooling period required")
  return self._add(387,"COOLING_PERIOD_FIXED",{"start":start.isoformat(),"end":end.isoformat(),"wall_clock_used":False},key,version)
 def exceptions(self,codes,key,version):
  allowed={"INSUFFICIENT_DATA","CONFLICTING_EVIDENCE","FAIRNESS_REVIEW","CEILING_BREACH"}
  if tuple(sorted(codes))!=codes or len(codes)!=len(set(codes)) or not set(codes)<=allowed:raise GovernanceRejected("allowlisted exception codes required")
  return self._add(388,"EXCEPTION_DOCKET_DRAFTED",{"codes":codes,"free_text_absent":True},key,version)
 def roles(self,author,reviewer,operator,key,version):
  actors=(author,reviewer,operator)
  if len(set(actors))!=3 or any(not _s(x,"synthetic:actor:") for x in actors):raise GovernanceRejected("three independent synthetic actors required")
  return self._add(389,"ROLE_SEPARATION_VERIFIED",{"actors":actors,"approval_granted":False},key,version)
 def rollback(self,triggers,key,version):
  allowed={"METRIC_REGRESSION","FAIRNESS_BREACH","CEILING_BREACH","DATA_DRIFT"}
  if tuple(sorted(triggers))!=triggers or not triggers or len(triggers)!=len(set(triggers)) or not set(triggers)<=allowed:raise GovernanceRejected("unique rollback triggers required")
  return self._add(390,"ROLLBACK_PLAN_DRAFTED",{"triggers":triggers,"rollback_executable":False},key,version)
 def shadow_schedule(self,start,end,sample_bp,key,version):
  if any(x.tzinfo is None for x in (start,end)) or end<=start or type(sample_bp) is not int or not 1<=sample_bp<=10000:raise GovernanceRejected("bounded deterministic shadow schedule required")
  return self._add(391,"SHADOW_SCHEDULE_DRAFTED",{"start":start.isoformat(),"end":end.isoformat(),"sample_bp":sample_bp,"traffic_routed":False},key,version)
 def success_criteria(self,criteria,key,version):
  allowed={"DEADLINE_BP","COVERAGE_BP","FAIRNESS_GAP_BP","IMPACT_MINOR"}
  if tuple(sorted(criteria))!=criteria or not criteria or len({n for n,_,_ in criteria})!=len(criteria) or any(n not in allowed or op not in {"LTE","GTE"} or type(v) is not int or v<0 for n,op,v in criteria):raise GovernanceRejected("unique bounded success criteria required")
  return self._add(392,"SUCCESS_CRITERIA_FIXED",{"criteria":criteria,"auto_promote":False},key,version)
 def operator_packet(self,operator_ref,checks,key,version):
  required=("EVIDENCE","FAIRNESS","ROLLBACK","SAFETY")
  if not _s(operator_ref,"synthetic:operator:") or checks!=required:raise GovernanceRejected("complete non-authorizing operator packet required")
  return self._add(393,"OPERATOR_PACKET_DRAFTED",{"operator_ref":operator_ref,"checks":checks,"authorization_token":None},key,version)
 def seal(self,previous_snapshot,key,version):
  if previous_snapshot is not None and not _d(previous_snapshot):raise GovernanceRejected("valid previous snapshot required")
  if tuple(x.feature for x in self.stages)!=tuple(range(381,394)):raise GovernanceRejected("complete response lineage required")
  return self._add(394,"RISK_RESPONSE_SNAPSHOT_SEALED",{"stage_digests":tuple(x.digest for x in self.stages),"previous_snapshot":previous_snapshot},key,version)
 def complete(self,controls,key,version):
  required=("NON_EXECUTABLE","OPERATOR_SEPARATE","READ_ONLY","SYNTHETIC_ONLY")
  if controls!=required or tuple(x.feature for x in self.stages)!=tuple(range(381,395)):raise GovernanceRejected("complete fixed controls required")
  return self._add(395,"SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED",{"controls":controls,"promotion_allowed":False},key,version)
 def evidence(self):
  if not self.stages or self.stages[-1].feature!=395:raise GovernanceRejected("completed plan required")
  out={"schema":"nurion.pg.synthetic-risk-response-plan.v1","features":[x.feature for x in self.stages],"states":[x.state for x in self.stages],"risk_report_digest":self.risk_report_digest,"policy_digest":self.policy_digest,"maximum_state":"SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED","synthetic_only":True,"read_only":True,"execution_allowed":False,"merchant_block_allowed":False,"notification_allowed":False,"card_network_submission_allowed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"external_api_used":False,"deployment_allowed":False,"production_credentials_accessed":False,"automatic_policy_change_allowed":False,"operator_final_approval_granted":False}
  return {**out,"report_digest":canonical_digest(out)}
