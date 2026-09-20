"""Source-bound option methodology independent challenge #12301-#12700.

The layer reconstructs one methodology card per prior option.  Cards are
preparation material only: they cannot rank, select, recommend, accept,
resolve, approve, activate, deploy, or perform I/O.
"""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_judgment_preparation_stress_test import (
    APPLIED_LESSONS as PRIOR_LESSONS, APPLIED_RULES, CASE_KEYS,
    NEGATIVE as PRIOR_NEGATIVE, SyntheticJudgmentPreparationStressTest,
)

APPLIED_LESSONS = tuple(sorted(PRIOR_LESSONS if "ARL-12301-001" in PRIOR_LESSONS else PRIOR_LESSONS + ("ARL-12301-001",)))
WORKSTREAM_NAMES = (
    "PRIOR_STRESS_DOCKET_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "FULL_STRESS_ARTIFACT_RECONSTRUCTION", "NO_JUDGMENT_MARKER_PRESERVATION",
    "OPTION_SOURCE_IDENTITY_BINDING", "CORRECTION_DIRECTION_BINDING",
    "MULTIPLE_OVERCOMING_METHODS", "ASSUMPTION_TO_FALSIFIER_BINDING",
    "PER_OPTION_STOP_CONDITION", "PER_OPTION_VALIDATION_CRITERIA",
    "PER_OPTION_RESIDUAL_RISK", "ESCALATION_AND_ROLLBACK_BINDING",
    "APPEND_ONLY_CHALLENGE_EVENT", "UNRESOLVED_HUMAN_HOLD_CHAIN",
    "PARTIAL_BATCH_LATEST_CONCURRENCY", "NON_AUTHORITY_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS=tuple((12301+i*25,12325+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS=("input_schema","required_fields","semantic_label","source_type","tenant_scope","role_scope","state_precondition","latest_sequence","source_binding","digest_recalculation","negative_path","missing_input","duplicate_input","replay","conflict","stale_version","concurrency","partial_batch","ordering","append_only","hold_propagation","review_independence","receipt_lineage","operator_gate","non_execution")
NEGATIVE=frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
def _syn(v,k):return isinstance(v,str) and v.startswith(f"synthetic:{k}:")
def _hex(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _identity(v):return v.rsplit(":",1)[-1].casefold()

@dataclass(frozen=True)
class Control:
    control_id:int;workstream:str;aspect:str;requirement_ref:str;fixture_digest:str;expected_result:str;digest:str
@dataclass(frozen=True)
class SourceAnchor:
    service:object;docket_digest:str;stress_set_digest:str;registry_digest:str;manifest_digest:str;lessons:tuple;rules:tuple;sequence:int;latest:bool;digest:str
@dataclass(frozen=True)
class Challenge:
    challenge_id:str;flow:str;answer_kind:str;source_stress_digest:str;challenger:str|None;custodian:str|None;marker:str;parent_digest:str|None;position:int;methodology_cards:tuple;projection_digest:str;held:bool;pending_human_judgment:bool;ranked:bool;selected:bool;concluded:bool;recommended:bool;accepted:bool;resolved:bool;digest:str
@dataclass(frozen=True)
class Docket:
    docket_id:str;source_anchor_digest:str;challenge_set_digest:str;compiler:str;validator:str;role_lineage_digest:str;complete:bool;held:bool;pending_human_judgment:bool;ranked:bool;selected:bool;concluded:bool;recommended:bool;accepted:bool;resolved:bool;approved:bool;activated:bool;deployed:bool;status:str;digest:str

def methodology_cards(stress):
    cards=[]
    for p in stress.option_profiles:
        name,source,packet,direction,effect,risk,cost,reversibility,assumption,falsifier,stop,_feasibility,profile_digest=p
        validation=("validation_criteria",profile_digest,"ASSUMPTION_EVIDENCED","DISCONFIRMING_TEST_PASSED","HUMAN_OWNER_CONFIRMED")
        residual=("residual_risk",profile_digest,risk,"UNASSESSED")
        escalation=("escalation",profile_digest,"ASSUMPTION_UNVERIFIED_OR_TEST_FAILED","HUMAN_REVIEW_AND_STOP")
        rollback=("rollback",profile_digest,"NO_EXECUTION_PRESERVE_SOURCE","FUTURE_CHANGE_REVERT_UNDER_HUMAN_AUTHORITY")
        body=(name,stress.digest,source,packet,profile_digest,direction,("overcoming_method",direction,effect,cost,reversibility),assumption,falsifier,stop,validation,residual,escalation,rollback,("authority","HUMAN_DETERMINATION_REQUIRED"))
        cards.append(body+(canonical_digest(("SOURCE_BOUND_METHODOLOGY_CARD",body)),))
    return tuple(cards)

def projection(source,challenger,custodian,marker,cards):return canonical_digest(("OPTION_METHODOLOGY_CHALLENGE_PROJECTION",source,challenger,custodian,marker,cards))

class SyntheticOptionMethodologyIndependentChallenge:
    def __init__(self):self._controls={};self._source=None;self._challenges={};self._docket=None;self._events=[];self._holds=[];self._lock=RLock()
    def _expected(self,cid):i=cid-12301;return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result);r=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(r):raise GovernanceRejected("valid #12301-#12700 control required")
            old=self._controls.get(cid)
            if old:
                if old==r:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=r;return r
    def anchor(self,service,registry,manifest,lessons,rules,sequence,latest):
        if not isinstance(service,SyntheticJudgmentPreparationStressTest):raise GovernanceRejected("prior stress service required")
        e=service.evidence();d=service._docket;p=dict(service=service,docket_digest=d.digest if d else None,stress_set_digest=d.stress_set_digest if d else None,registry_digest=registry,manifest_digest=manifest,lessons=tuple(lessons),rules=tuple(rules),sequence=sequence,latest=latest);r=SourceAnchor(**p,digest=canonical_digest(tuple(v for k,v in p.items() if k!="service")+(e.get("complete_role_lineage_digest"),)))
        with self._lock:
            if not (self._registry_valid() and e["complete_counterfactual_stress_evidence"] and e["integrity_valid"] and e["judgment_authority"] is False and d and _hex(registry) and _hex(manifest) and tuple(lessons)==APPLIED_LESSONS and tuple(rules)==APPLIED_RULES and isinstance(sequence,int) and not isinstance(sequence,bool) and sequence>0 and latest is True):raise GovernanceRejected("complete latest non-authoritative source required")
            if self._source:
                if self._source==r:return r
                raise GovernanceRejected("source conflict")
            self._source=r;self._event("PRIOR_STRESS_DOCKET_ANCHORED",r.digest);return r
    def add_challenge(self,challenge_id,flow,kind,challenger=None,custodian=None):
        with self._lock:
            key=(flow,kind)
            if not self._source or key not in CASE_KEYS:raise GovernanceRejected("anchored source required")
            i=CASE_KEYS.index(key);source=self._source.service._tests[key];previous=None if i==0 else self._challenges.get(CASE_KEYS[i-1])
            if i and previous is None:raise GovernanceRejected("immediate prior challenge required")
            if not source.option_profiles:
                if challenger is not None or custodian is not None:raise GovernanceRejected("N/A forbids actors")
                marker="NO_OPTION_METHODOLOGY_REQUIRED";cards=()
            else:
                if not _syn(challenger,"methodology-challenger") or not _syn(custodian,"methodology-custodian"):raise GovernanceRejected("independent challenge actors required")
                occupied=self._prior_actors()+tuple(y for x in self._challenges.values() for y in (x.challenger,x.custodian) if y)
                if len({_identity(x) for x in occupied+(challenger,custodian)})!=len(occupied)+2:raise GovernanceRejected("actor collision")
                marker="OPTION_METHODOLOGY_PENDING_HUMAN_JUDGMENT";cards=methodology_cards(source)
            parent=None if previous is None else previous.digest;proj=projection(source.digest,challenger,custodian,marker,cards);values=(challenge_id,flow,kind,source.digest,challenger,custodian,marker,parent,i+1,cards,proj,True,bool(cards),False,False,False,False,False,False);r=Challenge(*values,canonical_digest(("OPTION_METHODOLOGY_CHALLENGE",values)))
            if not self._challenge_valid(r,key):raise GovernanceRejected("valid methodology challenge required")
            old=self._challenges.get(key)
            if old:
                if old==r:return old
                raise GovernanceRejected("challenge conflict")
            self._challenges[key]=r;self._event("OPTION_METHODOLOGY_CHALLENGE_RECORDED",r.digest)
            if r.pending_human_judgment:self._hold("HUMAN_METHODOLOGY_JUDGMENT_REQUIRED",r.digest)
            return r
    def finalize(self,docket_id,compiler,validator):
        with self._lock:
            if self._docket or tuple(self._challenges)!=CASE_KEYS or not self._integrity():raise GovernanceRejected("complete intact batch required")
            actors=self._prior_actors()+tuple(y for x in self._challenges.values() for y in (x.challenger,x.custodian) if y)+(compiler,validator)
            if not _syn(compiler,"methodology-docket-compiler") or not _syn(validator,"methodology-docket-validator") or len({_identity(x) for x in actors})!=len(actors):raise GovernanceRejected("independent final actors required")
            cset=canonical_digest(tuple(self._challenges[k].digest for k in CASE_KEYS));lineage=canonical_digest(("COMPLETE_OPTION_METHODOLOGY_ROLE_LINEAGE",self._source.service._docket.full_role_lineage_digest,actors));p=dict(docket_id=docket_id,source_anchor_digest=self._source.digest,challenge_set_digest=cset,compiler=compiler,validator=validator,role_lineage_digest=lineage,complete=True,held=True,pending_human_judgment=True,ranked=False,selected=False,concluded=False,recommended=False,accepted=False,resolved=False,approved=False,activated=False,deployed=False,status="OPTION_METHODOLOGY_DOCKET_ON_HOLD");self._docket=Docket(**p,digest=canonical_digest(p));self._event("OPTION_METHODOLOGY_DOCKET_HELD",self._docket.digest);return self._docket
    def _control_valid(self,r):
        p={k:v for k,v in r.__dict__.items() if k!="digest"};return isinstance(r.control_id,int) and not isinstance(r.control_id,bool) and 12301<=r.control_id<=12700 and self._expected(r.control_id)==(r.workstream,r.aspect) and r.requirement_ref==f"synthetic:methodology-challenge-requirement:{(r.control_id-12301)//25:02}" and _hex(r.fixture_digest) and r.expected_result==("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest==canonical_digest(p)
    def _registry_valid(self):return set(self._controls)==set(range(12301,12701)) and all(self._control_valid(x) for x in self._controls.values())
    def _source_valid(self):
        if not self._source:return False
        s=self._source;e=s.service.evidence();d=s.service._docket;p=tuple(v for k,v in s.__dict__.items() if k not in ("service","digest"))+(e.get("complete_role_lineage_digest"),)
        return e["integrity_valid"] and e["complete_counterfactual_stress_evidence"] and e["judgment_authority"] is False and d and s.docket_digest==d.digest and s.stress_set_digest==d.stress_set_digest and _hex(s.registry_digest) and _hex(s.manifest_digest) and s.lessons==APPLIED_LESSONS and s.rules==APPLIED_RULES and isinstance(s.sequence,int) and not isinstance(s.sequence,bool) and s.sequence>0 and s.latest is True and s.digest==canonical_digest(p)
    def _prior_actors(self):
        svc=self._source.service;return svc._prior_actors()+tuple(y for x in svc._tests.values() for y in (x.preparer,x.challenger) if y)+(svc._docket.compiler,svc._docket.validator)
    def _challenge_valid(self,r,key):
        i=CASE_KEYS.index(key);source=self._source.service._tests[key];previous=None if i==0 else self._challenges.get(CASE_KEYS[i-1]);parent=None if previous is None else previous.digest;cards=methodology_cards(source) if source.option_profiles else ();marker="OPTION_METHODOLOGY_PENDING_HUMAN_JUDGMENT" if cards else "NO_OPTION_METHODOLOGY_REQUIRED";state=(_syn(r.challenger,"methodology-challenger") and _syn(r.custodian,"methodology-custodian")) if cards else (r.challenger is None and r.custodian is None);proj=projection(source.digest,r.challenger,r.custodian,marker,cards);values=(r.challenge_id,r.flow,r.answer_kind,source.digest,r.challenger,r.custodian,marker,parent,i+1,cards,proj,True,bool(cards),False,False,False,False,False,False);ids=[x.challenge_id for k,x in self._challenges.items() if k!=key];return _syn(r.challenge_id,"option-methodology-challenge") and r.challenge_id not in ids and (r.flow,r.answer_kind)==key and state and r.parent_digest==parent and r.position==i+1 and r.methodology_cards==cards and r.projection_digest==proj and r.held is True and r.pending_human_judgment is bool(cards) and not any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved)) and r.digest==canonical_digest(("OPTION_METHODOLOGY_CHALLENGE",values))
    def _event(self,action,artifact):prev=self._events[-1]["digest"] if self._events else None;p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev);self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):prev=self._holds[-1]["digest"] if self._holds else None;p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev);self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(rows,kind):
        prev=None
        for i,r in enumerate(rows,1):
            keys=("sequence","action","artifact_digest","previous_digest") if kind=="event" else ("sequence","reason","attachment_digest","previous_digest");p={k:r.get(k) for k in keys}
            if r!={**p,"digest":canonical_digest(p)} or r["sequence"]!=i or r["previous_digest"]!=prev:return False
            prev=r["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._source_valid() or not self._chain(self._events,"event") or not self._chain(self._holds,"hold") or any(not self._challenge_valid(v,k) for k,v in self._challenges.items()):return False
        events=[("PRIOR_STRESS_DOCKET_ANCHORED",self._source.digest)]+[("OPTION_METHODOLOGY_CHALLENGE_RECORDED",x.digest) for x in self._challenges.values()];holds=[("HUMAN_METHODOLOGY_JUDGMENT_REQUIRED",x.digest) for x in self._challenges.values() if x.pending_human_judgment]
        if self._docket:events.append(("OPTION_METHODOLOGY_DOCKET_HELD",self._docket.digest))
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if self._docket:
            r=self._docket;p={k:v for k,v in r.__dict__.items() if k!="digest"};actors=self._prior_actors()+tuple(y for x in self._challenges.values() for y in (x.challenger,x.custodian) if y)+(r.compiler,r.validator);expected=canonical_digest(("COMPLETE_OPTION_METHODOLOGY_ROLE_LINEAGE",self._source.service._docket.full_role_lineage_digest,actors));return _syn(r.docket_id,"option-methodology-docket") and _syn(r.compiler,"methodology-docket-compiler") and _syn(r.validator,"methodology-docket-validator") and r.complete is True and r.held is True and r.pending_human_judgment is True and r.status=="OPTION_METHODOLOGY_DOCKET_ON_HOLD" and r.digest==canonical_digest(p) and r.source_anchor_digest==self._source.digest and r.challenge_set_digest==canonical_digest(tuple(self._challenges[k].digest for k in CASE_KEYS)) and r.role_lineage_digest==expected and len({_identity(x) for x in actors})==len(actors) and not any((r.ranked,r.selected,r.concluded,r.recommended,r.accepted,r.resolved,r.approved,r.activated,r.deployed))
        return True
    def evidence(self):
        ok=self._integrity();complete=ok and self._docket is not None and len(self._challenges)==20 and len(self._holds)==16;zero={k:0 for k in ("external_calls","document_transmissions","external_pg_calls","card_network_calls","payment_approvals","cancellations","refunds","settlements","transfers","ledger_writes","credential_reads","deployments")};return {"range":[12301,12700],"control_count":400,"registered_control_count":len(self._controls),"challenge_count":len(self._challenges),"methodology_card_count":sum(len(x.methodology_cards) for x in self._challenges.values()),"no_judgment_marker_count":sum(not x.methodology_cards for x in self._challenges.values()),"human_judgment_hold_count":len(self._holds),"source_anchor_digest":self._source.digest if self._source else None,"challenge_set_digest":self._docket.challenge_set_digest if complete else None,"final_docket_digest":self._docket.digest if complete else None,"complete_role_lineage_digest":self._docket.role_lineage_digest if complete else None,"integrity_valid":ok,"complete_option_methodology_challenge_evidence":complete,"maximum_state":"OPTION_METHODOLOGY_DOCKET_ON_HOLD" if self._docket else "CHALLENGE_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"judgment_authority":False,"ranked":False,"selected":False,"concluded":False,"recommended":False,"accepted":False,"resolved":False,"approved":False,"activated":False,**zero}
