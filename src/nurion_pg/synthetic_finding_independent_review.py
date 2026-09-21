"""Synthetic independent finding review controls #11501-#11900.

Pure in-memory governance layer.  It preserves N/A findings and opens human
finding review holds; it cannot conclude, recommend, accept, resolve, approve,
activate, deploy, perform I/O, call a PG, or write a financial ledger.
"""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_rereview_finding_observation import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, CASE_KEYS, ROUTES,
    SOURCE_ACTOR_KINDS, Finding, SourceReReview, SourceSubmission,
    finding_digest, observation_projection_digest, rereview_digest,
    source_submission_digest,
)
from .synthetic_rebuttal_correction_submission_validation import RESPONDER, derived_receipt_digest

APPLIED_LESSONS = PRIOR_LESSONS
WORKSTREAM_NAMES = (
    "FINDING_DOCKET_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "SOURCE_FINDING_SEMANTIC_RECONSTRUCTION", "NO_FINDING_MARKER_PRESERVATION",
    "REBUTTAL_FINDING_INDEPENDENT_REVIEW", "CORRECTION_FINDING_INDEPENDENT_REVIEW",
    "INDEPENDENT_FINDING_REVIEWER_ASSIGNMENT", "FINDING_CUSTODIAN_ASSIGNMENT",
    "IMMEDIATE_PARENT_REVIEW_LINEAGE", "FULL_SOURCE_ACTOR_PROJECTION",
    "PRIOR_REREVIEWER_PROJECTION", "FINDING_ROLE_SEPARATION",
    "APPEND_ONLY_REVIEW_EVENT", "UNRESOLVED_REVIEW_HOLD_CHAIN",
    "PARTIAL_BATCH_FAIL_CLOSED", "NON_CONCLUSION_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((11501+i*25,11525+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema","required_fields","semantic_label","source_type","tenant_scope",
    "role_scope","state_precondition","latest_sequence","source_binding",
    "digest_recalculation","negative_path","missing_input","duplicate_input","replay",
    "conflict","stale_version","concurrency","partial_batch","ordering","append_only",
    "hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution",
)
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})

def _syn(v,k): return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v): return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control:
    control_id:int; workstream:str; aspect:str; requirement_ref:str
    fixture_digest:str; expected_result:str; digest:str

@dataclass(frozen=True)
class Anchor:
    anchor_id:str; source_docket_digest:str; source_finding_set_digest:str
    lesson_registry_digest:str; remediation_manifest_digest:str
    applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]
    source_submissions:tuple[SourceSubmission,...]; source_rereviews:tuple[SourceReReview,...]
    source_findings:tuple[Finding,...]; source_actor_roles:tuple[str,...]
    source_submission_compiler:str; source_submission_validator:str
    source_rereview_compiler:str; source_rereview_validator:str
    source_finding_compiler:str; source_finding_validator:str
    full_source_lineage_digest:str; source_sequence:int; is_latest:bool; status:str; digest:str

@dataclass(frozen=True)
class FindingReview:
    review_id:str; flow:str; answer_kind:str; source_finding_digest:str; route:str
    reviewer:str|None; custodian:str|None; marker:str; parent_review_digest:str|None
    position:int; judgment_packet:tuple; judgment_packet_digest:str|None
    review_projection_digest:str; held:bool; pending_human_finding_review:bool
    concluded:bool; recommended:bool; accepted:bool; resolved:bool; digest:str

@dataclass(frozen=True)
class Docket:
    docket_id:str; anchor_digest:str; review_set_digest:str; compiler:str; validator:str
    full_role_lineage_digest:str; complete:bool; held:bool; pending_human_finding_review:bool
    concluded:bool; recommended:bool; accepted:bool; resolved:bool; approved:bool
    activated:bool; deployed:bool; status:str; digest:str

