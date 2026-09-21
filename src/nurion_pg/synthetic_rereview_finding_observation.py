"""Synthetic finding-observation controls #11101-#11500.

The layer observes twenty independent re-reviews and opens human finding review.
It never concludes, recommends, accepts, resolves, executes, or performs I/O.
"""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_rebuttal_correction_independent_rereview import (
    APPLIED_LESSONS, APPLIED_RULES, CASE_KEYS, ROUTES, SOURCE_ACTOR_KINDS,
    SourceSubmission, source_submission_digest, rereview_digest,
)
from .synthetic_rebuttal_correction_submission_validation import RESPONDER, derived_receipt_digest

WORKSTREAM_NAMES = (
    "REREVIEW_DOCKET_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "SOURCE_REREVIEW_SEMANTIC_RECONSTRUCTION", "NO_FINDING_MARKER_PRESERVATION",
    "REBUTTAL_FINDING_OBSERVATION", "CORRECTION_FINDING_OBSERVATION",
    "FINDING_DRAFTER_ASSIGNMENT", "FINDING_REVIEWER_ASSIGNMENT",
    "IMMEDIATE_PARENT_FINDING_LINEAGE", "FULL_SOURCE_ACTOR_PROJECTION",
    "SOURCE_REREVIEWER_PROJECTION", "FINDING_ROLE_SEPARATION",
    "APPEND_ONLY_FINDING_EVENT", "UNRESOLVED_FINDING_HOLD_CHAIN",
    "PARTIAL_BATCH_FAIL_CLOSED", "NON_CONCLUSION_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((11101 + i * 25, 11125 + i * 25, n) for i, n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type", "tenant_scope",
    "role_scope", "state_precondition", "latest_sequence", "source_binding",
    "digest_recalculation", "negative_path", "missing_input", "duplicate_input", "replay",
    "conflict", "stale_version", "concurrency", "partial_batch", "ordering", "append_only",
    "hold_propagation", "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})

def _syn(value, kind): return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
def _identity(value): return value.rsplit(":", 1)[-1].casefold()

@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str
    fixture_digest: str; expected_result: str; digest: str

@dataclass(frozen=True)
class SourceReReview:
    rereview_id: str; flow: str; answer_kind: str; source_submission_digest: str; route: str
    reviewer: str | None; marker: str; parent_rereview_digest: str | None; position: int
    held: bool; pending_human_reexamination: bool; concluded: bool; resolved: bool
    accepted: bool; digest: str

@dataclass(frozen=True)
class Anchor:
    anchor_id: str; source_docket_digest: str; source_rereview_set_digest: str
    lesson_registry_digest: str; remediation_manifest_digest: str
    applied_lesson_ids: tuple[str, ...]; applied_rule_ids: tuple[str, ...]
    source_submissions: tuple[SourceSubmission, ...]; source_rereviews: tuple[SourceReReview, ...]
    source_actor_roles: tuple[str, ...]; source_submission_compiler: str; source_submission_validator: str
    source_rereview_compiler: str; source_rereview_validator: str; full_lineage_digest: str
    source_sequence: int; is_latest: bool; status: str; digest: str

@dataclass(frozen=True)
class Finding:
    finding_id: str; flow: str; answer_kind: str; source_rereview_digest: str; route: str
    drafter: str | None; reviewer: str | None; marker: str; parent_finding_digest: str | None
    position: int; observation_projection_digest: str; held: bool; pending_human_finding_review: bool; concluded: bool
    recommended: bool; accepted: bool; resolved: bool; digest: str

@dataclass(frozen=True)
class Docket:
    docket_id: str; anchor_digest: str; finding_set_digest: str; compiler: str; validator: str
    full_lineage_digest: str; complete: bool; held: bool; pending_human_finding_review: bool
    concluded: bool; recommended: bool; accepted: bool; resolved: bool; approved: bool
    activated: bool; deployed: bool; status: str; digest: str

def observation_projection_digest(source, route, drafter, reviewer, marker):
    return canonical_digest(("PENDING_FINDING_OBSERVATION_PROJECTION", source, route,
                             drafter, reviewer, marker))

def finding_digest(finding_id, flow, kind, source, route, drafter, reviewer, marker, parent, position, projection):
    return canonical_digest(("REREVIEW_FINDING_OBSERVATION", finding_id, flow, kind, source,
                             route, drafter, reviewer, marker, parent, position, projection))

def _anchor_payload(payload):
    result = dict(payload)
    result["source_submissions"] = tuple(tuple(x.__dict__.values()) for x in result["source_submissions"])
    result["source_rereviews"] = tuple(tuple(x.__dict__.values()) for x in result["source_rereviews"])
    return result

class SyntheticReReviewFindingObservation:
    def __init__(self):
        self._controls = {}; self._anchor = None; self._findings = {}; self._docket = None
        self._events = []; self._holds = []; self._lock = RLock()

    def _expected(self, control_id):
        index = control_id - 11101
        return WORKSTREAM_NAMES[index // 25], CONTROL_ASPECTS[index % 25]

    def add_control(self, control_id, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        payload = dict(control_id=control_id, workstream=workstream, aspect=aspect,
                       requirement_ref=requirement_ref, fixture_digest=fixture_digest, expected_result=expected_result)
        row = Control(**payload, digest=canonical_digest(payload))
        with self._lock:
            if not self._control_valid(row): raise GovernanceRejected("valid #11101-#11500 control required")
            old = self._controls.get(control_id)
            if old:
                if old == row: return old
                raise GovernanceRejected("control conflict")
            self._controls[control_id] = row; return row

    def anchor(self, anchor_id, source_docket_digest, source_set_digest, registry_digest, manifest_digest,
               lessons, rules, submissions, rereviews, source_actor_roles, submission_compiler,
               submission_validator, rereview_compiler, rereview_validator, sequence, is_latest):
        submissions, rereviews, source_actor_roles = tuple(submissions), tuple(rereviews), tuple(source_actor_roles)
        lineage = canonical_digest(("REREVIEW_FULL_ROLE_LINEAGE", source_docket_digest, source_set_digest,
            tuple(x.digest for x in submissions), tuple(x.digest for x in rereviews), source_actor_roles,
            submission_compiler, submission_validator, rereview_compiler, rereview_validator))
        payload = dict(anchor_id=anchor_id, source_docket_digest=source_docket_digest,
            source_rereview_set_digest=source_set_digest, lesson_registry_digest=registry_digest,
            remediation_manifest_digest=manifest_digest, applied_lesson_ids=tuple(lessons),
            applied_rule_ids=tuple(rules), source_submissions=submissions, source_rereviews=rereviews,
            source_actor_roles=source_actor_roles, source_submission_compiler=submission_compiler,
            source_submission_validator=submission_validator, source_rereview_compiler=rereview_compiler,
            source_rereview_validator=rereview_validator, full_lineage_digest=lineage,
            source_sequence=sequence, is_latest=is_latest,
            status="INDEPENDENT_REREVIEW_DOCKET_ANCHORED_FINDINGS_NOT_DRAFTED")
        row = Anchor(**payload, digest=canonical_digest(_anchor_payload(payload)))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("complete latest rereview docket required")
            if self._anchor:
                if self._anchor == row: return row
                raise GovernanceRejected("anchor conflict")
            self._anchor = row; self._event("REREVIEW_DOCKET_ANCHORED", row.digest); return row

    def add_finding(self, finding_id, flow, kind, drafter=None, reviewer=None):
        with self._lock:
            key = (flow, kind)
            if not self._anchor or key not in CASE_KEYS: raise GovernanceRejected("anchored rereview required")
            position = CASE_KEYS.index(key); source = self._anchor.source_rereviews[position]
            previous = None if position == 0 else self._findings.get(CASE_KEYS[position - 1])
            if position and previous is None: raise GovernanceRejected("immediate prior finding required")
            if source.route == "NOT_APPLICABLE_PRESERVED":
                if drafter is not None or reviewer is not None: raise GovernanceRejected("N/A forbids actors")
                marker = "NO_FINDING_MARKER_PRESERVED"
            else:
                if not _syn(drafter, "finding-drafter") or not _syn(reviewer, "finding-reviewer"):
                    raise GovernanceRejected("finding drafter and reviewer required")
                occupied = self._source_actors() + tuple(y for x in self._findings.values() for y in (x.drafter, x.reviewer) if y)
                if len({_identity(x) for x in occupied + (drafter, reviewer)}) != len(occupied) + 2:
                    raise GovernanceRejected("finding actor collision")
                marker = "HUMAN_FINDING_REVIEW_PENDING"
            parent = None if previous is None else previous.digest
            projection = observation_projection_digest(source.digest, source.route, drafter, reviewer, marker)
            digest = finding_digest(finding_id, flow, kind, source.digest, source.route, drafter, reviewer, marker, parent, position + 1, projection)
            row = Finding(finding_id, flow, kind, source.digest, source.route, drafter, reviewer, marker,
                parent, position + 1, projection, True, source.route != "NOT_APPLICABLE_PRESERVED",
                False, False, False, False, digest)
            if not self._finding_valid(row, key): raise GovernanceRejected("valid pending finding required")
            old = self._findings.get(key)
            if old:
                if old == row: return old
                raise GovernanceRejected("finding conflict")
            self._findings[key] = row; self._event("FINDING_OBSERVATION_RECORDED", row.digest)
            if row.pending_human_finding_review: self._hold("HUMAN_FINDING_REVIEW_REQUIRED", row.digest)
            return row

    def finalize(self, docket_id, compiler, validator):
        with self._lock:
            if self._docket or tuple(self._findings) != CASE_KEYS or not self._integrity():
                raise GovernanceRejected("complete intact finding batch required")
            actors = self._source_actors() + tuple(y for x in self._findings.values() for y in (x.drafter, x.reviewer) if y) + (compiler, validator)
            if not _syn(compiler, "finding-docket-compiler") or not _syn(validator, "finding-docket-validator") or len({_identity(x) for x in actors}) != len(actors):
                raise GovernanceRejected("independent finding docket actors required")
            finding_set = canonical_digest(tuple(self._findings[k].digest for k in CASE_KEYS))
            payload = dict(docket_id=docket_id, anchor_digest=self._anchor.digest, finding_set_digest=finding_set,
                compiler=compiler, validator=validator, full_lineage_digest=self._anchor.full_lineage_digest,
                complete=True, held=True, pending_human_finding_review=True, concluded=False,
                recommended=False, accepted=False, resolved=False, approved=False, activated=False,
                deployed=False, status="FINDING_OBSERVATION_DOCKET_ON_HOLD_HUMAN_FINDING_REVIEW_PENDING")
            row = Docket(**payload, digest=canonical_digest(payload)); self._docket = row
            self._event("FINDING_OBSERVATION_DOCKET_HELD", row.digest); return row

    def _control_valid(self, row):
        payload = {k:v for k,v in row.__dict__.items() if k != "digest"}
        return isinstance(row.control_id, int) and not isinstance(row.control_id, bool) and 11101 <= row.control_id <= 11500 and self._expected(row.control_id) == (row.workstream, row.aspect) and row.requirement_ref == f"synthetic:finding-observation-requirement:{(row.control_id-11101)//25:02}" and _hex(row.fixture_digest) and row.expected_result == ("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS") and row.digest == canonical_digest(payload)

    def _registry_valid(self):
        return set(self._controls) == set(range(11101,11501)) and all(self._control_valid(x) for x in self._controls.values())

    def _source_submission_valid(self, row, position, rows):
        parent = None if position == 0 else rows[position-1].digest
        flow, kind = CASE_KEYS[position]; route = ROUTES[position % 5]
        if route == "NOT_APPLICABLE_PRESERVED":
            material = row.submitter_party is None and row.document_digest is None and row.receipt_digest is None and row.marker == "NO_SUBMISSION_REQUIRED"
        else:
            material = row.submitter_party == RESPONDER[flow] and _hex(row.document_digest) and row.receipt_digest == derived_receipt_digest(flow, kind, row.source_review_digest, route, row.submitter_party, row.document_digest) and row.marker == "SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        return _syn(row.submission_id,"rebuttal-correction-submission") and (row.flow,row.answer_kind)==(flow,kind) and _hex(row.source_review_digest) and row.route==route and material and row.parent_submission_digest==parent and row.position==position+1 and row.held is True and row.validated is True and not row.resolved and not row.accepted and row.digest==source_submission_digest(row)

    def _source_rereview_valid(self, row, position, rows, submissions):
        parent = None if position == 0 else rows[position-1].digest; source = submissions[position]
        if source.route == "NOT_APPLICABLE_PRESERVED": state = row.reviewer is None and row.marker=="NO_SUBMISSION_MARKER_PRESERVED" and row.pending_human_reexamination is False
        else: state = _syn(row.reviewer,"independent-human-rereviewer") and row.marker=="HUMAN_REEXAMINATION_PENDING" and row.pending_human_reexamination is True
        expected = rereview_digest(row.rereview_id,row.flow,row.answer_kind,source.digest,source.route,row.reviewer,row.marker,parent,position+1)
        return _syn(row.rereview_id,"independent-rereview") and (row.flow,row.answer_kind)==CASE_KEYS[position] and row.source_submission_digest==source.digest and row.route==source.route and state and row.parent_rereview_digest==parent and row.position==position+1 and row.held is True and not any((row.concluded,row.resolved,row.accepted)) and row.digest==expected

    def _source_actors(self):
        a=self._anchor
        return a.source_actor_roles + (a.source_submission_compiler,a.source_submission_validator) + tuple(x.reviewer for x in a.source_rereviews if x.reviewer) + (a.source_rereview_compiler,a.source_rereview_validator)

    def _anchor_valid(self,row):
        payload={k:v for k,v in row.__dict__.items() if k!="digest"}
        rereview_set=canonical_digest(tuple(x.digest for x in row.source_rereviews))
        docket=canonical_digest(("INDEPENDENT_REREVIEW_DOCKET_SOURCE",rereview_set,row.source_rereview_compiler,row.source_rereview_validator))
        lineage=canonical_digest(("REREVIEW_FULL_ROLE_LINEAGE",row.source_docket_digest,row.source_rereview_set_digest,tuple(x.digest for x in row.source_submissions),tuple(x.digest for x in row.source_rereviews),row.source_actor_roles,row.source_submission_compiler,row.source_submission_validator,row.source_rereview_compiler,row.source_rereview_validator))
        actors=row.source_actor_roles+(row.source_submission_compiler,row.source_submission_validator)+tuple(x.reviewer for x in row.source_rereviews if x.reviewer)+(row.source_rereview_compiler,row.source_rereview_validator)
        expected_kinds=SOURCE_ACTOR_KINDS
        return self._registry_valid() and _syn(row.anchor_id,"finding-observation-anchor") and len(row.source_submissions)==20 and len({x.submission_id for x in row.source_submissions})==20 and all(self._source_submission_valid(x,i,row.source_submissions) for i,x in enumerate(row.source_submissions)) and len(row.source_rereviews)==20 and len({x.rereview_id for x in row.source_rereviews})==20 and all(self._source_rereview_valid(x,i,row.source_rereviews,row.source_submissions) for i,x in enumerate(row.source_rereviews)) and row.source_rereview_set_digest==rereview_set and row.source_docket_digest==docket and _hex(row.lesson_registry_digest) and _hex(row.remediation_manifest_digest) and row.applied_lesson_ids==APPLIED_LESSONS and row.applied_rule_ids==APPLIED_RULES and len(row.source_actor_roles)==32 and all(_syn(x,k) for x,k in zip(row.source_actor_roles,expected_kinds)) and _syn(row.source_submission_compiler,"submission-docket-compiler") and _syn(row.source_submission_validator,"submission-docket-validator") and _syn(row.source_rereview_compiler,"rereview-docket-compiler") and _syn(row.source_rereview_validator,"rereview-docket-validator") and len({_identity(x) for x in actors})==len(actors) and row.full_lineage_digest==lineage and isinstance(row.source_sequence,int) and not isinstance(row.source_sequence,bool) and row.source_sequence>0 and row.is_latest is True and row.status=="INDEPENDENT_REREVIEW_DOCKET_ANCHORED_FINDINGS_NOT_DRAFTED" and row.digest==canonical_digest(_anchor_payload(payload))

    def _finding_valid(self,row,key):
        if not self._anchor or key not in CASE_KEYS:return False
        position=CASE_KEYS.index(key);source=self._anchor.source_rereviews[position];previous=None if position==0 else self._findings.get(CASE_KEYS[position-1])
        if source.route=="NOT_APPLICABLE_PRESERVED": state=row.drafter is None and row.reviewer is None and row.marker=="NO_FINDING_MARKER_PRESERVED" and row.pending_human_finding_review is False
        else: state=_syn(row.drafter,"finding-drafter") and _syn(row.reviewer,"finding-reviewer") and row.marker=="HUMAN_FINDING_REVIEW_PENDING" and row.pending_human_finding_review is True
        projection=observation_projection_digest(source.digest,source.route,row.drafter,row.reviewer,row.marker)
        expected=finding_digest(row.finding_id,row.flow,row.answer_kind,source.digest,source.route,row.drafter,row.reviewer,row.marker,None if previous is None else previous.digest,position+1,projection)
        ids=[x.finding_id for k,x in self._findings.items() if k!=key]
        return _syn(row.finding_id,"finding-observation") and row.finding_id not in ids and (row.flow,row.answer_kind)==key and row.source_rereview_digest==source.digest and row.route==source.route and state and row.parent_finding_digest==(None if previous is None else previous.digest) and row.position==position+1 and row.observation_projection_digest==projection and row.held is True and not any((row.concluded,row.recommended,row.accepted,row.resolved)) and row.digest==expected

    def _event(self,action,artifact):
        previous=self._events[-1]["digest"] if self._events else None;payload=dict(sequence=len(self._events)+1,action=action,artifact_digest=artifact,previous_digest=previous);self._events.append({**payload,"digest":canonical_digest(payload)})
    def _hold(self,reason,artifact):
        previous=self._holds[-1]["digest"] if self._holds else None;payload=dict(sequence=len(self._holds)+1,reason=reason,attachment_digest=artifact,previous_digest=previous);self._holds.append({**payload,"digest":canonical_digest(payload)})
    @staticmethod
    def _chain(rows,event):
        previous=None
        for sequence,row in enumerate(rows,1):
            keys=("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest");payload={k:row.get(k) for k in keys}
            if row!={**payload,"digest":canonical_digest(payload)} or row["sequence"]!=sequence or row["previous_digest"]!=previous:return False
            previous=row["digest"]
        return True

    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._finding_valid(v,k) for k,v in self._findings.items()):return False
        events=[]
        if self._anchor:events.append(("REREVIEW_DOCKET_ANCHORED",self._anchor.digest))
        events.extend(("FINDING_OBSERVATION_RECORDED",x.digest) for x in self._findings.values())
        if self._docket:events.append(("FINDING_OBSERVATION_DOCKET_HELD",self._docket.digest))
        holds=[("HUMAN_FINDING_REVIEW_REQUIRED",x.digest) for x in self._findings.values() if x.pending_human_finding_review]
        if [(x["action"],x["artifact_digest"]) for x in self._events]!=events or [(x["reason"],x["attachment_digest"]) for x in self._holds]!=holds:return False
        if self._docket:
            row=self._docket;payload={k:v for k,v in row.__dict__.items() if k!="digest"};actors=self._source_actors()+tuple(y for x in self._findings.values() for y in (x.drafter,x.reviewer) if y)+(row.compiler,row.validator)
            if not _syn(row.docket_id,"finding-observation-docket") or row.anchor_digest!=self._anchor.digest or row.finding_set_digest!=canonical_digest(tuple(self._findings[k].digest for k in CASE_KEYS)) or not _syn(row.compiler,"finding-docket-compiler") or not _syn(row.validator,"finding-docket-validator") or len({_identity(x) for x in actors})!=len(actors) or row.full_lineage_digest!=self._anchor.full_lineage_digest or row.complete is not True or row.held is not True or row.pending_human_finding_review is not True or any((row.concluded,row.recommended,row.accepted,row.resolved,row.approved,row.activated,row.deployed)) or row.status!="FINDING_OBSERVATION_DOCKET_ON_HOLD_HUMAN_FINDING_REVIEW_PENDING" or row.digest!=canonical_digest(payload):return False
        return True

    def evidence(self):
        ok=self._integrity()
        complete=len(self._findings)==20 and self._docket is not None and ok
        projection_set=canonical_digest(tuple(self._findings[k].observation_projection_digest for k in CASE_KEYS)) if complete else None
        finding_set=canonical_digest(tuple(self._findings[k].digest for k in CASE_KEYS)) if complete else None
        return {"range":[11101,11500],"control_count":400,"registered_control_count":len(self._controls),"finding_count":len(self._findings),"source_actor_count":len(self._anchor.source_actor_roles) if self._anchor else 0,"source_rereviewer_count":sum(x.reviewer is not None for x in self._anchor.source_rereviews) if self._anchor else 0,"full_lineage_digest":self._anchor.full_lineage_digest if self._anchor else None,"observation_projection_set_digest":projection_set,"finding_set_digest":finding_set,"final_docket_digest":self._docket.digest if complete else None,"no_finding_marker_count":sum(x.route=="NOT_APPLICABLE_PRESERVED" for x in self._findings.values()),"rebuttal_finding_pending_count":sum(x.route=="REBUTTAL_OPPORTUNITY_REQUIRED" and x.pending_human_finding_review for x in self._findings.values()),"correction_finding_pending_count":sum(x.route=="CORRECTION_REQUEST_REQUIRED" and x.pending_human_finding_review for x in self._findings.values()),"hold_count":len(self._holds),"integrity_valid":ok,"complete_pending_finding_docket_evidence":complete,"maximum_state":"FINDING_OBSERVATION_DOCKET_ON_HOLD_HUMAN_FINDING_REVIEW_PENDING" if self._docket else "FINDING_DOCKET_INCOMPLETE","external_calls":0,"document_transmissions":0,"external_pg_calls":0,"payment_approvals":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"concluded":False,"recommended":False,"accepted":False,"resolved":False,"approved":False,"activated":False}
