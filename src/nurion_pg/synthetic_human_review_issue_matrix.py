"""Synthetic/in-memory human-review issue matrix hold controls #8701-#9100."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "SUBMISSION_DOCKET_SOURCE_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "TENANT_NURION_ISSUE_EXTRACTION", "NURION_UPSTREAM_ISSUE_EXTRACTION",
    "ACTUAL_VALUE_COMPARISON", "PROPOSAL_COUNTERARGUMENT_EVIDENCE_LINEAGE",
    "ISSUE_SEVERITY_NEUTRAL_CLASSIFICATION", "FOUR_DIRECTION_ROUTE_BINDING",
    "ISSUE_MATRIX_ORDERING", "SOURCE_ROLE_PROJECTION", "MATRIX_COMPILER_SEPARATION",
    "APPEND_ONLY_MATRIX_EVENT", "HUMAN_REVIEW_HOLD_CHAIN", "PARTIAL_BATCH_FAIL_CLOSED",
    "INDEPENDENT_MATRIX_VALIDATION", "NON_CONCLUSION_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((8701+i*25, 8725+i*25, name) for i, name in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type", "tenant_scope",
    "role_scope", "state_precondition", "latest_sequence", "source_binding", "digest_recalculation",
    "negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version",
    "concurrency", "partial_batch", "ordering", "append_only", "hold_propagation",
    "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path","missing_input","duplicate_input","replay","conflict","stale_version","partial_batch"})
FLOWS = ("tenant_to_nurion","nurion_to_upstream","upstream_to_nurion","nurion_to_tenant")
FLOW_PARTIES = {"tenant_to_nurion":("TENANT_AGENCY","NURION_PG"),"nurion_to_upstream":("NURION_PG","UPSTREAM_PG"),"upstream_to_nurion":("UPSTREAM_PG","NURION_PG"),"nurion_to_tenant":("NURION_PG","TENANT_AGENCY")}
ANSWER_KINDS = ("ASSUMPTION_RESPONSE","RESIDUAL_RISK_RESPONSE","ADDITIONAL_EVIDENCE","MEANING_CLARIFICATION","SAFE_BOUNDARY_ACKNOWLEDGEMENT")
OUTCOMES = ("CONSISTENT","CLAIM_CONFLICT","MANIFEST_CONFLICT","RECEIPT_CONFLICT","VERSION_CONFLICT")
APPLIED_LESSONS = ("ARL-3901-001","ARL-4301-001","ARL-4301-002","ARL-4301-003","ARL-4701-001","ARL-5101-001","ARL-5501-001","ARL-5901-001","ARL-6301-001","ARL-6701-001","ARL-7101-001","ARL-7501-001","ARL-7901-001","ARL-8301-001","ARL-8701-001")
APPLIED_RULES = tuple(f"ARP-{i:02}" for i in range(1,9))

def _syn(value, kind): return isinstance(value,str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)
def _identity(value): return value.rsplit(":",1)[-1].casefold()
def actual_outcome(claim_a,claim_b,manifest_a,manifest_b,receipt_a,receipt_b,version_a,version_b):
    if claim_a != claim_b: return "CLAIM_CONFLICT"
    if manifest_a != manifest_b: return "MANIFEST_CONFLICT"
    if receipt_a != receipt_b: return "RECEIPT_CONFLICT"
    if version_a != version_b: return "VERSION_CONFLICT"
    return "CONSISTENT"
def bundle_projection_digest(flow,answer_kind,claim_pair,manifest_pair,receipt_pair,version_pair):
    return canonical_digest(("SOURCE_SUBMISSION_BUNDLE_PROJECTION",flow,answer_kind,claim_pair,manifest_pair,receipt_pair,version_pair))

@dataclass(frozen=True)
class Control:
    control_id:int; workstream:str; aspect:str; requirement_ref:str; fixture_digest:str; expected_result:str; digest:str
@dataclass(frozen=True)
class DocketAnchor:
    anchor_id:str; source_docket_digest:str; bundle_set_digest:str; lesson_registry_digest:str; remediation_manifest_digest:str
    applied_lesson_ids:tuple[str,...]; applied_rule_ids:tuple[str,...]; source_bundle_digests:tuple[str,...]
    claim_pairs:tuple[tuple[str,str],...]; manifest_pairs:tuple[tuple[str,str],...]; receipt_pairs:tuple[tuple[str,str],...]
    version_pairs:tuple[tuple[int,int],...]; source_reviewers:tuple[str,...]; source_compilers:tuple[str,...]
    source_chair:str; source_validator:str; source_lineage_digest:str; source_sequence:int; is_latest:bool; status:str; digest:str
@dataclass(frozen=True)
class Issue:
    issue_id:str; flow:str; answer_kind:str; outcome:str; source_bundle_digest:str; claim_pair:tuple[str,str]
    manifest_pair:tuple[str,str]; receipt_pair:tuple[str,str]; version_pair:tuple[int,int]; parent_issue_digest:str|None
    position:int; neutral_label:str; held:bool; concluded:bool; recommended:bool; accepted:bool; digest:str
@dataclass(frozen=True)
class IssueMatrix:
    matrix_id:str; anchor_digest:str; ordered_issue_set_digest:str; compiler:str; validator:str
    source_reviewers:tuple[str,...]; source_compilers:tuple[str,...]; source_chair:str; source_validator:str
    source_lineage_digest:str; complete:bool; held:bool; concluded:bool; recommended:bool; accepted:bool
    approved:bool; activated:bool; deployed:bool; status:str; digest:str

class SyntheticHumanReviewIssueMatrix:
    """Builds a neutral issue matrix for people; it cannot decide or recommend."""
    def __init__(self):
        self._controls={}; self._anchor=None; self._issues={}; self._matrix=None; self._events=[]; self._holds=[]; self._lock=RLock()
    def _expected(self,cid):
        i=cid-8701; return WORKSTREAM_NAMES[i//25],CONTROL_ASPECTS[i%25]
    def add_control(self,cid,workstream,aspect,requirement_ref,fixture_digest,expected_result):
        p=dict(control_id=cid,workstream=workstream,aspect=aspect,requirement_ref=requirement_ref,fixture_digest=fixture_digest,expected_result=expected_result); row=Control(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(row): raise GovernanceRejected("valid #8701-#9100 control required")
            old=self._controls.get(cid)
            if old:
                if old==row:return old
                raise GovernanceRejected("control conflict")
            self._controls[cid]=row; return row
    def anchor_docket(self,anchor_id,source_docket_digest,bundle_set_digest,lesson_registry_digest,remediation_manifest_digest,applied_lesson_ids,applied_rule_ids,source_bundle_digests,claim_pairs,manifest_pairs,receipt_pairs,version_pairs,source_reviewers,source_compilers,source_chair,source_validator,source_sequence,is_latest):
        bundles=tuple(source_bundle_digests); claims=tuple(claim_pairs); manifests=tuple(manifest_pairs); receipts=tuple(receipt_pairs); versions=tuple(version_pairs); reviewers=tuple(source_reviewers); compilers=tuple(source_compilers)
        lineage=canonical_digest(("SUBMISSION_HOLD_DOCKET_FULL_LINEAGE",source_docket_digest,bundle_set_digest,bundles,claims,manifests,receipts,versions,reviewers,compilers,source_chair,source_validator))
        p=dict(anchor_id=anchor_id,source_docket_digest=source_docket_digest,bundle_set_digest=bundle_set_digest,lesson_registry_digest=lesson_registry_digest,remediation_manifest_digest=remediation_manifest_digest,applied_lesson_ids=tuple(applied_lesson_ids),applied_rule_ids=tuple(applied_rule_ids),source_bundle_digests=bundles,claim_pairs=claims,manifest_pairs=manifests,receipt_pairs=receipts,version_pairs=versions,source_reviewers=reviewers,source_compilers=compilers,source_chair=source_chair,source_validator=source_validator,source_lineage_digest=lineage,source_sequence=source_sequence,is_latest=is_latest,status="SUBMISSION_HOLD_DOCKET_ANCHORED_NOT_ACCEPTED_NOT_DECIDED")
        row=DocketAnchor(**p,digest=canonical_digest(p))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("complete latest source docket lineage required")
            if self._anchor:
                if self._anchor==row:return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor=row; self._event("SUBMISSION_HOLD_DOCKET_ANCHORED",row.digest); return row
    def add_issue(self,issue_id,flow,answer_kind):
        with self._lock:
            key=(flow,answer_kind); expected=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS)
            if not self._anchor or key not in expected: raise GovernanceRejected("anchored known issue required")
            position=expected.index(key); parent=None if position==0 else self._issues.get(expected[position-1])
            if position and parent is None: raise GovernanceRejected("immediate prior issue required")
            cp=self._anchor.claim_pairs[position]; mp=self._anchor.manifest_pairs[position]; rp=self._anchor.receipt_pairs[position]; vp=self._anchor.version_pairs[position]
            outcome=actual_outcome(*cp,*mp,*rp,*vp)
            p=dict(issue_id=issue_id,flow=flow,answer_kind=answer_kind,outcome=outcome,source_bundle_digest=self._anchor.source_bundle_digests[position],claim_pair=cp,manifest_pair=mp,receipt_pair=rp,version_pair=vp,parent_issue_digest=None if parent is None else parent.digest,position=position+1,neutral_label=f"HUMAN_REVIEW_{outcome}",held=True,concluded=False,recommended=False,accepted=False)
            row=Issue(**p,digest=canonical_digest(p))
            if not self._issue_valid(row,key): raise GovernanceRejected("valid neutral ordered issue required")
            old=self._issues.get(key)
            if old:
                if old==row:return old
                raise GovernanceRejected("issue conflict")
            self._issues[key]=row; self._event("NEUTRAL_ISSUE_RECORDED",row.digest); self._hold("HUMAN_ISSUE_REVIEW_REQUIRED",row.digest); return row
    def finalize(self,matrix_id,compiler,validator):
        with self._lock:
            expected=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS)
            if self._matrix or tuple(self._issues)!=expected or not self._integrity(): raise GovernanceRejected("exact intact ordered issue set required")
            occupied=self._source_roles()
            if not _syn(compiler,"issue-matrix-compiler") or not _syn(validator,"issue-matrix-validator") or len({_identity(x) for x in occupied+(compiler,validator)})!=len(occupied)+2: raise GovernanceRejected("independent compiler and validator required")
            issue_set=canonical_digest(tuple(self._issues[k].digest for k in expected))
            p=dict(matrix_id=matrix_id,anchor_digest=self._anchor.digest,ordered_issue_set_digest=issue_set,compiler=compiler,validator=validator,source_reviewers=self._anchor.source_reviewers,source_compilers=self._anchor.source_compilers,source_chair=self._anchor.source_chair,source_validator=self._anchor.source_validator,source_lineage_digest=self._anchor.source_lineage_digest,complete=True,held=True,concluded=False,recommended=False,accepted=False,approved=False,activated=False,deployed=False,status="HUMAN_REVIEW_ISSUE_MATRIX_READY_ON_HOLD_NOT_CONCLUDED")
            row=IssueMatrix(**p,digest=canonical_digest(p)); self._matrix=row; self._event("HUMAN_REVIEW_ISSUE_MATRIX_HELD",row.digest); return row
    def _control_valid(self,row):
        p={k:v for k,v in row.__dict__.items() if k!="digest"}; return isinstance(row.control_id,int) and not isinstance(row.control_id,bool) and 8701<=row.control_id<=9100 and self._expected(row.control_id)==(row.workstream,row.aspect) and row.requirement_ref==f"synthetic:issue-matrix-requirement:{(row.control_id-8701)//25:02}" and _hex(row.fixture_digest) and row.expected_result==("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS") and row.digest==canonical_digest(p)
    def _registry_valid(self): return set(self._controls)==set(range(8701,9101)) and all(k==v.control_id and self._control_valid(v) for k,v in self._controls.items())
    def _source_roles(self): return self._anchor.source_reviewers+self._anchor.source_compilers+(self._anchor.source_chair,self._anchor.source_validator)
    def _anchor_valid(self,row):
        p={k:v for k,v in row.__dict__.items() if k!="digest"}; roles=row.source_reviewers+row.source_compilers+(row.source_chair,row.source_validator); expected_count=20
        derived_set=canonical_digest(row.source_bundle_digests); lineage=canonical_digest(("SUBMISSION_HOLD_DOCKET_FULL_LINEAGE",row.source_docket_digest,row.bundle_set_digest,row.source_bundle_digests,row.claim_pairs,row.manifest_pairs,row.receipt_pairs,row.version_pairs,row.source_reviewers,row.source_compilers,row.source_chair,row.source_validator))
        source_docket=canonical_digest(("SUBMISSION_HOLD_DOCKET_SOURCE",row.bundle_set_digest,row.source_reviewers,row.source_compilers,row.source_chair,row.source_validator))
        pairs_ok=all(len(x)==2 and all(_hex(v) for v in x) for pairs in (row.claim_pairs,row.manifest_pairs,row.receipt_pairs) for x in pairs); versions_ok=all(len(x)==2 and all(isinstance(v,int) and not isinstance(v,bool) and v>0 for v in x) for x in row.version_pairs)
        keys=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS)
        projections=tuple(bundle_projection_digest(*key,row.claim_pairs[i],row.manifest_pairs[i],row.receipt_pairs[i],row.version_pairs[i]) for i,key in enumerate(keys)) if all(len(x)==expected_count for x in (row.claim_pairs,row.manifest_pairs,row.receipt_pairs,row.version_pairs)) else ()
        return self._registry_valid() and _syn(row.anchor_id,"issue-matrix-anchor") and all(_hex(x) for x in (row.source_docket_digest,row.bundle_set_digest,row.lesson_registry_digest,row.remediation_manifest_digest)) and row.bundle_set_digest==derived_set and row.source_bundle_digests==projections and row.source_docket_digest==source_docket and row.applied_lesson_ids==APPLIED_LESSONS and row.applied_rule_ids==APPLIED_RULES and len(row.source_bundle_digests)==expected_count and len(set(row.source_bundle_digests))==expected_count and all(_hex(x) for x in row.source_bundle_digests) and all(len(x)==expected_count for x in (row.claim_pairs,row.manifest_pairs,row.receipt_pairs,row.version_pairs)) and pairs_ok and versions_ok and len(row.source_reviewers)==3 and len(row.source_compilers)==4 and all(_syn(x,k) for x,k in zip(row.source_reviewers,("readiness-reviewer","preflight-reviewer","reconsideration-reviewer"))) and all(_syn(x,"packet-compiler") for x in row.source_compilers) and _syn(row.source_chair,"human-deliberation-chair") and _syn(row.source_validator,"cross-party-validator") and len({_identity(x) for x in roles})==9 and row.source_lineage_digest==lineage and isinstance(row.source_sequence,int) and not isinstance(row.source_sequence,bool) and row.source_sequence>0 and row.is_latest is True and row.status=="SUBMISSION_HOLD_DOCKET_ANCHORED_NOT_ACCEPTED_NOT_DECIDED" and row.digest==canonical_digest(p)
    def _issue_valid(self,row,key):
        expected=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS); pos=expected.index(key) if key in expected else -1
        if not self._anchor or pos<0:return False
        previous=None if pos==0 else self._issues.get(expected[pos-1]); p={k:v for k,v in row.__dict__.items() if k!="digest"}; outcome=actual_outcome(*row.claim_pair,*row.manifest_pair,*row.receipt_pair,*row.version_pair)
        return _syn(row.issue_id,"human-review-issue") and key==(row.flow,row.answer_kind) and row.position==pos+1 and row.source_bundle_digest==self._anchor.source_bundle_digests[pos] and (row.claim_pair,row.manifest_pair,row.receipt_pair,row.version_pair)==(self._anchor.claim_pairs[pos],self._anchor.manifest_pairs[pos],self._anchor.receipt_pairs[pos],self._anchor.version_pairs[pos]) and row.parent_issue_digest==(None if previous is None else previous.digest) and row.outcome==outcome and row.neutral_label==f"HUMAN_REVIEW_{outcome}" and row.held is True and not any((row.concluded,row.recommended,row.accepted)) and row.digest==canonical_digest(p)
    def _event(self,action,artifact):
        prev=self._events[-1]["digest"] if self._events else None; p=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=prev); self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self,reason,artifact):
        prev=self._holds[-1]["digest"] if self._holds else None; p=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=prev); self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(rows,event):
        prev=None
        for i,row in enumerate(rows,1):
            keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest"); p={k:row.get(k) for k in keys}
            if row!={**p,"digest":canonical_digest(p)} or row["sequence"]!=i or row["previous_digest"]!=prev:return False
            prev=row["digest"]
        return True
    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._issue_valid(v,k) for k,v in self._issues.items()):return False
        if self._matrix:
            r=self._matrix; p={k:v for k,v in r.__dict__.items() if k!="digest"}; expected=tuple((f,k) for f in FLOWS for k in ANSWER_KINDS); issue_set=canonical_digest(tuple(self._issues[k].digest for k in expected)); occupied=self._source_roles()
            if not _syn(r.matrix_id,"human-review-issue-matrix") or r.anchor_digest!=self._anchor.digest or r.ordered_issue_set_digest!=issue_set or not _syn(r.compiler,"issue-matrix-compiler") or not _syn(r.validator,"issue-matrix-validator") or len({_identity(x) for x in occupied+(r.compiler,r.validator)})!=len(occupied)+2 or (r.source_reviewers,r.source_compilers,r.source_chair,r.source_validator,r.source_lineage_digest)!=(self._anchor.source_reviewers,self._anchor.source_compilers,self._anchor.source_chair,self._anchor.source_validator,self._anchor.source_lineage_digest) or r.complete is not True or r.held is not True or any((r.concluded,r.recommended,r.accepted,r.approved,r.activated,r.deployed)) or r.status!="HUMAN_REVIEW_ISSUE_MATRIX_READY_ON_HOLD_NOT_CONCLUDED" or r.digest!=canonical_digest(p):return False
        expected_events=[]
        if self._anchor:expected_events.append(("SUBMISSION_HOLD_DOCKET_ANCHORED",self._anchor.digest))
        expected_events.extend(("NEUTRAL_ISSUE_RECORDED",x.digest) for x in self._issues.values())
        if self._matrix:expected_events.append(("HUMAN_REVIEW_ISSUE_MATRIX_HELD",self._matrix.digest))
        return [(x["action"],x["artifact_digest"]) for x in self._events]==expected_events and [(x["reason"],x["attachment_digest"]) for x in self._holds]==[("HUMAN_ISSUE_REVIEW_REQUIRED",x.digest) for x in self._issues.values()]
    def evidence(self):
        ok=self._integrity(); complete=len(self._issues)==20 and self._matrix is not None
        return {"range":[8701,9100],"control_count":400,"workstream_count":16,"controls_per_workstream":25,"control_matrix_valid":WORKSTREAMS==tuple((8701+i*25,8725+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25,"registered_control_count":len(self._controls),"issue_count":len(self._issues),"hold_count":len(self._holds),"event_count":len(self._events),"integrity_valid":ok,"complete_issue_matrix_evidence":complete and ok,"maximum_state":"HUMAN_REVIEW_ISSUE_MATRIX_READY_ON_HOLD_NOT_CONCLUDED" if self._matrix else "ISSUE_MATRIX_INCOMPLETE","applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),"external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,"accepted":False,"recommended":False,"concluded":False,"approved":False,"activated":False}