def judgment_packet(source, route):
    """Deterministic, non-authoritative preparation method; never a judgment."""
    if route == "NOT_APPLICABLE_PRESERVED": return ()
    return (
        ("conclusion_method", (("claim", source), ("evidence", source), ("counterevidence_required", True),
                               ("uncertainty", "UNRESOLVED"), ("hold_condition", "HUMAN_FINDING_REVIEW_REQUIRED"))),
        ("recommendation_method", (("alternatives", (
            ("correction", "effect", "risk", "cost", "reversibility"),
            ("preserve_and_escalate", "effect", "risk", "cost", "reversibility"))),
            ("priority_basis", (source, route)))),
        ("acceptance_method", (("met_criteria", ()), ("unmet_criteria", ("HUMAN_APPROVAL",)),
                               ("residual_risk", "PRESENT"), ("owner", "HUMAN_OWNER_REQUIRED"),
                               ("explicit_human_approval_gate", True))),
        ("resolution_method", (("root_cause_removal", "UNVERIFIED"), ("correction_plan", "DRAFT_ONLY"),
                               ("negative_test", "REQUIRED"), ("regression", "REQUIRED"),
                               ("recurrence_lesson", "REQUIRED"), ("rollback_condition", "REQUIRED"),
                               ("resume_condition", "EXPLICIT_HUMAN_APPROVAL_REQUIRED"))),
        ("correction_direction", (route, source, "HUMAN_DETERMINATION_REQUIRED")),
        ("overcoming_options", ("CORRECT_AND_REVALIDATE", "PRESERVE_AND_ESCALATE")),
        ("validation_criteria", ("NEGATIVE_TEST_PASS", "REGRESSION_PASS", "LINEAGE_INTACT")),
        ("residual_risk", ("NOT_YET_ASSESSED_BY_HUMAN", source)),
        ("escalation_condition", ("UNCERTAINTY_OR_UNMET_CRITERIA", "HUMAN_REVIEW_REQUIRED")),
    )

def review_projection_digest(source,route,reviewer,custodian,marker,packet_digest):
    return canonical_digest(("INDEPENDENT_FINDING_REVIEW_PROJECTION",source,route,reviewer,custodian,marker,packet_digest))

def finding_review_digest(review_id,flow,kind,source,route,reviewer,custodian,marker,parent,position,packet,packet_digest,projection):
    return canonical_digest(("INDEPENDENT_FINDING_REVIEW",review_id,flow,kind,source,route,reviewer,custodian,marker,parent,position,packet,packet_digest,projection))

def _anchor_payload(p):
    p=dict(p)
    for key in ("source_submissions","source_rereviews","source_findings"):
        p[key]=tuple(tuple(x.__dict__.values()) for x in p[key])
    return p

