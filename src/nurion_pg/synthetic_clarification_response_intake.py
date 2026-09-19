"""Synthetic/in-memory clarification response intake controls #9501-#9900."""
from dataclasses import dataclass
from threading import RLock
from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES=("CLARIFICATION_DOCKET_ANCHOR","LESSON_RULE_BINDING","REQUEST_SEMANTIC_RECONSTRUCTION","RESPONSE_REQUIREMENT_DERIVATION","TENANT_RESPONSE_INTAKE","NURION_RESPONSE_INTAKE","UPSTREAM_RESPONSE_INTAKE","NO_RESPONSE_MARKER","RESPONSE_CONTENT_BINDING","IMMEDIATE_PARENT_LINEAGE","SOURCE_ROLE_PROJECTION","INTAKE_VALIDATOR_SEPARATION","APPEND_ONLY_EVENT","UNANSWERED_HOLD_CHAIN","PARTIAL_BATCH_FAIL_CLOSED","NON_CONCLUSION_NON_EXECUTION")
WORKSTREAMS=tuple((9501+i*25,9525+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
FLOWS=("tenant_to_nurion","nurion_to_upstream","upstream_to_nurion","nurion_to_tenant")
ANSWER_KINDS=("ASSUMPTION_RESPONSE","RESIDUAL_RISK_RESPONSE","ADDITIONAL_EVIDENCE","MEANING_CLARIFICATION","SAFE_BOUNDARY_ACKNOWLEDGEMENT")
OUTCOMES=("CONSISTENT","CLAIM_CONFLICT","MANIFEST_CONFLICT","RECEIPT_CONFLICT","VERSION_CONFLICT")
REQUEST_TYPES={"CONSISTENT":"NO_CLARIFICATION_REQUIRED","CLAIM_CONFLICT":"CLARIFY_CLAIM_MEANING","MANIFEST_CONFLICT":"CLARIFY_MATERIAL_MANIFEST","RECEIPT_CONFLICT":"CLARIFY_RECEIPT_LINEAGE","VERSION_CONFLICT":"CLARIFY_VERSION_PRECEDENCE"}
RESPONDER={"tenant_to_nurion":"TENANT_AGENCY","nurion_to_upstream":"NURION_PG","upstream_to_nurion":"UPSTREAM_PG","nurion_to_tenant":"NURION_PG"}
APPLIED_LESSONS=("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001","ARL-7101-001","ARL-7501-001","ARL-7901-001","ARL-8301-001","ARL-8701-001","ARL-9101-001","ARL-9501-001")
APPLIED_RULES=tuple(f"ARP-{i:02}" for i in range(1,9))
SOURCE_ROLE_KINDS=("readiness-reviewer","preflight-reviewer","reconsideration-reviewer")+("packet-compiler",)*4+("human-deliberation-chair","cross-party-validator","issue-matrix-compiler","issue-matrix-validator","clarification-drafter","clarification-reviewer")
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v):return v.rsplit(":",1)[-1].casefold()
def request_digest(flow,kind,outcome,request_type,source_issue,parent,response_required):return canonical_digest(("SOURCE_CLARIFICATION_REQUEST",flow,kind,outcome,request_type,source_issue,parent,response_required))

@dataclass(frozen=True)
class Control: control_id:int; workstream:str; aspect:str; requirement_ref:str; fixture_digest:str; expected_result:str; digest:str
@dataclass(frozen=True)
class SourceRequest: flow:str; answer_kind:str; outcome:str; request_type:str; source_issue_digest:str; parent_request_digest:str|None; response_required:bool; request_digest:str
@dataclass(frozen=True)
class DocketAnchor:
    anchor_id:str; source_docket_digest:str; request_set_digest:str; lesson_registry_digest:str; remediation_manifest_digest:str; applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]; source_requests:tuple[SourceRequest,...]; source_roles:tuple[str,...]; source_lineage_digest:str; source_sequence:int; is_latest:bool; status:str; digest:str
@dataclass(frozen=True)
class Intake:
    intake_id:str; flow:str; answer_kind:str; request_digest:str; responder_party:str|None; response_document_digest:str|None; parent_intake_digest:str|None; position:int; response_present:bool; held:bool; concluded:bool; accepted:bool; digest:str
@dataclass(frozen=True)
class IntakeDocket:
    docket_id:str; anchor_digest:str; intake_set_digest:str; compiler:str; validator:str; source_lineage_digest:str; complete:bool; held:bool; answered:bool; concluded:bool; recommended:bool; accepted:bool; approved:bool; activated:bool; deployed:bool; status:str; digest:str

def _payload(p):
    p=dict(p)
    if "source_requests" in p:p["source_requests"]=tuple(tuple(x.__dict__.values()) for x in p["source_requests"])
    return p
