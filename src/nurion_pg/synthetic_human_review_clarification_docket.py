"""Synthetic/in-memory clarification docket controls #9101-#9500."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES=("ISSUE_MATRIX_SOURCE_ANCHOR","LESSON_RULE_REGISTRY_BINDING","CLARIFICATION_NEED_DERIVATION","CONSISTENT_ITEM_NON_ESCALATION","CLAIM_CONFLICT_QUESTION","MANIFEST_CONFLICT_QUESTION","RECEIPT_CONFLICT_QUESTION","VERSION_CONFLICT_QUESTION","FOUR_DIRECTION_ROUTE_BINDING","REQUEST_ORDERING","SOURCE_ROLE_PROJECTION","DRAFTER_REVIEWER_SEPARATION","APPEND_ONLY_REQUEST_EVENT","HUMAN_RESPONSE_HOLD_CHAIN","PARTIAL_BATCH_FAIL_CLOSED","NON_CONCLUSION_NON_EXECUTION_BOUNDARY")
WORKSTREAMS=tuple((9101+i*25,9125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
FLOWS=("tenant_to_nurion","nurion_to_upstream","upstream_to_nurion","nurion_to_tenant")
ANSWER_KINDS=("ASSUMPTION_RESPONSE","RESIDUAL_RISK_RESPONSE","ADDITIONAL_EVIDENCE","MEANING_CLARIFICATION","SAFE_BOUNDARY_ACKNOWLEDGEMENT")
OUTCOMES=("CONSISTENT","CLAIM_CONFLICT","MANIFEST_CONFLICT","RECEIPT_CONFLICT","VERSION_CONFLICT")
REQUEST_TYPES={"CONSISTENT":"NO_CLARIFICATION_REQUIRED","CLAIM_CONFLICT":"CLARIFY_CLAIM_MEANING","MANIFEST_CONFLICT":"CLARIFY_MATERIAL_MANIFEST","RECEIPT_CONFLICT":"CLARIFY_RECEIPT_LINEAGE","VERSION_CONFLICT":"CLARIFY_VERSION_PRECEDENCE"}
APPLIED_LESSONS=("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001","ARL-7101-001","ARL-7501-001","ARL-7901-001","ARL-8301-001","ARL-8701-001","ARL-9101-001")
APPLIED_RULES=tuple(f"ARP-{i:02}" for i in range(1,9))

def _syn(v,k): return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":",1)[-1].casefold()
def issue_projection_digest(flow,kind,outcome,source_bundle,claim_pair,manifest_pair,receipt_pair,version_pair,parent_issue):
    return canonical_digest(("SOURCE_HUMAN_REVIEW_ISSUE_PROJECTION",flow,kind,outcome,source_bundle,claim_pair,manifest_pair,receipt_pair,version_pair,parent_issue))
def bundle_projection_digest(flow,kind,claim_pair,manifest_pair,receipt_pair,version_pair):
    return canonical_digest(("SOURCE_SUBMISSION_BUNDLE_PROJECTION",flow,kind,claim_pair,manifest_pair,receipt_pair,version_pair))
def actual_outcome(claim_pair,manifest_pair,receipt_pair,version_pair):
    if claim_pair[0]!=claim_pair[1]:return "CLAIM_CONFLICT"
    if manifest_pair[0]!=manifest_pair[1]:return "MANIFEST_CONFLICT"
    if receipt_pair[0]!=receipt_pair[1]:return "RECEIPT_CONFLICT"
    if version_pair[0]!=version_pair[1]:return "VERSION_CONFLICT"
    return "CONSISTENT"
def _digest_payload(p):
    p=dict(p)
    if "source_issues" in p:p["source_issues"]=tuple(tuple(x.__dict__.values()) for x in p["source_issues"])
    return p

@dataclass(frozen=True)
class Control:
    control_id:int; workstream:str; aspect:str; requirement_ref:str; fixture_digest:str; expected_result:str; digest:str
@dataclass(frozen=True)
class SourceIssue:
    flow:str; answer_kind:str; outcome:str; source_bundle_digest:str; claim_pair:tuple[str,str]; manifest_pair:tuple[str,str]; receipt_pair:tuple[str,str]; version_pair:tuple[int,int]; parent_issue_digest:str|None; projection_digest:str
@dataclass(frozen=True)
class MatrixAnchor:
    anchor_id:str; source_matrix_digest:str; issue_set_digest:str; lesson_registry_digest:str; remediation_manifest_digest:str; applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]; source_issues:tuple[SourceIssue,...]; source_reviewers:tuple[str,...]; source_compilers:tuple[str,...]; source_chair:str; source_validator:str; matrix_compiler:str; matrix_validator:str; source_lineage_digest:str; source_sequence:int; is_latest:bool; status:str; digest:str
@dataclass(frozen=True)
class ClarificationRequest:
    request_id:str; flow:str; answer_kind:str; outcome:str; request_type:str; source_issue_digest:str; parent_request_digest:str|None; position:int; response_required:bool; held:bool; concluded:bool; recommended:bool; accepted:bool; digest:str
@dataclass(frozen=True)
class ClarificationDocket:
    docket_id:str; anchor_digest:str; ordered_request_set_digest:str; drafter:str; reviewer:str; source_lineage_digest:str; complete:bool; held:bool; concluded:bool; recommended:bool; accepted:bool; approved:bool; activated:bool; deployed:bool; status:str; digest:str

class SyntheticHumanReviewClarificationDocket:
    def __init__(self): self._controls={}; self._anchor=None; self._requests={}; self._docket=None; self._events=[]; self._holds=[]; self._lock=RLock()
    def _expected(self,cid): i=cid-9101; return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result); row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(row): raise GovernanceRejected("valid #9101-#9500 control required")
            old=self._controls.get(cid)
            if old:
                if old==row:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=row; return row
    def anchor_matrix(self,anchor_id,source_matrix_digest,issue_set_digest,lesson_registry_digest,remediation_manifest_digest,applied_lesson_ids,applied_rule_ids,source_issues,source_reviewers,source_compilers,source_chair,source_validator,matrix_compiler,matrix_validator,source_sequence,is_latest):
        issues=tuple(source_issues); reviewers=tuple(source_reviewers); compilers=tuple(source_compilers)
        lineage=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_FULL_LINEAGE",source_matrix_digest,issue_set_digest,tuple(x.projection_digest for x in issues),reviewers,compilers,source_chair,source_validator,matrix_compiler,matrix_validator))
        p=dict(anchor_id=anchor_id,source_matrix_digest=source_matrix_digest,issue_set_digest=issue_set_digest,lesson_registry_digest=lesson_registry_digest,remediation_manifest_digest=remediation_manifest_digest,applied_lesson_ids=tuple(applied_lesson_ids),applied_rule_ids=tuple(applied_rule_ids),source_issues=issues,source_reviewers=reviewers,source_compilers=compilers,source_chair=source_chair,source_validator=source_validator,matrix_compiler=matrix_compiler,matrix_validator=matrix_validator,source_lineage_digest=lineage,source_sequence=source_sequence,is_latest=is_latest,status="ISSUE_MATRIX_ANCHORED_ON_HOLD_NOT_CONCLUDED")
        row=MatrixAnchor(**p,digest=canonical_digest(_digest_payload(p)))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("complete latest issue matrix lineage required")
            if self._anchor:
                if self._anchor==row:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=row; self._event("ISSUE_MATRIX_ANCHORED",row.digest); return row
    def add_request(self,request_id,flow,answer_kind):
        with self._lock:
            keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS); key=(flow,answer_kind)
            if not self._anchor or key not in keys: raise GovernanceRejected("anchored known issue required")
            pos=keys.index(key); previous=None if pos==0 else self._requests.get(keys[pos-1])
            if pos and previous is None: raise GovernanceRejected("immediate prior request required")
            source=self._anchor.source_issues[pos]; request_type=REQUEST_TYPES[source.outcome]
            p=dict(request_id=request_id,flow=flow,answer_kind=answer_kind,outcome=source.outcome,request_type=request_type,source_issue_digest=source.projection_digest,parent_request_digest=None if previous is None else previous.digest,position=pos+1,response_required=source.outcome!="CONSISTENT",held=True,concluded=False,recommended=False,accepted=False)
            row=ClarificationRequest(**p,digest=canonical_digest(p))
            if not self._request_valid(row,key): raise GovernanceRejected("derived ordered clarification request required")
            old=self._requests.get(key)
            if old:
                if old==row:return old
                raise GovernanceRejected("request conflict")
            self._requests[key]=row; self._event("CLARIFICATION_REQUEST_RECORDED",row.digest)
            if row.response_required:self._hold("HUMAN_CLARIFICATION_RESPONSE_REQUIRED",row.digest)
            return row
    def finalize(self,docket_id,drafter,reviewer):
        with self._lock:
            keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS)
            if self._docket or tuple(self._requests)!=keys or not self._integrity(): raise GovernanceRejected("exact intact request set required")
            occupied=self._roles()
            if not _syn(drafter,"clarification-drafter") or not _syn(reviewer,"clarification-reviewer") or len({_identity(x) for x in occupied+(drafter,reviewer)})!=len(occupied)+2: raise GovernanceRejected("independent drafter and reviewer required")
            request_set=canonical_digest(tuple(self._requests[k].digest for k in keys)); p=dict(docket_id=docket_id,anchor_digest=self._anchor.digest,ordered_request_set_digest=request_set,drafter=drafter,reviewer=reviewer,source_lineage_digest=self._anchor.source_lineage_digest,complete=True,held=True,concluded=False,recommended=False,accepted=False,approved=False,activated=False,deployed=False,status="HUMAN_CLARIFICATION_DOCKET_READY_ON_HOLD_NOT_ANSWERED")
            row=ClarificationDocket(**p,digest=canonical_digest(p)); self._docket=row; self._event("HUMAN_CLARIFICATION_DOCKET_HELD",row.digest); return row
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}; return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 9101<=r.control_id<=9500 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:clarification-docket-requirement:{(r.control_id-9101)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self): return set(self._controls)==set(range(9101,9501)) and all(k==v.control_id and self._control_valid(v) for k,v in self._controls.items())
    def _roles(self):
        a=self._anchor; return a.source_reviewers+a.source_compilers+(a.source_chair,a.source_validator,a.matrix_compiler,a.matrix_validator)
    def _source_issue_valid(self,row,pos,issues):
        key=(FLOWS[pos//5],ANSWER_KINDS[pos%5]); pairs=(row.claim_pair,row.manifest_pair,row.receipt_pair); versions=row.version_pair
        expected_parent=None if pos==0 else issues[pos-1].projection_digest
        projection=issue_projection_digest(*key,row.outcome,row.source_bundle_digest,row.claim_pair,row.manifest_pair,row.receipt_pair,row.version_pair,row.parent_issue_digest)
        return (row.flow,row.answer_kind)==key and row.outcome==actual_outcome(row.claim_pair,row.manifest_pair,row.receipt_pair,row.version_pair) and row.source_bundle_digest==bundle_projection_digest(*key,row.claim_pair,row.manifest_pair,row.receipt_pair,row.version_pair) and all(len(x)==2 and all(_hex(v) for v in x) for x in pairs) and len(versions)==2 and all(isinstance(v,int) and not isinstance(v,bool) and v>0 for v in versions) and row.parent_issue_digest==expected_parent and row.projection_digest==projection
    def _anchor_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}; roles=r.source_reviewers+r.source_compilers+(r.source_chair,r.source_validator,r.matrix_compiler,r.matrix_validator)
        issue_set=canonical_digest(tuple(x.projection_digest for x in r.source_issues)); source_matrix=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_SOURCE",issue_set,r.matrix_compiler,r.matrix_validator))
        lineage=canonical_digest(("HUMAN_REVIEW_ISSUE_MATRIX_FULL_LINEAGE",r.source_matrix_digest,r.issue_set_digest,tuple(x.projection_digest for x in r.source_issues),r.source_reviewers,r.source_compilers,r.source_chair,r.source_validator,r.matrix_compiler,r.matrix_validator))
        return self._registry_valid() and _syn(r.anchor_id,"clarification-docket-anchor") and all(_hex(x) for x in (r.source_matrix_digest,r.issue_set_digest,r.lesson_registry_digest,r.remediation_manifest_digest)) and len(r.source_issues)==20 and r.issue_set_digest==issue_set and r.source_matrix_digest==source_matrix and all(self._source_issue_valid(x,i,r.source_issues) for i,x in enumerate(r.source_issues)) and r.applied_lesson_ids==APPLIED_LESSONS and r.applied_rule_ids==APPLIED_RULES and len(r.source_reviewers)==3 and len(r.source_compilers)==4 and all(_syn(x,k) for x,k in zip(r.source_reviewers,("readiness-reviewer","preflight-reviewer","reconsideration-reviewer"))) and all(_syn(x,"packet-compiler") for x in r.source_compilers) and _syn(r.source_chair,"human-deliberation-chair") and _syn(r.source_validator,"cross-party-validator") and _syn(r.matrix_compiler,"issue-matrix-compiler") and _syn(r.matrix_validator,"issue-matrix-validator") and len({_identity(x) for x in roles})==11 and r.source_lineage_digest==lineage and isinstance(r.source_sequence,int) and not isinstance(r.source_sequence,bool) and r.source_sequence>0 and r.is_latest is True and r.status=="ISSUE_MATRIX_ANCHORED_ON_HOLD_NOT_CONCLUDED" and r.digest==canonical_digest(_digest_payload(p))
    def _request_valid(self,r,key):
        keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS); pos=keys.index(key) if key in keys else -1
        if not self._anchor or pos<0:return False
        source=self._anchor.source_issues[pos]; previous=None if pos==0 else self._requests.get(keys[pos-1]); p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return _syn(r.request_id,"clarification-request") and key==(r.flow,r.answer_kind) and r.position==pos+1 and r.outcome==source.outcome and r.request_type==REQUEST_TYPES[source.outcome] and r.source_issue_digest==source.projection_digest and r.parent_request_digest==(None if previous is None else previous.digest) and r.response_required is (source.outcome!="CONSISTENT") and r.held is True and not any((r.concluded,r.recommended,r.accepted)) and r.digest==canonical_digest(p)
    def _event(self,action,artifact):
        prev=self._events[-1]["digest"] if self._events else None; p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev); self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):
        prev=self._holds[-1]["digest"] if self._holds else None; p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev); self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(rows,event):
        prev=None
        for i,r in enumerate(rows,1):
            keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest"); p={k:r.get(k) for k in keys}
            if r!={**p,"digest":canonical_digest(p)} or r["sequence"]!=i or r["previous_digest"]!=prev:return False
            prev=r["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._request_valid(v,k) for k,v in self._requests.items()):return False
        if self._docket:
            r=self._docket; keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS); p={k:v for k,v in r.__dict__.items() if k!="digest"}; occupied=self._roles(); request_set=canonical_digest(tuple(self._requests[k].digest for k in keys))
            if not _syn(r.docket_id,"human-clarification-docket") or r.anchor_digest!=self._anchor.digest or r.ordered_request_set_digest!=request_set or not _syn(r.drafter,"clarification-drafter") or not _syn(r.reviewer,"clarification-reviewer") or len({_identity(x) for x in occupied+(r.drafter,r.reviewer)})!=len(occupied)+2 or r.source_lineage_digest!=self._anchor.source_lineage_digest or r.complete is not True or r.held is not True or any((r.concluded,r.recommended,r.accepted,r.approved,r.activated,r.deployed)) or r.status!="HUMAN_CLARIFICATION_DOCKET_READY_ON_HOLD_NOT_ANSWERED" or r.digest!=canonical_digest(p):return False
        expected_events=[]
        if self._anchor:expected_events.append(("ISSUE_MATRIX_ANCHORED",self._anchor.digest))
        expected_events.extend(("CLARIFICATION_REQUEST_RECORDED",x.digest) for x in self._requests.values())
        if self._docket:expected_events.append(("HUMAN_CLARIFICATION_DOCKET_HELD",self._docket.digest))
        expected_holds=[("HUMAN_CLARIFICATION_RESPONSE_REQUIRED",x.digest) for x in self._requests.values() if x.response_required]
        return [(x["action"],x["artifact_digest"]) for x in self._events]==expected_events and [(x["reason"],x["attachment_digest"]) for x in self._holds]==expected_holds
    def evidence(self):
        ok=self._integrity(); complete=len(self._requests)==20 and self._docket is not None
        return {"range":[9101,9500],"control_count":400,"workstream_count":16,"controls_per_workstream":25,"control_matrix_valid":WORKSTREAMS==tuple((9101+i*25,9125+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25,"registered_control_count":len(self._controls),"request_count":len(self._requests),"response_required_count":sum(x.response_required for x in self._requests.values()),"hold_count":len(self._holds),"event_count":len(self._events),"integrity_valid":ok,"complete_clarification_docket_evidence":complete and ok,"maximum_state":"HUMAN_CLARIFICATION_DOCKET_READY_ON_HOLD_NOT_ANSWERED" if self._docket else "CLARIFICATION_DOCKET_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"accepted":False,"recommended":False,"concluded":False,"approved":False,"activated":False}
