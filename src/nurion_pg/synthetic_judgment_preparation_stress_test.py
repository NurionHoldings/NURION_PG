"""Counterfactual judgment-preparation stress tests #11901-#12300.

This in-memory layer turns each non-authoritative finding-review packet into
two source-bound, falsifiable option profiles.  It cannot rank, select,
conclude, recommend, accept, resolve, approve, activate, deploy, or perform I/O.
"""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_finding_independent_review import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, CASE_KEYS,
    NEGATIVE as PRIOR_NEGATIVE, SyntheticFindingIndependentReview,
)

APPLIED_LESSONS = PRIOR_LESSONS
WORKSTREAM_NAMES = (
    "PRIOR_JUDGMENT_DOCKET_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "FULL_PRIOR_ARTIFACT_PRESERVATION", "NO_FINDING_MARKER_PRESERVATION",
    "SOURCE_BOUND_OPTION_PROFILES", "COUNTERFACTUAL_ASSUMPTION_REGISTER",
    "DISCONFIRMING_TEST_DESIGN", "EFFECT_RISK_COST_REVERSIBILITY",
    "CORRECTION_DIRECTION_CONSTRAINTS", "MULTIPLE_OVERCOMING_PATHS",
    "VALIDATION_AND_STOP_CRITERIA", "RESIDUAL_RISK_ESCALATION",
    "APPEND_ONLY_STRESS_EVENT", "UNRESOLVED_HUMAN_HOLD_CHAIN",
    "PARTIAL_BATCH_FAIL_CLOSED", "NON_JUDGMENT_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((11901+i*25, 11925+i*25, n) for i,n in enumerate(WORKSTREAM_NAMES))
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
class SourceBundle:
    anchor:object; reviews:tuple; docket:object; source_bundle_digest:str
    lesson_registry_digest:str; remediation_manifest_digest:str
    applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]
    source_sequence:int; is_latest:bool; digest:str

@dataclass(frozen=True)
class StressTest:
    stress_id:str; flow:str; answer_kind:str; source_review_digest:str
    source_packet_digest:str|None; preparer:str|None; challenger:str|None
    marker:str; parent_stress_digest:str|None; position:int; option_profiles:tuple
    assumption_register:tuple; validation_criteria:tuple; residual_risks:tuple
    escalation_conditions:tuple; rollback_conditions:tuple; stress_projection_digest:str
    held:bool; pending_human_judgment:bool; ranked:bool; selected:bool
    concluded:bool; recommended:bool; accepted:bool; resolved:bool; digest:str

@dataclass(frozen=True)
class Docket:
    docket_id:str; source_bundle_digest:str; stress_set_digest:str; compiler:str; validator:str
    full_role_lineage_digest:str; complete:bool; held:bool; pending_human_judgment:bool
    ranked:bool; selected:bool; concluded:bool; recommended:bool; accepted:bool
    resolved:bool; approved:bool; activated:bool; deployed:bool; status:str; digest:str

def option_profiles(source_digest, packet_digest):
    def profile(name, direction, effect, risk, cost, reversibility, falsifier, stop):
        body=(name,source_digest,packet_digest,direction,effect,risk,cost,reversibility,
              ("assumption","UNVERIFIED",source_digest),
              ("disconfirming_test",falsifier,"REQUIRED"),
              ("stop_condition",stop),("feasibility","HUMAN_DETERMINATION_REQUIRED"))
        return body+(canonical_digest(("SOURCE_BOUND_OPTION_PROFILE",body)),)
    return (
        profile("CORRECT_AND_REVALIDATE","CORRECTION_DRAFT_ONLY","EXPECTED_BUT_UNVERIFIED",
                "REGRESSION_OR_SCOPE_ERROR","UNKNOWN","REVERSIBLE_BEFORE_HUMAN_APPROVAL",
                "NEGATIVE_AND_REGRESSION_TESTS","ANY_TEST_FAILURE"),
        profile("PRESERVE_AND_ESCALATE","PRESERVE_SOURCE_AND_HOLD","NO_AUTOMATIC_CHANGE",
                "DELAY_OR_UNRESOLVED_HARM","UNKNOWN","FULLY_REVERSIBLE",
                "INDEPENDENT_EVIDENCE_CHALLENGE","HUMAN_SCOPE_REJECTION"),
    )