class SyntheticClarificationResponseIntake:
    def __init__(self):self._controls={};self._anchor=None;self._intakes={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-9501;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #9501-#9900 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor_docket(self,anchor_id,source_docket_digest,request_set_digest,lesson_registry_digest,remediation_manifest_digest,applied_lesson_ids,applied_rule_ids,source_requests,source_roles,source_sequence,is_latest):
        requests=tuple(source_requests);roles=tuple(source_roles);lineage=canonical_digest(("CLARIFICATION_DOCKET_FULL_LINEAGE",source_docket_digest,request_set_digest,tuple(x.request_digest for x in requests),roles))
        p=dict(anchor_id=anchor_id,source_docket_digest=source_docket_digest,request_set_digest=request_set_digest,lesson_registry_digest=lesson_registry_digest,remediation_manifest_digest=remediation_manifest_digest,applied_lesson_ids=tuple(applied_lesson_ids),applied_rule_ids=tuple(applied_rule_ids),source_requests=requests,source_roles=roles,source_lineage_digest=lineage,source_sequence=source_sequence,is_latest=is_latest,status="CLARIFICATION_DOCKET_ANCHORED_ON_HOLD_NOT_ANSWERED");r=DocketAnchor(**p,digest=canonical_digest(_payload(p)))
        with self._lock:
            if not self._anchor_valid(r):raise GovernanceRejected("complete latest clarification docket required")
            if self._anchor:
                if self._anchor==r:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=r;self._event("CLARIFICATION_DOCKET_ANCHORED",r.digest);return r
    def add_intake(self,intake_id,flow,kind,responder_party=None,response_document_digest=None):
        with self._lock:
            keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS);key=(flow,kind)
            if not self._anchor or key not in keys:raise GovernanceRejected("anchored request required")
            pos=keys.index(key);source=self._anchor.source_requests[pos];previous=None if pos==0 else self._intakes.get(keys[pos-1])
            if pos and previous is None:raise GovernanceRejected("immediate prior intake required")
            required=source.response_required
            if required and (responder_party!=RESPONDER[flow] or not _hex(response_document_digest)):raise GovernanceRejected("required response and derived responder required")
            if not required and (responder_party is not None or response_document_digest is not None):raise GovernanceRejected("response forbidden for consistent issue")
            p=dict(intake_id=intake_id,flow=flow,answer_kind=kind,request_digest=source.request_digest,responder_party=responder_party,response_document_digest=response_document_digest,parent_intake_digest=None if previous is None else previous.digest,position=pos+1,response_present=required,held=True,concluded=False,accepted=False);r=Intake(**p,digest=canonical_digest(p))
            if not self._intake_valid(r,key):raise GovernanceRejected("valid ordered response intake required")
            old=self._intakes.get(key)
            if old:
                if old==r:return old
                raise GovernanceRejected("intake conflict")
            self._intakes[key]=r;self._event("RESPONSE_INTAKE_RECORDED",r.digest)
            if required:self._hold("HUMAN_RESPONSE_REVIEW_REQUIRED",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS)
            if self._docket or tuple(self._intakes)!=keys or not self._integrity():raise GovernanceRejected("exact intact intake set required")
            if not _syn(compiler,"response-intake-compiler") or not _syn(validator,"response-intake-validator") or len({_identity(x) for x in self._anchor.source_roles+(compiler,validator)})!=len(self._anchor.source_roles)+2:raise GovernanceRejected("independent compiler and validator required")
            iset=canonical_digest(tuple(self._intakes[k].digest for k in keys));p=dict(docket_id=docket_id,anchor_digest=self._anchor.digest,intake_set_digest=iset,compiler=compiler,validator=validator,source_lineage_digest=self._anchor.source_lineage_digest,complete=True,held=True,answered=False,concluded=False,recommended=False,accepted=False,approved=False,activated=False,deployed=False,status="CLARIFICATION_RESPONSE_INTAKE_READY_ON_HOLD_NOT_REVIEWED");r=IntakeDocket(**p,digest=canonical_digest(p));self._docket=r;self._event("RESPONSE_INTAKE_DOCKET_HELD",r.digest);return r
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 9501<=r.control_id<=9900 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:response-intake-requirement:{(r.control_id-9501)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(9501,9901)) and all(k==v.control_id and self._control_valid(v) for k,v in self._controls.items())
    def _request_valid(self,r,pos,requests):
        key=(FLOWS[pos//5],ANSWER_KINDS[pos%5]);parent=None if pos==0 else requests[pos-1].request_digest;required=r.outcome!="CONSISTENT"
        return (r.flow,r.answer_kind)==key and r.outcome==OUTCOMES[pos%5] and r.request_type==REQUEST_TYPES[r.outcome] and _hex(r.source_issue_digest) and r.parent_request_digest==parent and r.response_required is required and r.request_digest==request_digest(*key,r.outcome,r.request_type,r.source_issue_digest,parent,required)
    def _anchor_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};reqset=canonical_digest(tuple(x.request_digest for x in r.source_requests));docket=canonical_digest(("HUMAN_CLARIFICATION_DOCKET_SOURCE",reqset,r.source_roles));lineage=canonical_digest(("CLARIFICATION_DOCKET_FULL_LINEAGE",r.source_docket_digest,r.request_set_digest,tuple(x.request_digest for x in r.source_requests),r.source_roles))
        return self._registry_valid() and _syn(r.anchor_id,"response-intake-anchor") and len(r.source_requests)==20 and all(self._request_valid(x,i,r.source_requests) for i,x in enumerate(r.source_requests)) and r.request_set_digest==reqset and r.source_docket_digest==docket and all(_hex(x) for x in (r.lesson_registry_digest,r.remediation_manifest_digest)) and r.applied_lesson_ids==APPLIED_LESSONS and r.applied_rule_ids==APPLIED_RULES and len(r.source_roles)==13 and all(_syn(x,k) for x,k in zip(r.source_roles,SOURCE_ROLE_KINDS)) and len({_identity(x) for x in r.source_roles})==13 and r.source_lineage_digest==lineage and isinstance(r.source_sequence,int) and not isinstance(r.source_sequence,bool) and r.source_sequence>0 and r.is_latest is True and r.status=="CLARIFICATION_DOCKET_ANCHORED_ON_HOLD_NOT_ANSWERED" and r.digest==canonical_digest(_payload(p))
    def _intake_valid(self,r,key):
        keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS);pos=keys.index(key) if key in keys else -1
        if not self._anchor or pos<0:return False
        s=self._anchor.source_requests[pos];prev=None if pos==0 else self._intakes.get(keys[pos-1]);p={k:v for k,v in r.__dict__.items() if k!="digest"};required=s.response_required
        return _syn(r.intake_id,"clarification-response-intake") and (r.flow,r.answer_kind)==key and r.request_digest==s.request_digest and r.parent_intake_digest==(None if prev is None else prev.digest) and r.position==pos+1 and r.response_present is required and ((required and r.responder_party==RESPONDER[r.flow] and _hex(r.response_document_digest)) or (not required and r.responder_party is None and r.response_document_digest is None)) and r.held is True and not any((r.concluded,r.accepted)) and r.digest==canonical_digest(p)
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
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._intake_valid(v,k) for k,v in self._intakes.items()):return False
        if self._docket:
            r=self._docket;keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS);p={k:v for k,v in r.__dict__.items() if k!="digest"};iset=canonical_digest(tuple(self._intakes[k].digest for k in keys));roles=self._anchor.source_roles+(r.compiler,r.validator)
            if not _syn(r.docket_id,"clarification-response-intake-docket") or r.anchor_digest!=self._anchor.digest or r.intake_set_digest!=iset or len({_identity(x) for x in roles})!=15 or r.source_lineage_digest!=self._anchor.source_lineage_digest or r.complete is not True or r.held is not True or any((r.answered,r.concluded,r.recommended,r.accepted,r.approved,r.activated,r.deployed)) or r.status!="CLARIFICATION_RESPONSE_INTAKE_READY_ON_HOLD_NOT_REVIEWED" or r.digest!=canonical_digest(p):return False
        events=[]
        if self._anchor:events.append(("CLARIFICATION_DOCKET_ANCHORED",self._anchor.digest))
        events.extend(("RESPONSE_INTAKE_RECORDED",x.digest) for x in self._intakes.values())
        if self._docket:events.append(("RESPONSE_INTAKE_DOCKET_HELD",self._docket.digest))
        holds=[("HUMAN_RESPONSE_REVIEW_REQUIRED",x.digest) for x in self._intakes.values() if x.response_present]
        return [(x["action"],x["artifact_digest"]) for x in self._events]==events and [(x["reason"],x["attachment_digest"]) for x in self._holds]==holds
    def evidence(self):
        ok=self._integrity();complete=len(self._intakes)==20 and self._docket is not None
        return {"range":[9501,9900],"control_count":400,"registered_control_count":len(self._controls),"intake_count":len(self._intakes),"response_count":sum(x.response_present for x in self._intakes.values()),"hold_count":len(self._holds),"integrity_valid":ok,"complete_response_intake_evidence":complete and ok,"maximum_state":"CLARIFICATION_RESPONSE_INTAKE_READY_ON_HOLD_NOT_REVIEWED" if self._docket else "RESPONSE_INTAKE_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"answered":False,"concluded":False,"recommended":False,"accepted":False,"approved":False,"activated":False}
