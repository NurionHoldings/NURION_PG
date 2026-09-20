"""Synthetic response review/rebuttal/correction controls #9901-#10300."""
from dataclasses import dataclass
from threading import RLock
from .arkaon.governance import GovernanceRejected,canonical_digest
WORKSTREAM_NAMES=("RESPONSE_INTAKE_DOCKET_ANCHOR","LESSON_RULE_REGISTRY_BINDING","INTAKE_SEMANTIC_RECONSTRUCTION","NO_RESPONSE_MARKER_PRESERVATION","RESPONSE_DOCUMENT_PROJECTION","INDEPENDENT_REVIEW_ASSIGNMENT","REVIEW_RESULT_CONSTRAINED_CLASSIFICATION","REBUTTAL_OPPORTUNITY_ROUTING","CORRECTION_REQUEST_ROUTING","IMMEDIATE_PARENT_DOCUMENT_LINEAGE","SOURCE_ROLE_NAMESPACE_PROJECTION","NEW_ROLE_SEPARATION","APPEND_ONLY_REVIEW_EVENT","UNRESOLVED_HOLD_CHAIN","PARTIAL_BATCH_FAIL_CLOSED","NON_RESOLUTION_NON_EXECUTION_BOUNDARY")
WORKSTREAMS=tuple((9901+i*25,9925+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES));CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution");NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
FLOWS=("tenant_to_nurion","nurion_to_upstream","upstream_to_nurion","nurion_to_tenant");ANSWER_KINDS=("ASSUMPTION_RESPONSE","RESIDUAL_RISK_RESPONSE","ADDITIONAL_EVIDENCE","MEANING_CLARIFICATION","SAFE_BOUNDARY_ACKNOWLEDGEMENT");OUTCOMES=("CONSISTENT","CLAIM_CONFLICT","MANIFEST_CONFLICT","RECEIPT_CONFLICT","VERSION_CONFLICT");RESPONDER={"tenant_to_nurion":"TENANT_AGENCY","nurion_to_upstream":"NURION_PG","upstream_to_nurion":"UPSTREAM_PG","nurion_to_tenant":"NURION_PG"};ROUTE={"CONSISTENT":"NOT_APPLICABLE_PRESERVED","CLAIM_CONFLICT":"REBUTTAL_OPPORTUNITY_REQUIRED","MANIFEST_CONFLICT":"REBUTTAL_OPPORTUNITY_REQUIRED","RECEIPT_CONFLICT":"CORRECTION_REQUEST_REQUIRED","VERSION_CONFLICT":"CORRECTION_REQUEST_REQUIRED"}
APPLIED_LESSONS=("ARL-10301-001","ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001","ARL-7101-001","ARL-7501-001","ARL-7901-001","ARL-8301-001","ARL-8701-001","ARL-9101-001","ARL-9501-001","ARL-9901-001");APPLIED_RULES=tuple(f"ARP-{i:02}" for i in range(1,9));SOURCE_ROLE_KINDS=("readiness-reviewer","preflight-reviewer","reconsideration-reviewer")+("packet-compiler",)*4+("human-deliberation-chair","cross-party-validator","issue-matrix-compiler","issue-matrix-validator","clarification-drafter","clarification-reviewer","response-intake-compiler","response-intake-validator")
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _id(v):return v.rsplit(":",1)[-1].casefold()
def intake_digest(flow,kind,outcome,request,responder,response_doc,parent,present):return canonical_digest(("SOURCE_RESPONSE_INTAKE",flow,kind,outcome,request,responder,response_doc,parent,present))
@dataclass(frozen=True)
class Control:control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class SourceIntake:flow:str;answer_kind:str;outcome:str;request_digest:str;responder_party:str|None;response_document_digest:str|None;parent_intake_digest:str|None;response_present:bool;intake_digest:str
@dataclass(frozen=True)
class Anchor:anchor_id:str;source_docket_digest:str;intake_set_digest:str;lesson_registry_digest:str;remediation_manifest_digest:str;applied_lesson_ids:tuple[str,...];applied_rule_ids:tuple[str,...];source_intakes:tuple[SourceIntake,...];source_roles:tuple[str,...];source_lineage_digest:str;source_sequence:int;is_latest:bool;status:str;digest:str
@dataclass(frozen=True)
class Review:review_id:str;flow:str;answer_kind:str;source_intake_digest:str;route:str;reviewer:str|None;route_custodian:str|None;parent_review_digest:str|None;position:int;held:bool;resolved:bool;recommended:bool;accepted:bool;digest:str
@dataclass(frozen=True)
class Docket:docket_id:str;anchor_digest:str;review_set_digest:str;compiler:str;validator:str;source_lineage_digest:str;complete:bool;held:bool;resolved:bool;recommended:bool;accepted:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str
def _payload(p):
 p=dict(p)
 if "source_intakes" in p:p["source_intakes"]=tuple(tuple(x.__dict__.values()) for x in p["source_intakes"])
 return p
