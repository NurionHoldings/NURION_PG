"""Synthetic dispute observability controls #366-#380; read-only by construction."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from .arkaon.governance import GovernanceRejected,canonical_digest

def _digest(value:str)->bool:
 return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)
def _synthetic(value:str,prefix="synthetic:")->bool:return isinstance(value,str) and value.startswith(prefix)
@dataclass(frozen=True)
class Observation:
 feature:int;state:str;payload:dict[str,object];previous_digest:str;digest:str;key:str
@dataclass
class DisputeObservatory:
 source_manifest_digest:str;policy_digest:str
 observations:list[Observation]=field(default_factory=list)
 _keys:dict[str,tuple[str,Observation]]=field(default_factory=dict)
 def __post_init__(self):
  if not _digest(self.source_manifest_digest) or not _digest(self.policy_digest):raise GovernanceRejected("immutable source and policy digests required")
 def _step(self,feature,state,payload,key,expected_version):
  if not _synthetic(key,"synthetic:key:"):raise GovernanceRejected("synthetic idempotency key required")
  fingerprint=canonical_digest({"feature":feature,"payload":payload})
  if key in self._keys:
   prior_fingerprint,prior=self._keys[key]
   if prior_fingerprint!=fingerprint:raise GovernanceRejected("idempotency conflict")
   return prior
  if expected_version!=len(self.observations) or feature!=366+len(self.observations):raise GovernanceRejected("ordered current version required")
  previous=self.observations[-1].digest if self.observations else self.source_manifest_digest
  digest=canonical_digest({"feature":feature,"state":state,"payload":payload,"previous_digest":previous})
  item=Observation(feature,state,payload,previous,digest,key);self.observations.append(item);self._keys[key]=(fingerprint,item);return item
 def projection(self,rows,key,expected_version=0):
  normalized=tuple(sorted(rows,key=lambda x:x["case_id"]))
  ids=[x.get("case_id") for x in normalized]
  if not normalized or len(ids)!=len(set(ids)) or any(not _synthetic(x) for x in ids):raise GovernanceRejected("unique synthetic projections required")
  for row in normalized:
   if set(row)!={"case_id","currency","state","lineage_digest","reason","merchant_ref","received_at","exposure_minor"} or len(row["currency"])!=3 or row["state"]!="CLOSURE_RECONCILED" or not _digest(row["lineage_digest"]) or row["reason"] not in {"FRAUD","SERVICE","PROCESSING","OTHER"} or not _synthetic(row["merchant_ref"],"synthetic:merchant:") or type(row["exposure_minor"]) is not int or row["exposure_minor"]<0:raise GovernanceRejected("projection schema rejected")
  return self._step(366,"PROJECTION_ACCEPTED",{"rows":normalized},key,expected_version)
 def cohorts(self,dimensions,key,expected_version):
  if tuple(sorted(dimensions))!=dimensions or not dimensions or any(x not in {"age","currency","merchant","reason"} for x in dimensions):raise GovernanceRejected("allowlisted ordered dimensions required")
  return self._step(367,"COHORTS_BUILT",{"dimensions":dimensions,"exclusive_assignment":True},key,expected_version)
 def exposure(self,by_currency,key,expected_version):
  items=tuple(sorted(by_currency))
  if not items or any(len(c)!=3 or type(v) is not int or v<0 for c,v in items) or len({c for c,_ in items})!=len(items):raise GovernanceRejected("separate nonnegative currency exposure required")
  return self._step(368,"EXPOSURE_AGGREGATED",{"by_currency":items,"cross_currency_total":None},key,expected_version)
 def aging(self,as_of,ages_days,key,expected_version):
  if as_of.tzinfo is None or any(type(x) is not int or x<0 for x in ages_days):raise GovernanceRejected("aware deterministic aging required")
  buckets={"0_7":0,"8_14":0,"15_30":0,"31_plus":0}
  for age in ages_days:buckets["0_7" if age<=7 else "8_14" if age<=14 else "15_30" if age<=30 else "31_plus"]+=1
  return self._step(369,"AGING_OBSERVED",{"as_of":as_of.isoformat(),"buckets":buckets},key,expected_version)
 def deadline_risk(self,horizon_hours,score,key,expected_version):
  if type(horizon_hours) is not int or horizon_hours<=0 or type(score) is not int or not 0<=score<=100:raise GovernanceRejected("bounded deterministic deadline score required")
  return self._step(370,"DEADLINE_RISK_SCORED",{"horizon_hours":horizon_hours,"score":score,"automatic_action":False},key,expected_version)
 def reason_concentration(self,basis_points,key,expected_version):
  items=tuple(sorted(basis_points))
  if not items or any(r not in {"FRAUD","SERVICE","PROCESSING","OTHER"} or type(v) is not int or v<0 for r,v in items) or len({r for r,_ in items})!=len(items) or sum(v for _,v in items)!=10000:raise GovernanceRejected("reason basis points must total 10000")
  return self._step(371,"REASON_CONCENTRATION_ASSESSED",{"basis_points":items},key,expected_version)
 def merchant_concentration(self,rows,key,expected_version):
  items=tuple(sorted(rows))
  if not items or any(not _synthetic(m,"synthetic:merchant:") or len(c)!=3 or type(v) is not int or v<0 for m,c,v in items) or len({(m,c) for m,c,_ in items})!=len(items):raise GovernanceRejected("synthetic merchant concentration required")
  return self._step(372,"MERCHANT_CONCENTRATION_ASSESSED",{"rows":items,"cross_currency_total":None},key,expected_version)
 def duplicate_clusters(self,edges,key,expected_version):
  items=tuple(sorted(tuple(sorted(e)) for e in edges))
  if len(items)!=len(set(items)) or any(a==b or not _synthetic(a,"synthetic:case:") or not _synthetic(b,"synthetic:case:") for a,b in items):raise GovernanceRejected("valid unique synthetic edges required")
  return self._step(373,"DUPLICATE_CLUSTER_RISK_ASSESSED",{"edges":items,"automatic_merge":False},key,expected_version)
 def evidence_coverage(self,present,required,key,expected_version):
  allowed={"AUTH","DELIVERY","COMMUNICATION","REFUND"}
  if not required or not set(present)<=allowed or not set(required)<=allowed or len(present)!=len(set(present)) or len(required)!=len(set(required)):raise GovernanceRejected("allowlisted metadata-only evidence required")
  bp=10000*len(set(present)&set(required))//len(required)
  return self._step(374,"EVIDENCE_COVERAGE_ASSESSED",{"coverage_bp":bp,"content_accessed":False},key,expected_version)
 def independence(self,intake,reviewer,verifier,key,expected_version):
  actors=(intake,reviewer,verifier)
  if len(set(actors))!=3 or any(not _synthetic(x,"synthetic:actor:") for x in actors):raise GovernanceRejected("three independent synthetic actors required")
  return self._step(375,"REVIEW_INDEPENDENCE_AUDITED",{"actors":actors,"final_approval":False},key,expected_version)
 def impact_ceiling(self,preview_minor,ceiling_minor,posted,key,expected_version):
  if type(preview_minor) is not int or type(ceiling_minor) is not int or min(preview_minor,ceiling_minor)<0 or preview_minor>ceiling_minor or posted:raise GovernanceRejected("bounded unposted impact required")
  return self._step(376,"IMPACT_CEILING_CHECKED",{"preview_minor":preview_minor,"ceiling_minor":ceiling_minor,"posted":False},key,expected_version)
 def anomalies(self,rules,triggered,key,expected_version):
  allowed={"DEADLINE_HIGH","CONCENTRATION_HIGH","COVERAGE_LOW","IMPACT_NEAR_CEILING"}
  if tuple(sorted(rules))!=rules or not set(triggered)<=set(rules) or not set(rules)<=allowed:raise GovernanceRejected("allowlisted deterministic rules required")
  return self._step(377,"ANOMALIES_FLAGGED",{"rules":rules,"triggered":tuple(sorted(triggered)),"automatic_policy_change":False},key,expected_version)
 def alert_dockets(self,alert_keys,key,expected_version):
  if tuple(sorted(alert_keys))!=alert_keys or len(alert_keys)!=len(set(alert_keys)) or any(not _synthetic(x,"synthetic:alert:") for x in alert_keys):raise GovernanceRejected("unique synthetic alerts required")
  return self._step(378,"ALERT_DOCKETS_DRAFTED",{"alerts":alert_keys,"recipient":None,"notification_sent":False},key,expected_version)
 def snapshot(self,previous_snapshot_digest,key,expected_version):
  if previous_snapshot_digest is not None and not _digest(previous_snapshot_digest):raise GovernanceRejected("valid previous snapshot digest required")
  if tuple(x.feature for x in self.observations)!=tuple(range(366,379)):raise GovernanceRejected("complete observation lineage required")
  return self._step(379,"OBSERVABILITY_SNAPSHOT_SEALED",{"stage_digests":tuple(x.digest for x in self.observations),"previous_snapshot_digest":previous_snapshot_digest},key,expected_version)
 def report(self,controls,key,expected_version):
  required=("ALERTS_READ_ONLY","NO_AUTO_ACTION","NO_CURRENCY_COLLAPSE","ROLE_SEPARATION")
  if controls!=required or tuple(x.feature for x in self.observations)!=tuple(range(366,380)):raise GovernanceRejected("complete control matrix required")
  return self._step(380,"SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED",{"controls":controls,"operator_final_approval_granted":False},key,expected_version)
 def evidence(self):
  if not self.observations or self.observations[-1].feature!=380:raise GovernanceRejected("completed report required")
  result={"schema":"nurion.pg.synthetic-dispute-observatory.v1","features":[x.feature for x in self.observations],"states":[x.state for x in self.observations],"source_manifest_digest":self.source_manifest_digest,"policy_digest":self.policy_digest,"maximum_state":"SYNTHETIC_PORTFOLIO_RISK_REPORT_COMPLETED","synthetic_only":True,"read_only":True,"raw_evidence_accessed":False,"card_network_submission_allowed":False,"payment_execution_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"external_api_used":False,"deployment_allowed":False,"production_credentials_accessed":False,"automatic_policy_change_allowed":False,"operator_final_approval_granted":False}
  return {**result,"report_digest":canonical_digest(result)}
