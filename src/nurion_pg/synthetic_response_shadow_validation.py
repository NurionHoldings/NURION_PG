"""Synthetic risk-response shadow validation #396-#410; no execution."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from .arkaon.governance import GovernanceRejected,canonical_digest

def _d(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _s(v,p="synthetic:"):return isinstance(v,str) and v.startswith(p)
@dataclass(frozen=True)
class ShadowStage:
 feature:int;state:str;payload:dict[str,object];previous_digest:str;digest:str;key:str
@dataclass
class ResponseShadowValidation:
 plan_digest:str;policy_digest:str
 stages:list[ShadowStage]=field(default_factory=list);_keys:dict[str,tuple[str,ShadowStage]]=field(default_factory=dict)
 def __post_init__(self):
  if not _d(self.plan_digest) or not _d(self.policy_digest):raise GovernanceRejected("immutable plan and policy digests required")
 def _add(self,feature,state,payload,key,version):
  if not _s(key,"synthetic:key:"):raise GovernanceRejected("synthetic idempotency key required")
  fp=canonical_digest({"feature":feature,"payload":payload})
  if key in self._keys:
   old,item=self._keys[key]
   if old!=fp:raise GovernanceRejected("idempotency conflict")
   return item
  if version!=len(self.stages) or feature!=396+len(self.stages):raise GovernanceRejected("ordered current version required")
  prev=self.stages[-1].digest if self.stages else self.plan_digest
  item=ShadowStage(feature,state,payload,prev,canonical_digest({"feature":feature,"state":state,"payload":payload,"previous_digest":prev}),key);self.stages.append(item);self._keys[key]=(fp,item);return item
 def admit(self,state,forbidden,key,version=0):
  if state!="SYNTHETIC_RISK_RESPONSE_PLAN_COMPLETED" or forbidden:raise GovernanceRejected("safe completed plan required")
  return self._add(396,"SHADOW_PLAN_ADMITTED",{"plan_digest":self.plan_digest},key,version)
 def fixture_cohort(self,cases,currency,key,version):
  items=tuple(sorted(cases))
  if not items or len(items)!=len(set(items)) or any(not _s(x,"synthetic:case:") for x in items) or len(currency)!=3:raise GovernanceRejected("unique synthetic single-currency cohort required")
  return self._add(397,"SHADOW_FIXTURE_COHORT_FIXED",{"cases":items,"currency":currency},key,version)
 def baseline(self,metrics,as_of,key,version):
  allowed={"COVERAGE_BP","DEADLINE_BP","FAIRNESS_GAP_BP","IMPACT_MINOR"}
  if as_of.tzinfo is None or set(metrics)!=allowed or any(type(v) is not int or v<0 or (n.endswith("_BP") and v>10000) for n,v in metrics.items()):raise GovernanceRejected("complete bounded deterministic baseline required")
  return self._add(398,"BASELINE_SNAPSHOT_SEALED",{"metrics":tuple(sorted(metrics.items())),"as_of":as_of.isoformat()},key,version)
 def project(self,option_code,metrics,key,version):
  allowed_options={"REQUEST_METADATA","QUEUE_REVIEW","LOWER_DRAFT_LIMIT","EXTEND_OBSERVATION","NO_ACTION"};allowed_metrics={"COVERAGE_BP","DEADLINE_BP","FAIRNESS_GAP_BP","IMPACT_MINOR"}
  if option_code not in allowed_options or set(metrics)!=allowed_metrics or any(type(v) is not int or v<0 or (n.endswith("_BP") and v>10000) for n,v in metrics.items()):raise GovernanceRejected("allowlisted bounded projection required")
  return self._add(399,"SHADOW_OUTCOME_PROJECTED",{"option":option_code,"metrics":tuple(sorted(metrics.items())),"executed":False},key,version)
 def deltas(self,values,key,version):
  allowed={"COVERAGE_BP","DEADLINE_BP","FAIRNESS_GAP_BP","IMPACT_MINOR"}
  baseline=dict(self.stages[2].payload["metrics"]) if len(self.stages)>3 else {};projection=dict(self.stages[3].payload["metrics"]) if len(self.stages)>3 else {}
  if set(values)!=allowed or any(type(v) is not int for v in values.values()) or any(values[n]!=projection[n]-baseline[n] for n in allowed):raise GovernanceRejected("baseline-bound projection deltas required")
  return self._add(400,"METRIC_DELTAS_EVALUATED",{"deltas":tuple(sorted(values.items()))},key,version)
 def criteria(self,results,key,version):
  allowed={"COVERAGE_BP","DEADLINE_BP","FAIRNESS_GAP_BP","IMPACT_MINOR"}
  projection=dict(self.stages[3].payload["metrics"]) if len(self.stages)>4 else {};criteria=self.stages[0].payload["criteria"] if self.stages else ()
  expected={n:(projection[n]<=v if op=="LTE" else projection[n]>=v) for n,op,v in criteria}
  if set(results)!=allowed or any(type(v) is not bool for v in results.values()) or results!=expected:raise GovernanceRejected("projection-bound fixed criteria comparison required")
  return self._add(401,"SUCCESS_CRITERIA_COMPARED",{"results":tuple(sorted(results.items())),"all_passed":all(results.values()),"auto_promote":False},key,version)
 def fairness_drift(self,segment_bp,key,version):
  items=tuple(sorted(segment_bp))
  if not items or len({s for s,_ in items})!=len(items) or any(not _s(s,"synthetic:segment:") or type(v) is not int or not 0<=v<=10000 for s,v in items):raise GovernanceRejected("unique bounded synthetic segments required")
  return self._add(402,"FAIRNESS_DRIFT_ASSESSED",{"segments":items,"protected_data_used":False},key,version)
 def financial_guard(self,projected_minor,ceiling_minor,key,version):
  if any(type(x) is not int for x in (projected_minor,ceiling_minor)) or min(projected_minor,ceiling_minor)<0 or projected_minor>ceiling_minor:raise GovernanceRejected("bounded minor-unit financial guard required")
  return self._add(403,"FINANCIAL_GUARD_CHECKED",{"projected_minor":projected_minor,"ceiling_minor":ceiling_minor,"applied":False},key,version)
 def rollback_check(self,triggers,observed,key,version):
  allowed={"METRIC_REGRESSION","FAIRNESS_BREACH","CEILING_BREACH","DATA_DRIFT"}
  planned=self.stages[0].payload["rollback_triggers"] if self.stages else ()
  if triggers!=planned or tuple(sorted(triggers))!=triggers or not triggers or len(triggers)!=len(set(triggers)) or not set(triggers)<=allowed or not set(observed)<=set(triggers):raise GovernanceRejected("plan-bound rollback trigger observation required")
  return self._add(404,"ROLLBACK_TRIGGERS_EVALUATED",{"triggers":triggers,"observed":tuple(sorted(observed)),"rollback_executed":False},key,version)
 def false_positive(self,numerator,denominator,key,version):
  if any(type(x) is not int for x in (numerator,denominator)) or denominator<=0 or not 0<=numerator<=denominator:raise GovernanceRejected("valid false-positive fraction required")
  return self._add(405,"FALSE_POSITIVE_REVIEWED",{"numerator":numerator,"denominator":denominator,"rate_bp":numerator*10000//denominator},key,version)
 def sensitivity(self,scenarios,key,version):
  items=tuple(sorted(scenarios))
  if {n for n,_ in items}!={"LOW","BASE","HIGH"} or len(items)!=3 or any(type(v) is not int for _,v in items):raise GovernanceRejected("unique allowlisted sensitivity scenarios required")
  return self._add(406,"SENSITIVITY_ANALYSIS_COMPLETED",{"scenarios":items,"randomness_used":False},key,version)
 def attest(self,planner,reviewer,checks,key,version):
  if not _s(planner,"synthetic:actor:") or not _s(reviewer,"synthetic:actor:") or planner==reviewer or checks!=("CRITERIA","FAIRNESS","FINANCIAL","ROLLBACK"):raise GovernanceRejected("independent complete attestation required")
  return self._add(407,"INDEPENDENT_REVIEW_ATTESTED",{"planner":planner,"reviewer":reviewer,"checks":checks,"approval_granted":False},key,version)
 def recommendation(self,code,key,version):
  allowed={"HOLD","REVISE","ELIGIBLE_DRAFT"}
  if code not in allowed:raise GovernanceRejected("allowlisted non-authorizing recommendation required")
  criteria=dict(self.stages[5].payload["results"]) if len(self.stages)>5 else {}
  observed=self.stages[8].payload["observed"] if len(self.stages)>8 else ()
  if code=="ELIGIBLE_DRAFT" and (not criteria or not all(criteria.values()) or observed):raise GovernanceRejected("eligibility requires passed criteria and no rollback triggers")
  return self._add(408,"SHADOW_RECOMMENDATION_DRAFTED",{"code":code,"promotion_allowed":False},key,version)
 def seal(self,previous_snapshot,key,version):
  if previous_snapshot is not None and not _d(previous_snapshot):raise GovernanceRejected("valid previous snapshot required")
  if tuple(x.feature for x in self.stages)!=tuple(range(396,409)):raise GovernanceRejected("complete shadow lineage required")
  return self._add(409,"SHADOW_VALIDATION_SNAPSHOT_SEALED",{"stage_digests":tuple(x.digest for x in self.stages),"previous_snapshot":previous_snapshot},key,version)
 def complete(self,controls,key,version):
  required=("NO_EXECUTION","NO_PROMOTION","READ_ONLY","SYNTHETIC_ONLY")
  if controls!=required or tuple(x.feature for x in self.stages)!=tuple(range(396,410)):raise GovernanceRejected("complete fixed shadow controls required")
  return self._add(410,"SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED",{"controls":controls},key,version)
 def evidence(self):
  if not self.stages or self.stages[-1].feature!=410:raise GovernanceRejected("completed shadow validation required")
  out={"schema":"nurion.pg.synthetic-response-shadow-validation.v1","features":[x.feature for x in self.stages],"states":[x.state for x in self.stages],"plan_digest":self.plan_digest,"policy_digest":self.policy_digest,"maximum_state":"SYNTHETIC_RESPONSE_SHADOW_VALIDATION_COMPLETED","synthetic_only":True,"read_only":True,"real_traffic_used":False,"execution_allowed":False,"promotion_allowed":False,"merchant_blocking_allowed":False,"notification_allowed":False,"card_network_submission_allowed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"external_api_used":False,"deployment_allowed":False,"production_credentials_accessed":False,"automatic_policy_change_allowed":False,"operator_final_approval_granted":False}
  return {**out,"report_digest":canonical_digest(out)}