def stress_projection(source,packet,preparer,challenger,marker,profiles,assumptions,criteria,risks,escalation,rollback):
    return canonical_digest(("JUDGMENT_PREPARATION_STRESS_PROJECTION",source,packet,preparer,challenger,marker,profiles,assumptions,criteria,risks,escalation,rollback))

def source_bundle_digest(anchor,reviews,docket):
    return canonical_digest((anchor.digest,tuple(x.digest for x in reviews),docket.digest if docket else None))

def source_record_digest(anchor,reviews,docket,bundle_digest,registry_digest,manifest_digest,lessons,rules,sequence,is_latest):
    return canonical_digest((anchor.digest,tuple(x.digest for x in reviews),docket.digest if docket else None,bundle_digest,registry_digest,manifest_digest,tuple(lessons),tuple(rules),sequence,is_latest))

class SyntheticJudgmentPreparationStressTest:
    def __init__(self):
        self._controls={};self._source=None;self._tests={};self._docket=None
        self._events=[];self._holds=[];self._lock=RLock()

    def _expected(self,cid):
        i=cid-11901;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]

    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(row):raise GovernanceRejected("valid #11901-#12300 control required")
            old=self._controls.get(cid)
            if old:
                if old==row:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=row;return row

    def anchor(self,source_service,registry_digest,manifest_digest,lessons,rules,sequence,is_latest):
        if not isinstance(source_service,SyntheticFindingIndependentReview):raise GovernanceRejected("prior service required")
        evidence=source_service.evidence();anchor=source_service._anchor;reviews=tuple(source_service._reviews[k] for k in CASE_KEYS);docket=source_service._docket
        bundle_digest=source_bundle_digest(anchor,reviews,docket)
        p=dict(anchor=anchor,reviews=reviews,docket=docket,source_bundle_digest=bundle_digest,
               lesson_registry_digest=registry_digest,remediation_manifest_digest=manifest_digest,
               applied_lesson_ids=tuple(lessons),applied_rule_ids=tuple(rules),source_sequence=sequence,is_latest=is_latest)
        row=SourceBundle(**p,digest=source_record_digest(anchor,reviews,docket,bundle_digest,registry_digest,manifest_digest,lessons,rules,sequence,is_latest))
        with self._lock:
            if not (self._registry_valid() and evidence["complete_pending_finding_review_evidence"] and evidence["integrity_valid"] and evidence["judgment_authority"] is False and len(reviews)==20 and docket and _hex(registry_digest) and _hex(manifest_digest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and is_latest is True):raise GovernanceRejected("complete latest non-authoritative source required")
            if self._source:
                if self._source==row:return row
                raise GovernanceRejected("source conflict")
            self._source=row;self._event("PRIOR_JUDGMENT_DOCKET_ANCHORED",row.digest);return row

    def add_stress_test(self,stress_id,flow,kind,preparer=None,challenger=None):
        with self._lock:
            key=(flow,kind)
            if not self._source or key not in CASE_KEYS:raise GovernanceRejected("anchored source required")
            i=CASE_KEYS.index(key);source=self._source.reviews[i];previous=None if i==0 else self._tests.get(CASE_KEYS[i-1])
            if i and previous is None:raise GovernanceRejected("immediate prior stress test required")
            if not source.judgment_packet:
                if preparer is not None or challenger is not None:raise GovernanceRejected("N/A forbids actors")
                marker="NO_JUDGMENT_PREPARATION_REQUIRED";profiles=assumptions=criteria=risks=escalation=rollback=()
            else:
                if not _syn(preparer,"judgment-stress-preparer") or not _syn(challenger,"judgment-stress-challenger"):raise GovernanceRejected("separate stress actors required")
                occupied=self._prior_actors()+tuple(y for x in self._tests.values() for y in (x.preparer,x.challenger) if y)
                if len({_identity(x) for x in occupied+(preparer,challenger)})!=len(occupied)+2:raise GovernanceRejected("stress actor collision")
                marker="COUNTERFACTUAL_STRESS_TEST_PENDING_HUMAN_JUDGMENT";profiles=option_profiles(source.digest,source.judgment_packet_digest)
                assumptions=tuple((p[0],p[8],p[-1]) for p in profiles)
                criteria=(("all_assumptions_evidenced",False),("all_disconfirming_tests_pass",False),("human_scope_and_owner_confirmed",False))
                risks=(("EVIDENCE_GAP","PRESENT"),("OPTION_INTERACTION","UNASSESSED"),("IMPLEMENTATION_SIDE_EFFECT","UNASSESSED"))
                escalation=(("ANY_UNVERIFIED_ASSUMPTION","HUMAN_REVIEW"),("ANY_TEST_FAILURE","PRESERVE_AND_ESCALATE"),("CRITICAL_RISK","STOP"))
                rollback=(("NO_EXECUTION_OCCURRED","PRESERVE_SOURCE"),("FUTURE_CHANGE_FAILS","REVERT_UNDER_HUMAN_AUTHORITY"))
            parent=None if previous is None else previous.digest;projection=stress_projection(source.digest,source.judgment_packet_digest,preparer,challenger,marker,profiles,assumptions,criteria,risks,escalation,rollback)
            values=(stress_id,flow,kind,source.digest,source.judgment_packet_digest,preparer,challenger,marker,parent,i+1,profiles,assumptions,criteria,risks,escalation,rollback,projection,True,bool(source.judgment_packet),False,False,False,False,False,False)
            row=StressTest(*values,canonical_digest(("JUDGMENT_PREPARATION_STRESS_TEST",values)))
            if not self._test_valid(row,key):raise GovernanceRejected("valid stress test required")
            old=self._tests.get(key)
            if old:
                if old==row:return old
                raise GovernanceRejected("stress test conflict")
            self._tests[key]=row;self._event("JUDGMENT_PREPARATION_STRESS_TEST_RECORDED",row.digest)
            if row.pending_human_judgment:self._hold("HUMAN_JUDGMENT_REQUIRED",row.digest)
            return row

    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._tests)!=CASE_KEYS or not self._integrity():raise GovernanceRejected("complete intact batch required")
            actors=self._prior_actors()+tuple(y for x in self._tests.values() for y in (x.preparer,x.challenger) if y)+(compiler,validator)
            if not _syn(compiler,"judgment-stress-docket-compiler") or not _syn(validator,"judgment-stress-docket-validator") or len({_identity(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            stress_set=canonical_digest(tuple(self._tests[k].digest for k in CASE_KEYS));lineage=canonical_digest(("COMPLETE_JUDGMENT_STRESS_ROLE_LINEAGE",self._source.docket.full_role_lineage_digest,actors))
            p=dict(docket_id=docket_id,source_bundle_digest=self._source.digest,stress_set_digest=stress_set,compiler=compiler,validator=validator,full_role_lineage_digest=lineage,complete=True,held=True,pending_human_judgment=True,ranked=False,selected=False,concluded=False,recommended=False,accepted=False,resolved=False,approved=False,activated=False,deployed=False,status="COUNTERFACTUAL_STRESS_DOCKET_ON_HOLD")
            self._docket=Docket(**p,digest=canonical_digest(p));self._event("COUNTERFACTUAL_STRESS_DOCKET_HELD",self._docket.digest);return self._docket

    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"}
        return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 11901<=r.control_id<=12300 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:judgment-stress-requirement:{(r.control_id-11901)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(11901,12301)) and all(self._control_valid(x) for x in self._controls.values())
    def _prior_actors(self):
        a=self._source.anchor;return a.source_actor_roles+(a.source_submission_compiler,a.source_submission_validator)+tuple(x.reviewer for x in a.source_rereviews if x.reviewer)+(a.source_rereview_compiler,a.source_rereview_validator)+tuple(y for x in a.source_findings for y in (x.drafter,x.reviewer) if y)+(a.source_finding_compiler,a.source_finding_validator)+tuple(y for x in self._source.reviews for y in (x.reviewer,x.custodian) if y)+(self._source.docket.compiler,self._source.docket.validator)
    def _source_valid(self):
        """Reconstruct and validate the complete embedded prior ledger."""
        b=self._source
        if not b or len(b.reviews)!=len(CASE_KEYS) or tuple((x.flow,x.answer_kind) for x in b.reviews)!=CASE_KEYS or b.docket is None:return False
        bundle=source_bundle_digest(b.anchor,b.reviews,b.docket)
        record=source_record_digest(b.anchor,b.reviews,b.docket,bundle,b.lesson_registry_digest,b.remediation_manifest_digest,b.applied_lesson_ids,b.applied_rule_ids,b.source_sequence,b.is_latest)
        if b.source_bundle_digest!=bundle or b.digest!=record or b.applied_lesson_ids!=APPLIED_LESSONS or b.applied_rule_ids!=APPLIED_RULES or not _hex(b.lesson_registry_digest) or not _hex(b.remediation_manifest_digest) or not isinstance(b.source_sequence,int) or isinstance(b.source_sequence,bool) or b.source_sequence<=0 or b.is_latest is not True:return False
        checker=SyntheticFindingIndependentReview()
        for cid in range(11501,11901):
            w,a=checker._expected(cid);checker.add_control(cid,w,a,f"synthetic:finding-review-requirement:{(cid-11501)//25:02}",canonical_digest(("EMBEDDED_SOURCE_CONTROL",cid)),"EXPECTED_REJECTION" if a in PRIOR_NEGATIVE else "PASS")
        checker._anchor=b.anchor;checker._reviews={k:v for k,v in zip(CASE_KEYS,b.reviews)};checker._docket=b.docket
        checker._event("FINDING_DOCKET_ANCHORED",b.anchor.digest)
        for row in b.reviews:
            checker._event("INDEPENDENT_FINDING_REVIEW_RECORDED",row.digest)
            if row.pending_human_finding_review:checker._hold("HUMAN_FINDING_REVIEW_REQUIRED",row.digest)
        checker._event("INDEPENDENT_FINDING_REVIEW_DOCKET_HELD",b.docket.digest)
        evidence=checker.evidence()
        return evidence["integrity_valid"] and evidence["complete_pending_finding_review_evidence"] and evidence["judgment_authority"] is False
    def _test_valid(self,r,key):
        i=CASE_KEYS.index(key);source=self._source.reviews[i];previous=None if i==0 else self._tests.get(CASE_KEYS[i-1]);parent=None if previous is None else previous.digest
        if source.judgment_packet:
            profiles=option_profiles(source.digest,source.judgment_packet_digest);assumptions=tuple((p[0],p[8],p[-1]) for p in profiles);criteria=(("all_assumptions_evidenced",False),("all_disconfirming_tests_pass",False),("human_scope_and_owner_confirmed",False));risks=(("EVIDENCE_GAP","PRESENT"),("OPTION_INTERACTION","UNASSESSED"),("IMPLEMENTATION_SIDE_EFFECT","UNASSESSED"));escalation=(("ANY_UNVERIFIED_ASSUMPTION","HUMAN_REVIEW"),("ANY_TEST_FAILURE","PRESERVE_AND_ESCALATE"),("CRITICAL_RISK","STOP"));rollback=(("NO_EXECUTION_OCCURRED","PRESERVE_SOURCE"),("FUTURE_CHANGE_FAILS","REVERT_UNDER_HUMAN_AUTHORITY"));state=_syn(r.preparer,"judgment-stress-preparer") and _syn(r.challenger,"judgment-stress-challenger") and r.marker=="COUNTERFACTUAL_STRESS_TEST_PENDING_HUMAN_JUDGMENT" and r.pending_human_judgment is True and len(profiles)>=2 and len({p[-1] for p in profiles})==len(profiles)
        else:profiles=assumptions=criteria=risks=escalation=rollback=();state=r.preparer is None and r.challenger is None and r.marker=="NO_JUDGMENT_PREPARATION_REQUIRED" and r.pending_human_judgment is False
        projection=stress_projection(source.digest,source.judgment_packet_digest,r.preparer,r.challenger,r.marker,profiles,assumptions,criteria,risks,escalation,rollback);values=(r.stress_id,r.flow,r.answer_kind,source.digest,source.judgment_packet_digest,r.preparer,r.challenger,r.marker,parent,i+1,profiles,assumptions,criteria,risks,escalation,rollback,projection,True,bool(source.judgment_packet),False,False,False,False,False,False)
        ids=[x.stress_id for k,x in self._tests.items() if k!=key]
        return _syn(r.stress_id,"judgment-preparation-stress-test") and r.stress_id not in ids and (r.flow,r.answer_kind)==key and state and r.parent_stress_digest==parent and r.position==i+1 and r.option_profiles==profiles and r.assumption_register==assumptions and r.validation_criteria==criteria and r.residual_risks==risks and r.escalation_conditions==escalation and r.rollback_conditions==rollback and r.stress_projection_digest==projection and r.held is True and not any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved)) and r.digest==canonical_digest(("JUDGMENT_PREPARATION_STRESS_TEST",values))
    def _event(self,action,artifact):
        prev=self._events[-1]["digest"] if self._events else None;p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev);self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):
        prev=self._holds[-1]["digest"] if self._holds else None;p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev);self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(rows,kind):
        prev=None
        for i,row in enumerate(rows,1):
            keys=("sequence","action","artifact_digest","previous_digest") if kind=="event" else ("sequence","reason","attachment_digest","previous_digest");p={k:row.get(k) for k in keys}
            if row!={**p,"digest":canonical_digest(p)} or row["sequence"]!=i or row["previous_digest"]!=prev:return False
            prev=row["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._source_valid() or not self._chain(self._events,"event") or not self._chain(self._holds,"hold") or any(not self._test_valid(v,k) for k,v in self._tests.items()):return False
        events=[("PRIOR_JUDGMENT_DOCKET_ANCHORED",self._source.digest)]+[("JUDGMENT_PREPARATION_STRESS_TEST_RECORDED",x.digest) for x in self._tests.values()]
        if self._docket:events.append(("COUNTERFACTUAL_STRESS_DOCKET_HELD",self._docket.digest))
        holds=[("HUMAN_JUDGMENT_REQUIRED",x.digest) for x in self._tests.values() if x.pending_human_judgment]
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if self._docket:
            r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._prior_actors()+tuple(y for x in self._tests.values() for y in (x.preparer,x.challenger) if y)+(r.compiler,r.validator);lineage=canonical_digest(("COMPLETE_JUDGMENT_STRESS_ROLE_LINEAGE",self._source.docket.full_role_lineage_digest,actors))
            if not _syn(r.docket_id,"judgment-stress-docket") or r.source_bundle_digest!=self._source.digest or r.stress_set_digest!=canonical_digest(tuple(self._tests[k].digest for k in CASE_KEYS)) or not _syn(r.compiler,"judgment-stress-docket-compiler") or not _syn(r.validator,"judgment-stress-docket-validator") or len({_identity(x) for x in actors})!=len(actors) or r.full_role_lineage_digest!=lineage or not r.complete or not r.held or not r.pending_human_judgment or any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved,r.approved,r.activated,r.deployed)) or r.status!="COUNTERFACTUAL_STRESS_DOCKET_ON_HOLD" or r.digest!=canonical_digest(p):return False
        return True
    def evidence(self):
        ok=self._integrity();complete=len(self._tests)==20 and self._docket is not None and ok
        zero={k:0 for k in ("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")}
        return {"range":[11901,12300],"control_count":400,"registered_control_count":len(self._controls),"stress_test_count":len(self._tests),"option_profile_count":sum(len(x.option_profiles) for x in self._tests.values()),"no_judgment_marker_count":sum(not x.option_profiles for x in self._tests.values()),"human_judgment_hold_count":len(self._holds),"source_bundle_digest":self._source.source_bundle_digest if self._source else None,"stress_projection_set_digest":canonical_digest(tuple(self._tests[k].stress_projection_digest for k in CASE_KEYS)) if complete else None,"stress_set_digest":self._docket.stress_set_digest if complete else None,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.full_role_lineage_digest if complete else None,"integrity_valid":ok,"complete_counterfactual_stress_evidence":complete,"maximum_state":"COUNTERFACTUAL_STRESS_DOCKET_ON_HOLD" if self._docket else "STRESS_TEST_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"ranked":False,"selected":False,"concluded":False,"recommended":False,"accepted":False,"resolved":False,"approved":False,"activated":False,**zero}