class SyntheticFindingIndependentReview:
    def __init__(self):
        self._controls={};self._anchor=None;self._reviews={};self._docket=None
        self._events=[];self._holds=[];self._lock=RLock()

    def _expected(self,cid):
        i=cid-11501;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]

    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result)
        row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(row):raise GovernanceRejected("valid #11501-#11900 control required")
            old=self._controls.get(cid)
            if old:
                if old==row:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=row;return row

    def anchor(self,anchor_id,source_docket_digest,source_set_digest,registry_digest,manifest_digest,
               lessons,rules,submissions,rereviews,findings,source_roles,sc,sv,rc,rv,fc,fv,sequence,is_latest):
        submissions,rereviews,findings,source_roles=tuple(submissions),tuple(rereviews),tuple(findings),tuple(source_roles)
        lineage=self._source_lineage(source_docket_digest,source_set_digest,submissions,rereviews,findings,source_roles,sc,sv,rc,rv,fc,fv)
        p=dict(anchor_id=anchor_id,source_docket_digest=source_docket_digest,source_finding_set_digest=source_set_digest,
            lesson_registry_digest=registry_digest,remediation_manifest_digest=manifest_digest,
            applied_lesson_ids=tuple(lessons),applied_rule_ids=tuple(rules),source_submissions=submissions,
            source_rereviews=rereviews,source_findings=findings,source_actor_roles=source_roles,
            source_submission_compiler=sc,source_submission_validator=sv,source_rereview_compiler=rc,
            source_rereview_validator=rv,source_finding_compiler=fc,source_finding_validator=fv,
            full_source_lineage_digest=lineage,source_sequence=sequence,is_latest=is_latest,
            status="FINDING_DOCKET_ANCHORED_INDEPENDENT_REVIEW_NOT_CONCLUDED")
        row=Anchor(**p,digest=canonical_digest(_anchor_payload(p)))
        with self._lock:
            if not self._anchor_valid(row):raise GovernanceRejected("complete latest finding docket required")
            if self._anchor:
                if self._anchor==row:return row
                raise GovernanceRejected("anchor conflict")
            self._anchor=row;self._event("FINDING_DOCKET_ANCHORED",row.digest);return row

    def add_review(self,review_id,flow,kind,reviewer=None,custodian=None):
        with self._lock:
            key=(flow,kind)
            if not self._anchor or key not in CASE_KEYS:raise GovernanceRejected("anchored finding required")
            position=CASE_KEYS.index(key);source=self._anchor.source_findings[position]
            previous=None if position==0 else self._reviews.get(CASE_KEYS[position-1])
            if position and previous is None:raise GovernanceRejected("immediate prior review required")
            if source.route=="NOT_APPLICABLE_PRESERVED":
                if reviewer is not None or custodian is not None:raise GovernanceRejected("N/A forbids review actors")
                marker="NO_FINDING_MARKER_PRESERVED"
            else:
                if not _syn(reviewer,"independent-finding-reviewer") or not _syn(custodian,"finding-review-custodian"):
                    raise GovernanceRejected("reviewer and custodian required")
                occupied=self._source_actors()+tuple(y for x in self._reviews.values() for y in (x.reviewer,x.custodian) if y)
                if len({_identity(x) for x in occupied+(reviewer,custodian)})!=len(occupied)+2:
                    raise GovernanceRejected("finding review actor collision")
                marker="HUMAN_FINDING_REVIEW_PENDING"
            parent=None if previous is None else previous.digest
            packet=judgment_packet(source.digest,source.route);packet_digest=canonical_digest(packet) if packet else None
            projection=review_projection_digest(source.digest,source.route,reviewer,custodian,marker,packet_digest)
            digest=finding_review_digest(review_id,flow,kind,source.digest,source.route,reviewer,custodian,marker,parent,position+1,packet,packet_digest,projection)
            row=FindingReview(review_id,flow,kind,source.digest,source.route,reviewer,custodian,marker,parent,position+1,packet,packet_digest,projection,True,source.route!="NOT_APPLICABLE_PRESERVED",False,False,False,False,digest)
            if not self._review_valid(row,key):raise GovernanceRejected("valid independent finding review required")
            old=self._reviews.get(key)
            if old:
                if old==row:return old
                raise GovernanceRejected("review conflict")
            self._reviews[key]=row;self._event("INDEPENDENT_FINDING_REVIEW_RECORDED",row.digest)
            if row.pending_human_finding_review:self._hold("HUMAN_FINDING_REVIEW_REQUIRED",row.digest)
            return row

    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._reviews)!=CASE_KEYS or not self._integrity():raise GovernanceRejected("complete intact finding review batch required")
            actors=self._source_actors()+tuple(y for x in self._reviews.values() for y in (x.reviewer,x.custodian) if y)+(compiler,validator)
            if not _syn(compiler,"finding-review-docket-compiler") or not _syn(validator,"finding-review-docket-validator") or len({_identity(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            review_set=canonical_digest(tuple(self._reviews[k].digest for k in CASE_KEYS));lineage=canonical_digest(("COMPLETE_FINDING_REVIEW_ROLE_LINEAGE",self._anchor.full_source_lineage_digest,actors))
            p=dict(docket_id=docket_id,anchor_digest=self._anchor.digest,review_set_digest=review_set,compiler=compiler,validator=validator,full_role_lineage_digest=lineage,complete=True,held=True,pending_human_finding_review=True,concluded=False,recommended=False,accepted=False,resolved=False,approved=False,activated=False,deployed=False,status="INDEPENDENT_FINDING_REVIEW_DOCKET_ON_HOLD")
            row=Docket(**p,digest=canonical_digest(p));self._docket=row;self._event("INDEPENDENT_FINDING_REVIEW_DOCKET_HELD",row.digest);return row

    def _control_valid(self,row):
        p={k:v for k,v in row.__dict__.items() if k!="digest"}
        return isinstance(row.control_id,int) and not isinstance(row.control_id,bool) and 11501<=row.control_id<=11900 and self._expected(row.control_id)==(row.workstream,row.aspect) and row.requirement_ref==f"synthetic:finding-review-requirement:{(row.control_id-11501)//25:02}" and _hex(row.fixture_digest) and row.expected_result==("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS") and row.digest==canonical_digest(p)

    def _registry_valid(self):return set(self._controls)==set(range(11501,11901)) and all(self._control_valid(x) for x in self._controls.values())

    def _submission_valid(self,row,i,rows):
        parent=None if i==0 else rows[i-1].digest;flow,kind=CASE_KEYS[i];route=ROUTES[i%5]
        if route=="NOT_APPLICABLE_PRESERVED":material=row.submitter_party is None and row.document_digest is None and row.receipt_digest is None and row.marker=="NO_SUBMISSION_REQUIRED"
        else:material=row.submitter_party==RESPONDER[flow] and _hex(row.document_digest) and row.receipt_digest==derived_receipt_digest(flow,kind,row.source_review_digest,route,row.submitter_party,row.document_digest) and row.marker=="SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        return _syn(row.submission_id,"rebuttal-correction-submission") and (row.flow,row.answer_kind)==(flow,kind) and _hex(row.source_review_digest) and row.route==route and material and row.parent_submission_digest==parent and row.position==i+1 and row.held is True and row.validated is True and not row.resolved and not row.accepted and row.digest==source_submission_digest(row)

    def _rereview_valid(self,row,i,rows,subs):
        parent=None if i==0 else rows[i-1].digest;source=subs[i]
        if source.route=="NOT_APPLICABLE_PRESERVED":state=row.reviewer is None and row.marker=="NO_SUBMISSION_MARKER_PRESERVED" and row.pending_human_reexamination is False
        else:state=_syn(row.reviewer,"independent-human-rereviewer") and row.marker=="HUMAN_REEXAMINATION_PENDING" and row.pending_human_reexamination is True
        expected=rereview_digest(row.rereview_id,row.flow,row.answer_kind,source.digest,source.route,row.reviewer,row.marker,parent,i+1)
        return _syn(row.rereview_id,"independent-rereview") and (row.flow,row.answer_kind)==CASE_KEYS[i] and row.source_submission_digest==source.digest and row.route==source.route and state and row.parent_rereview_digest==parent and row.position==i+1 and row.held is True and not any((row.concluded,row.resolved,row.accepted)) and row.digest==expected

    def _finding_valid(self,row,i,rows,rereviews):
        parent=None if i==0 else rows[i-1].digest;source=rereviews[i]
        if source.route=="NOT_APPLICABLE_PRESERVED":state=row.drafter is None and row.reviewer is None and row.marker=="NO_FINDING_MARKER_PRESERVED" and row.pending_human_finding_review is False
        else:state=_syn(row.drafter,"finding-drafter") and _syn(row.reviewer,"finding-reviewer") and row.marker=="HUMAN_FINDING_REVIEW_PENDING" and row.pending_human_finding_review is True
        projection=observation_projection_digest(source.digest,source.route,row.drafter,row.reviewer,row.marker)
        expected=finding_digest(row.finding_id,row.flow,row.answer_kind,source.digest,source.route,row.drafter,row.reviewer,row.marker,parent,i+1,projection)
        return _syn(row.finding_id,"finding-observation") and (row.flow,row.answer_kind)==CASE_KEYS[i] and row.source_rereview_digest==source.digest and row.route==source.route and state and row.parent_finding_digest==parent and row.position==i+1 and row.observation_projection_digest==projection and row.held is True and not any((row.concluded,row.recommended,row.accepted,row.resolved)) and row.digest==expected

    @staticmethod
    def _source_lineage(docket,fset,subs,rereviews,findings,roles,sc,sv,rc,rv,fc,fv):
        return canonical_digest(("COMPLETE_FINDING_SOURCE_ROLE_LINEAGE",docket,fset,tuple(x.digest for x in subs),tuple(x.digest for x in rereviews),tuple(x.digest for x in findings),roles,sc,sv,tuple(x.reviewer for x in rereviews if x.reviewer),rc,rv,tuple(y for x in findings for y in (x.drafter,x.reviewer) if y),fc,fv))

    def _source_actors(self):
        a=self._anchor;return a.source_actor_roles+(a.source_submission_compiler,a.source_submission_validator)+tuple(x.reviewer for x in a.source_rereviews if x.reviewer)+(a.source_rereview_compiler,a.source_rereview_validator)+tuple(y for x in a.source_findings for y in (x.drafter,x.reviewer) if y)+(a.source_finding_compiler,a.source_finding_validator)

    def _anchor_valid(self,a):
        p={k:v for k,v in a.__dict__.items() if k!="digest"};fset=canonical_digest(tuple(x.digest for x in a.source_findings));docket=canonical_digest(("FINDING_OBSERVATION_DOCKET_SOURCE",fset,a.source_finding_compiler,a.source_finding_validator));lineage=self._source_lineage(docket,fset,a.source_submissions,a.source_rereviews,a.source_findings,a.source_actor_roles,a.source_submission_compiler,a.source_submission_validator,a.source_rereview_compiler,a.source_rereview_validator,a.source_finding_compiler,a.source_finding_validator);actors=a.source_actor_roles+(a.source_submission_compiler,a.source_submission_validator)+tuple(x.reviewer for x in a.source_rereviews if x.reviewer)+(a.source_rereview_compiler,a.source_rereview_validator)+tuple(y for x in a.source_findings for y in (x.drafter,x.reviewer) if y)+(a.source_finding_compiler,a.source_finding_validator)
        return self._registry_valid() and _syn(a.anchor_id,"finding-independent-review-anchor") and len(a.source_submissions)==len(a.source_rereviews)==len(a.source_findings)==20 and len({x.submission_id for x in a.source_submissions})==len({x.rereview_id for x in a.source_rereviews})==len({x.finding_id for x in a.source_findings})==20 and all(self._submission_valid(x,i,a.source_submissions) for i,x in enumerate(a.source_submissions)) and all(self._rereview_valid(x,i,a.source_rereviews,a.source_submissions) for i,x in enumerate(a.source_rereviews)) and all(self._finding_valid(x,i,a.source_findings,a.source_rereviews) for i,x in enumerate(a.source_findings)) and a.source_finding_set_digest==fset and a.source_docket_digest==docket and _hex(a.lesson_registry_digest) and _hex(a.remediation_manifest_digest) and a.applied_lesson_ids==APPLIED_LESSONS and a.applied_rule_ids==APPLIED_RULES and len(a.source_actor_roles)==32 and all(_syn(x,k) for x,k in zip(a.source_actor_roles,SOURCE_ACTOR_KINDS)) and _syn(a.source_submission_compiler,"submission-docket-compiler") and _syn(a.source_submission_validator,"submission-docket-validator") and _syn(a.source_rereview_compiler,"rereview-docket-compiler") and _syn(a.source_rereview_validator,"rereview-docket-validator") and _syn(a.source_finding_compiler,"finding-docket-compiler") and _syn(a.source_finding_validator,"finding-docket-validator") and len(actors)==86 and len({_identity(x) for x in actors})==86 and a.full_source_lineage_digest==lineage and isinstance(a.source_sequence,int) and not isinstance(a.source_sequence,bool) and a.source_sequence>0 and a.is_latest is True and a.status=="FINDING_DOCKET_ANCHORED_INDEPENDENT_REVIEW_NOT_CONCLUDED" and a.digest==canonical_digest(_anchor_payload(p))

    def _review_valid(self,row,key):
        if not self._anchor or key not in CASE_KEYS:return False
        i=CASE_KEYS.index(key);source=self._anchor.source_findings[i];previous=None if i==0 else self._reviews.get(CASE_KEYS[i-1])
        if source.route=="NOT_APPLICABLE_PRESERVED":state=row.reviewer is None and row.custodian is None and row.marker=="NO_FINDING_MARKER_PRESERVED" and row.pending_human_finding_review is False
        else:state=_syn(row.reviewer,"independent-finding-reviewer") and _syn(row.custodian,"finding-review-custodian") and row.marker=="HUMAN_FINDING_REVIEW_PENDING" and row.pending_human_finding_review is True
        packet=judgment_packet(source.digest,source.route);packet_digest=canonical_digest(packet) if packet else None
        packet_valid=(row.judgment_packet==packet and row.judgment_packet_digest==packet_digest)
        if source.route!="NOT_APPLICABLE_PRESERVED":
            packet_map=dict(packet);options=dict(packet_map["recommendation_method"])["alternatives"]
            packet_valid=packet_valid and len(options)>=2 and dict(packet_map["acceptance_method"])["explicit_human_approval_gate"] is True and dict(packet_map["resolution_method"])["negative_test"]=="REQUIRED" and dict(packet_map["resolution_method"])["regression"]=="REQUIRED"
            packet_valid=packet_valid and packet_map["residual_risk"][0]=="NOT_YET_ASSESSED_BY_HUMAN"
        projection=review_projection_digest(source.digest,source.route,row.reviewer,row.custodian,row.marker,packet_digest);parent=None if previous is None else previous.digest;expected=finding_review_digest(row.review_id,row.flow,row.answer_kind,source.digest,source.route,row.reviewer,row.custodian,row.marker,parent,i+1,packet,packet_digest,projection)
        ids=[x.review_id for k,x in self._reviews.items() if k!=key]
        return _syn(row.review_id,"independent-finding-review") and row.review_id not in ids and (row.flow,row.answer_kind)==key and row.source_finding_digest==source.digest and row.route==source.route and state and row.parent_review_digest==parent and row.position==i+1 and packet_valid and row.review_projection_digest==projection and row.held is True and not any((row.concluded,row.recommended,row.accepted,row.resolved)) and row.digest==expected

    def _event(self,action,artifact):
        prev=self._events[-1]["digest"] if self._events else None;p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev);self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):
        prev=self._holds[-1]["digest"] if self._holds else None;p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev);self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(rows,event):
        prev=None
        for i,row in enumerate(rows,1):
            keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest");p={k:row.get(k) for k in keys}
            if row!={**p,"digest":canonical_digest(p)} or row["sequence"]!=i or row["previous_digest"]!=prev:return False
            prev=row["digest"]
        return True

    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._review_valid(v,k) for k,v in self._reviews.items()):return False
        events=[]
        if self._anchor:events.append(("FINDING_DOCKET_ANCHORED",self._anchor.digest))
        events.extend(("INDEPENDENT_FINDING_REVIEW_RECORDED",x.digest) for x in self._reviews.values())
        if self._docket:events.append(("INDEPENDENT_FINDING_REVIEW_DOCKET_HELD",self._docket.digest))
        holds=[("HUMAN_FINDING_REVIEW_REQUIRED",x.digest) for x in self._reviews.values() if x.pending_human_finding_review]
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if self._docket:
            r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._source_actors()+tuple(y for x in self._reviews.values() for y in (x.reviewer,x.custodian) if y)+(r.compiler,r.validator);lineage=canonical_digest(("COMPLETE_FINDING_REVIEW_ROLE_LINEAGE",self._anchor.full_source_lineage_digest,actors))
            if not _syn(r.docket_id,"finding-independent-review-docket") or r.anchor_digest!=self._anchor.digest or r.review_set_digest!=canonical_digest(tuple(self._reviews[k].digest for k in CASE_KEYS)) or not _syn(r.compiler,"finding-review-docket-compiler") or not _syn(r.validator,"finding-review-docket-validator") or len({_identity(x) for x in actors})!=len(actors) or r.full_role_lineage_digest!=lineage or r.complete is not True or r.held is not True or r.pending_human_finding_review is not True or any((r.concluded,r.recommended,r.accepted,r.resolved,r.approved,r.activated,r.deployed)) or r.status!="INDEPENDENT_FINDING_REVIEW_DOCKET_ON_HOLD" or r.digest!=canonical_digest(p):return False
        return True

    def evidence(self):
        ok=self._integrity();complete=len(self._reviews)==20 and self._docket is not None and ok
        projection_set=canonical_digest(tuple(self._reviews[k].review_projection_digest for k in CASE_KEYS)) if complete else None;review_set=canonical_digest(tuple(self._reviews[k].digest for k in CASE_KEYS)) if complete else None
        return {"range":[11501,11900],"control_count":400,"registered_control_count":len(self._controls),"review_count":len(self._reviews),"judgment_preparation_packet_count":sum(bool(x.judgment_packet) for x in self._reviews.values()),"judgment_authority":False,"source_actor_count":len(self._anchor.source_actor_roles) if self._anchor else 0,"source_rereviewer_count":sum(x.reviewer is not None for x in self._anchor.source_rereviews) if self._anchor else 0,"source_finding_actor_count":sum(x.drafter is not None for x in self._anchor.source_findings)*2 if self._anchor else 0,"full_source_lineage_digest":self._anchor.full_source_lineage_digest if self._anchor else None,"review_projection_set_digest":projection_set,"review_set_digest":review_set,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.full_role_lineage_digest if complete else None,"no_finding_marker_count":sum(x.route=="NOT_APPLICABLE_PRESERVED" for x in self._reviews.values()),"rebuttal_finding_pending_count":sum(x.route=="REBUTTAL_OPPORTUNITY_REQUIRED" and x.pending_human_finding_review for x in self._reviews.values()),"correction_finding_pending_count":sum(x.route=="CORRECTION_REQUEST_REQUIRED" and x.pending_human_finding_review for x in self._reviews.values()),"hold_count":len(self._holds),"integrity_valid":ok,"complete_pending_finding_review_evidence":complete,"maximum_state":"INDEPENDENT_FINDING_REVIEW_DOCKET_ON_HOLD" if self._docket else "FINDING_REVIEW_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"external_calls":0,"document_transmissions":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"concluded":False,"recommended":False,"accepted":False,"resolved":False,"approved":False,"activated":False}