class SyntheticResponseReviewRebuttalCorrection:
 def __init__(self):self._controls={};self._anchor=None;self._reviews={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
 def _expected(self,c):i=c-9901;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
 def add_control(self,c,w,a,ref,fixture,result):
  p=dict(control_id=c,workstream=w,aspect=a,requirement_ref=ref,fixture_digest=fixture,expected_result=result);r=Control(**p,digest=canonical_digest(p))
  with self._lock:
   if not self._control_valid(r):raise GovernanceRejected("valid #9901-#10300 control required")
   old=self._controls.get(c)
   if old:
    if old==r:return old
    raise GovernanceRejected("control conflict")
   self._controls[c]=r;return r
 def anchor(self,anchor_id,source_docket,intake_set,registry,manifest,lessons,rules,intakes,roles,sequence,is_latest):
  intakes=tuple(intakes);roles=tuple(roles);lineage=canonical_digest(("RESPONSE_INTAKE_FULL_LINEAGE",source_docket,intake_set,tuple(x.intake_digest for x in intakes),roles));p=dict(anchor_id=anchor_id,source_docket_digest=source_docket,intake_set_digest=intake_set,lesson_registry_digest=registry,remediation_manifest_digest=manifest,applied_lesson_ids=tuple(lessons),applied_rule_ids=tuple(rules),source_intakes=intakes,source_roles=roles,source_lineage_digest=lineage,source_sequence=sequence,is_latest=is_latest,status="RESPONSE_INTAKE_DOCKET_ANCHORED_ON_HOLD_NOT_REVIEWED");r=Anchor(**p,digest=canonical_digest(_payload(p)))
  with self._lock:
   if not self._anchor_valid(r):raise GovernanceRejected("complete latest response intake required")
   if self._anchor:
    if self._anchor==r:return self._anchor
    raise GovernanceRejected("anchor conflict")
   self._anchor=r;self._event("RESPONSE_INTAKE_DOCKET_ANCHORED",r.digest);return r
 def add_review(self,review_id,flow,kind,reviewer=None,route_custodian=None):
  with self._lock:
   keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS);key=(flow,kind)
   if not self._anchor or key not in keys:raise GovernanceRejected("anchored intake required")
   pos=keys.index(key);src=self._anchor.source_intakes[pos];prev=None if pos==0 else self._reviews.get(keys[pos-1]);route=ROUTE[src.outcome]
   if pos and prev is None:raise GovernanceRejected("immediate prior review required")
   if route=="NOT_APPLICABLE_PRESERVED":
    if reviewer is not None or route_custodian is not None:raise GovernanceRejected("N/A cannot have actors")
   else:
    kind_role="rebuttal-custodian" if route=="REBUTTAL_OPPORTUNITY_REQUIRED" else "correction-request-compiler"
    if not _syn(reviewer,"response-independent-reviewer") or not _syn(route_custodian,kind_role):raise GovernanceRejected("independent review actors required")
    occupied=self._anchor.source_roles
    if len({_id(x) for x in occupied+(reviewer,route_custodian)})!=len(occupied)+2:raise GovernanceRejected("role collision")
   p=dict(review_id=review_id,flow=flow,answer_kind=kind,source_intake_digest=src.intake_digest,route=route,reviewer=reviewer,route_custodian=route_custodian,parent_review_digest=None if prev is None else prev.digest,position=pos+1,held=True,resolved=False,recommended=False,accepted=False);r=Review(**p,digest=canonical_digest(p))
   if not self._review_valid(r,key):raise GovernanceRejected("valid derived review required")
   old=self._reviews.get(key)
   if old:
    if old==r:return old
    raise GovernanceRejected("review conflict")
   self._reviews[key]=r;self._event("RESPONSE_REVIEW_RECORDED",r.digest)
   if route!="NOT_APPLICABLE_PRESERVED":self._hold(route,r.digest)
   return r
 def finalize(self,docket_id,compiler,validator):
  with self._lock:
   keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS)
   if self._docket or tuple(self._reviews)!=keys or not self._integrity():raise GovernanceRejected("complete intact reviews required")
   actors=self._anchor.source_roles+tuple(x for r in self._reviews.values() for x in (r.reviewer,r.route_custodian) if x)+(compiler,validator)
   if not _syn(compiler,"review-docket-compiler") or not _syn(validator,"review-docket-validator") or len({_id(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
   rset=canonical_digest(tuple(self._reviews[k].digest for k in keys));p=dict(docket_id=docket_id,anchor_digest=self._anchor.digest,review_set_digest=rset,compiler=compiler,validator=validator,source_lineage_digest=self._anchor.source_lineage_digest,complete=True,held=True,resolved=False,recommended=False,accepted=False,approved=False,activated=False,deployed=False,status="RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_READY_ON_HOLD_NOT_RESOLVED");r=Docket(**p,digest=canonical_digest(p));self._docket=r;self._event("REVIEW_REBUTTAL_CORRECTION_DOCKET_HELD",r.digest);return r
 def _control_valid(self,r):p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 9901<=r.control_id<=10300 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:response-review-requirement:{(r.control_id-9901)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
 def _registry_valid(self):return set(self._controls)==set(range(9901,10301)) and all(k==v.control_id and self._control_valid(v) for k,v in self._controls.items())
 def _intake_valid(self,r,pos,intakes):
  f,k=FLOWS[pos//5],ANSWER_KINDS[pos%5];o=OUTCOMES[pos%5];present=o!="CONSISTENT";parent=None if pos==0 else intakes[pos-1].intake_digest;responder=RESPONDER[f] if present else None
  return (r.flow,r.answer_kind,r.outcome)==(f,k,o) and _hex(r.request_digest) and r.response_present is present and r.responder_party==responder and ((_hex(r.response_document_digest) if present else r.response_document_digest is None)) and r.parent_intake_digest==parent and r.intake_digest==intake_digest(f,k,o,r.request_digest,responder,r.response_document_digest,parent,present)
 def _anchor_valid(self,r):
  p={k:v for k,v in r.__dict__.items() if k!="digest"};iset=canonical_digest(tuple(x.intake_digest for x in r.source_intakes));docket=canonical_digest(("CLARIFICATION_RESPONSE_INTAKE_DOCKET_SOURCE",iset,r.source_roles));lineage=canonical_digest(("RESPONSE_INTAKE_FULL_LINEAGE",r.source_docket_digest,r.intake_set_digest,tuple(x.intake_digest for x in r.source_intakes),r.source_roles))
  return self._registry_valid() and _syn(r.anchor_id,"response-review-anchor") and len(r.source_intakes)==20 and all(self._intake_valid(x,i,r.source_intakes) for i,x in enumerate(r.source_intakes)) and r.intake_set_digest==iset and r.source_docket_digest==docket and all(_hex(x) for x in (r.lesson_registry_digest,r.remediation_manifest_digest)) and r.applied_lesson_ids==APPLIED_LESSONS and r.applied_rule_ids==APPLIED_RULES and len(r.source_roles)==15 and all(_syn(x,k) for x,k in zip(r.source_roles,SOURCE_ROLE_KINDS)) and len({_id(x) for x in r.source_roles})==15 and r.source_lineage_digest==lineage and isinstance(r.source_sequence,int) and not isinstance(r.source_sequence,bool) and r.source_sequence>0 and r.is_latest is True and r.status=="RESPONSE_INTAKE_DOCKET_ANCHORED_ON_HOLD_NOT_REVIEWED" and r.digest==canonical_digest(_payload(p))
 def _review_valid(self,r,key):
  keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS);pos=keys.index(key) if key in keys else -1
  if not self._anchor or pos<0:return False
  src=self._anchor.source_intakes[pos];prev=None if pos==0 else self._reviews.get(keys[pos-1]);route=ROUTE[src.outcome];p={k:v for k,v in r.__dict__.items() if k!="digest"}
  actors_ok=(r.reviewer is None and r.route_custodian is None) if route=="NOT_APPLICABLE_PRESERVED" else (_syn(r.reviewer,"response-independent-reviewer") and _syn(r.route_custodian,"rebuttal-custodian" if route=="REBUTTAL_OPPORTUNITY_REQUIRED" else "correction-request-compiler") and len({_id(x) for x in self._anchor.source_roles+(r.reviewer,r.route_custodian)})==17)
  return _syn(r.review_id,"response-review") and key==(r.flow,r.answer_kind) and r.source_intake_digest==src.intake_digest and r.route==route and actors_ok and r.parent_review_digest==(None if prev is None else prev.digest) and r.position==pos+1 and r.held is True and not any((r.resolved,r.recommended,r.accepted)) and r.digest==canonical_digest(p)
 def _event(self,a,x):prev=self._events[-1]["digest"] if self._events else None;p=dict(sequence=len(self._events)+1,action=a,artifact_digest=x,previous_digest=prev);self._events.append({**p,"digest":canonical_digest(p)})
 def _hold(self,a,x):prev=self._holds[-1]["digest"] if self._holds else None;p=dict(sequence=len(self._holds)+1,reason=a,attachment_digest=x,previous_digest=prev);self._holds.append({**p,"digest":canonical_digest(p)})
 @staticmethod
 def _chain(rows,event):
  prev=None
  for i,r in enumerate(rows,1):
   keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest");p={k:r.get(k) for k in keys}
   if r!={**p,"digest":canonical_digest(p)} or r["sequence"]!=i or r["previous_digest"]!=prev:return False
   prev=r["digest"]
  return True
 def _integrity(self):
  if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._review_valid(v,k) for k,v in self._reviews.items()):return False
  events=[]
  if self._anchor:events.append(("RESPONSE_INTAKE_DOCKET_ANCHORED",self._anchor.digest))
  events.extend(("RESPONSE_REVIEW_RECORDED",x.digest) for x in self._reviews.values())
  if self._docket:events.append(("REVIEW_REBUTTAL_CORRECTION_DOCKET_HELD",self._docket.digest))
  holds=[(x.route,x.digest) for x in self._reviews.values() if x.route!="NOT_APPLICABLE_PRESERVED"]
  if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
  if self._docket:
   r=self._docket;keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS);p={k:v for k,v in r.__dict__.items() if k!="digest"}
   if not _syn(r.docket_id,"response-review-docket") or r.anchor_digest!=self._anchor.digest or r.review_set_digest!=canonical_digest(tuple(self._reviews[k].digest for k in keys)) or r.source_lineage_digest!=self._anchor.source_lineage_digest or r.complete is not True or r.held is not True or any((r.resolved,r.recommended,r.accepted,r.approved,r.activated,r.deployed)) or r.status!="RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_READY_ON_HOLD_NOT_RESOLVED" or r.digest!=canonical_digest(p):return False
  return True
 def evidence(self):
  ok=self._integrity();return {"range":[9901,10300],"control_count":400,"registered_control_count":len(self._controls),"review_count":len(self._reviews),"rebuttal_route_count":sum(x.route=="REBUTTAL_OPPORTUNITY_REQUIRED" for x in self._reviews.values()),"correction_route_count":sum(x.route=="CORRECTION_REQUEST_REQUIRED" for x in self._reviews.values()),"hold_count":len(self._holds),"integrity_valid":ok,"complete_review_docket_evidence":len(self._reviews)==20 and self._docket is not None and ok,"maximum_state":"RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_READY_ON_HOLD_NOT_RESOLVED" if self._docket else "REVIEW_DOCKET_INCOMPLETE","external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"resolved":False,"recommended":False,"accepted":False,"approved":False,"activated":False}
