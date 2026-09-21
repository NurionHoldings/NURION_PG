"""Synthetic/in-memory reconciliation submissions and human hold controls #8301-#8700."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "RECONCILIATION_QUEUE_SOURCE_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "TENANT_PROPOSAL_DOCUMENT", "NURION_PROPOSAL_DOCUMENT", "UPSTREAM_PROPOSAL_DOCUMENT",
    "COUNTERARGUMENT_DOCUMENT", "SUPPORTING_EVIDENCE_DOCUMENT", "FOUR_DIRECTION_ROUTE_BINDING",
    "AUTHOR_ROLE_DERIVATION", "PARENT_TARGET_LINEAGE", "CONTENT_DERIVATION",
    "THREE_DOCUMENT_BUNDLE", "APPEND_ONLY_SUBMISSION_EVENT", "HUMAN_HOLD_CHAIN",
    "INDEPENDENT_LINEAGE_VALIDATION", "NON_CONCLUSION_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((8301 + i * 25, 8325 + i * 25, name) for i, name in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type", "tenant_scope",
    "role_scope", "state_precondition", "latest_sequence", "source_binding", "digest_recalculation",
    "negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version",
    "concurrency", "partial_batch", "ordering", "append_only", "hold_propagation",
    "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})
FLOWS = ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")
FLOW_PARTIES = {
    "tenant_to_nurion": ("TENANT_AGENCY", "NURION_PG"),
    "nurion_to_upstream": ("NURION_PG", "UPSTREAM_PG"),
    "upstream_to_nurion": ("UPSTREAM_PG", "NURION_PG"),
    "nurion_to_tenant": ("NURION_PG", "TENANT_AGENCY"),
}
ANSWER_KINDS = ("ASSUMPTION_RESPONSE", "RESIDUAL_RISK_RESPONSE", "ADDITIONAL_EVIDENCE", "MEANING_CLARIFICATION", "SAFE_BOUNDARY_ACKNOWLEDGEMENT")
COMPARISON_OUTCOMES = ("CONSISTENT", "CLAIM_CONFLICT", "MANIFEST_CONFLICT", "RECEIPT_CONFLICT", "VERSION_CONFLICT")
SUBMISSION_KINDS = ("NONBINDING_PROPOSAL", "NONBINDING_COUNTERARGUMENT", "SUPPORTING_EVIDENCE_REFERENCE")
APPLIED_LESSONS = ("ARL-3901-001", "ARL-4301-001", "ARL-4301-002", "ARL-4301-003", "ARL-4701-001", "ARL-5101-001", "ARL-5501-001", "ARL-5901-001", "ARL-6301-001", "ARL-6701-001", "ARL-7101-001", "ARL-7501-001", "ARL-7901-001", "ARL-8301-001")
APPLIED_RULES = tuple(f"ARP-{i:02}" for i in range(1, 9))

def _syn(value, kind): return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
def _identity(value): return value.rsplit(":", 1)[-1].casefold()
def expected_author(flow, submission_kind):
    source, counterparty = FLOW_PARTIES.get(flow, (None, None))
    return counterparty if submission_kind == "NONBINDING_COUNTERARGUMENT" else source
def derived_content(case, submission_kind, author, sequence):
    return canonical_digest(("RECONCILIATION_SUBMISSION_CONTENT", case.case_digest, case.comparison_outcome, submission_kind, author, sequence))
def source_case_outcome(case):
    if case.source_claim_digest != case.counterpart_claim_digest: return "CLAIM_CONFLICT"
    if case.source_manifest_digest != case.counterpart_manifest_digest: return "MANIFEST_CONFLICT"
    if case.source_receipt_digest != case.counterpart_receipt_digest: return "RECEIPT_CONFLICT"
    if case.source_version != case.counterpart_version: return "VERSION_CONFLICT"
    return "CONSISTENT"
def _anchor_payload(p):
    q = dict(p); q["source_cases"] = tuple(tuple(x.__dict__.values()) for x in q["source_cases"]); return q

@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str; fixture_digest: str; expected_result: str; digest: str

@dataclass(frozen=True)
class SourceCase:
    flow: str; answer_kind: str; comparison_outcome: str; source_binding_digest: str
    counterpart_binding_digest: str; source_claim_digest: str; counterpart_claim_digest: str
    source_manifest_digest: str; counterpart_manifest_digest: str; source_receipt_digest: str
    counterpart_receipt_digest: str; source_version: int; counterpart_version: int
    comparison_digest: str; queue_route_digest: str; case_digest: str

@dataclass(frozen=True)
class QueueAnchor:
    anchor_id: str; queue_packet_digest: str; case_set_digest: str; lesson_registry_digest: str
    remediation_manifest_digest: str; applied_lesson_ids: tuple[str, ...]; applied_rule_ids: tuple[str, ...]
    source_cases: tuple[SourceCase, ...]; source_sequence: int; is_latest: bool
    source_reviewers: tuple[str, str, str]; source_compilers: tuple[str, str, str, str]
    source_chair: str; source_validator: str; source_lineage_digest: str; status: str; digest: str

@dataclass(frozen=True)
class Submission:
    submission_id: str; flow: str; answer_kind: str; submission_kind: str; author_party: str
    source_case_digest: str; parent_submission_digest: str | None; content_digest: str; sequence: int
    author_identity: str; lineage_validator: str; nonbinding: bool; complete: bool; status: str; digest: str

@dataclass(frozen=True)
class SubmissionBundle:
    bundle_id: str; flow: str; answer_kind: str; source_case_digest: str; proposal_digest: str
    counterargument_digest: str; evidence_digest: str; bundle_digest: str; hold_route_digest: str
    bundle_compiler: str; lineage_validator: str; complete: bool; held: bool; accepted: bool
    recommended: bool; decided: bool; approved: bool; activated: bool; status: str; digest: str

@dataclass(frozen=True)
class HoldDocket:
    docket_id: str; anchor_digest: str; bundle_set_digest: str; docket_compiler: str; lineage_validator: str
    source_reviewers: tuple[str, str, str]; source_compilers: tuple[str, str, str, str]
    source_chair: str; source_validator: str; source_lineage_digest: str; complete: bool
    accepted: bool; recommended: bool; decided: bool; approved: bool; activated: bool; deployed: bool
    status: str; digest: str

class SyntheticReconciliationSubmissionLineage:
    """Creates inert proposal/counterargument/evidence bundles; never resolves them."""
    def __init__(self):
        self._controls = {}; self._anchor = None; self._submissions = {}; self._bundles = {}; self._docket = None
        self._events = []; self._holds = []; self._lock = RLock()

    def _expected(self, cid):
        i = cid - 8301; return WORKSTREAM_NAMES[i // 25], CONTROL_ASPECTS[i % 25]

    def add_control(self, cid, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        p = dict(control_id=cid, workstream=workstream, aspect=aspect, requirement_ref=requirement_ref, fixture_digest=fixture_digest, expected_result=expected_result)
        row = Control(**p, digest=canonical_digest(p))
        with self._lock:
            if not self._control_valid(row): raise GovernanceRejected("valid #8301-#8700 control required")
            old = self._controls.get(cid)
            if old:
                if old == row: return old
                raise GovernanceRejected("control conflict")
            self._controls[cid] = row; return row

    def anchor_queue(self, anchor_id, queue_packet_digest, case_set_digest, lesson_registry_digest,
                     remediation_manifest_digest, applied_lesson_ids, applied_rule_ids, source_cases,
                     source_sequence, is_latest, source_reviewers, source_compilers, source_chair, source_validator):
        cases = tuple(source_cases); reviewers = tuple(source_reviewers); compilers = tuple(source_compilers)
        lineage = canonical_digest(("RECONCILIATION_QUEUE_FULL_LINEAGE", queue_packet_digest, case_set_digest,
                                    tuple(x.case_digest for x in cases), reviewers, compilers, source_chair, source_validator))
        p = dict(anchor_id=anchor_id, queue_packet_digest=queue_packet_digest, case_set_digest=case_set_digest,
                 lesson_registry_digest=lesson_registry_digest, remediation_manifest_digest=remediation_manifest_digest,
                 applied_lesson_ids=tuple(applied_lesson_ids), applied_rule_ids=tuple(applied_rule_ids), source_cases=cases,
                 source_sequence=source_sequence, is_latest=is_latest, source_reviewers=reviewers, source_compilers=compilers,
                 source_chair=source_chair, source_validator=source_validator, source_lineage_digest=lineage,
                 status="RECONCILIATION_QUEUE_ANCHORED_NOT_ACCEPTED_NOT_DECIDED")
        row = QueueAnchor(**p, digest=canonical_digest(_anchor_payload(p)))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("latest complete reconciliation queue lineage required")
            if self._anchor:
                if self._anchor == row: return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor = row; self._event("RECONCILIATION_QUEUE_ANCHORED", row.digest); return row

    def add_submission(self, submission_id, flow, answer_kind, submission_kind, author_party, author_identity, lineage_validator):
        with self._lock:
            case = self._case(flow, answer_kind); key = (flow, answer_kind, submission_kind)
            if not case or submission_kind not in SUBMISSION_KINDS: raise GovernanceRejected("anchored case and submission kind required")
            sequence = SUBMISSION_KINDS.index(submission_kind) + 1
            prior = self._submissions.get((flow, answer_kind, SUBMISSION_KINDS[sequence-2])) if sequence > 1 else None
            if sequence > 1 and prior is None: raise GovernanceRejected("immediate prior submission required")
            parent = None if sequence == 1 else prior.digest
            content = derived_content(case, submission_kind, author_party, sequence)
            p = dict(submission_id=submission_id, flow=flow, answer_kind=answer_kind, submission_kind=submission_kind,
                     author_party=author_party, source_case_digest=case.case_digest, parent_submission_digest=parent,
                     content_digest=content, sequence=sequence, author_identity=author_identity,
                     lineage_validator=lineage_validator, nonbinding=True, complete=True,
                     status="SUBMISSION_RECORDED_FOR_HUMAN_REVIEW_NOT_ACCEPTED")
            row = Submission(**p, digest=canonical_digest(p))
            if not self._submission_valid(row, key): raise GovernanceRejected("complete ordered nonbinding submission required")
            old = self._submissions.get(key)
            if old:
                if old == row: return old
                raise GovernanceRejected("submission conflict")
            self._submissions[key] = row; self._event("RECONCILIATION_SUBMISSION_RECORDED", row.digest); return row

    def build_bundle(self, bundle_id, flow, answer_kind, bundle_compiler):
        with self._lock:
            case = self._case(flow, answer_kind); rows = tuple(self._submissions.get((flow, answer_kind, k)) for k in SUBMISSION_KINDS)
            if not case or len(self._submissions) != 60 or any(x is None for x in rows): raise GovernanceRejected("complete three-document submission set required")
            validator = rows[0].lineage_validator
            bdigest = canonical_digest(("RECONCILIATION_SUBMISSION_BUNDLE", case.case_digest, *(x.digest for x in rows)))
            route = canonical_digest(("HUMAN_RECONCILIATION_HOLD", flow, answer_kind, case.comparison_outcome, bdigest))
            p = dict(bundle_id=bundle_id, flow=flow, answer_kind=answer_kind, source_case_digest=case.case_digest,
                     proposal_digest=rows[0].digest, counterargument_digest=rows[1].digest, evidence_digest=rows[2].digest,
                     bundle_digest=bdigest, hold_route_digest=route, bundle_compiler=bundle_compiler,
                     lineage_validator=validator, complete=True, held=True, accepted=False, recommended=False,
                     decided=False, approved=False, activated=False,
                     status="HELD_FOR_HUMAN_RECONCILIATION_NOT_ACCEPTED_NOT_DECIDED")
            row = SubmissionBundle(**p, digest=canonical_digest(p)); key = (flow, answer_kind)
            if not self._bundle_valid(row, key): raise GovernanceRejected("valid held bundle required")
            old = self._bundles.get(key)
            if old:
                if old == row: return old
                raise GovernanceRejected("bundle conflict")
            self._bundles[key] = row; self._event("SUBMISSION_BUNDLE_HELD", row.digest); self._hold("HUMAN_RECONCILIATION_REQUIRED", row.digest); return row

    def finalize(self, docket_id, docket_compiler):
        with self._lock:
            expected = {(f, k) for f in FLOWS for k in ANSWER_KINDS}
            if self._docket or set(self._bundles) != expected or not self._integrity(): raise GovernanceRejected("exact intact held bundle set required")
            validators = {x.lineage_validator for x in self._bundles.values()}
            occupied = self._source_roles() + tuple(x.author_identity for x in self._submissions.values()) + tuple(x.bundle_compiler for x in self._bundles.values()) + tuple(validators)
            if len(validators) != 1 or not _syn(docket_compiler, "submission-docket-compiler") or _identity(docket_compiler) in {_identity(x) for x in occupied}: raise GovernanceRejected("independent docket compiler required")
            bset = canonical_digest(tuple(self._bundles[k].digest for k in sorted(self._bundles)))
            p = dict(docket_id=docket_id, anchor_digest=self._anchor.digest, bundle_set_digest=bset,
                     docket_compiler=docket_compiler, lineage_validator=next(iter(validators)),
                     source_reviewers=self._anchor.source_reviewers, source_compilers=self._anchor.source_compilers,
                     source_chair=self._anchor.source_chair, source_validator=self._anchor.source_validator,
                     source_lineage_digest=self._anchor.source_lineage_digest, complete=True, accepted=False,
                     recommended=False, decided=False, approved=False, activated=False, deployed=False,
                     status="RECONCILIATION_SUBMISSION_HOLD_DOCKET_READY_NOT_ACCEPTED_NOT_DECIDED")
            self._docket = HoldDocket(**p, digest=canonical_digest(p)); self._event("SUBMISSION_HOLD_DOCKET_RECORDED", self._docket.digest); return self._docket

    def _control_valid(self, row):
        p = {k:v for k,v in row.__dict__.items() if k != "digest"}
        return isinstance(row.control_id, int) and not isinstance(row.control_id, bool) and 8301 <= row.control_id <= 8700 and self._expected(row.control_id) == (row.workstream, row.aspect) and row.requirement_ref == f"synthetic:submission-lineage-requirement:{(row.control_id-8301)//25:02}" and _hex(row.fixture_digest) and row.expected_result == ("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS") and row.digest == canonical_digest(p)

    def _registry_valid(self): return set(self._controls) == set(range(8301, 8701)) and all(k == v.control_id and self._control_valid(v) for k,v in self._controls.items())
    def _source_roles(self): return self._anchor.source_reviewers + self._anchor.source_compilers + (self._anchor.source_chair, self._anchor.source_validator)
    def _case(self, flow, answer_kind):
        if not self._anchor: return None
        return next((x for x in self._anchor.source_cases if (x.flow, x.answer_kind) == (flow, answer_kind)), None)

    @staticmethod
    def _source_case_valid(row):
        p = ("SOURCE_RECONCILIATION_CASE", row.flow, row.answer_kind, row.comparison_outcome,
             row.source_binding_digest, row.counterpart_binding_digest, row.source_claim_digest,
             row.counterpart_claim_digest, row.source_manifest_digest, row.counterpart_manifest_digest,
             row.source_receipt_digest, row.counterpart_receipt_digest, row.source_version,
             row.counterpart_version, row.comparison_digest, row.queue_route_digest)
        digests = (row.source_binding_digest, row.counterpart_binding_digest, row.source_claim_digest,
                   row.counterpart_claim_digest, row.source_manifest_digest, row.counterpart_manifest_digest,
                   row.source_receipt_digest, row.counterpart_receipt_digest, row.comparison_digest, row.queue_route_digest)
        versions = (row.source_version, row.counterpart_version)
        comparison = canonical_digest(("SOURCE_RECONCILIATION_COMPARISON", row.flow, row.answer_kind,
                                       row.comparison_outcome, row.source_binding_digest, row.counterpart_binding_digest))
        route = canonical_digest(("SOURCE_HUMAN_RECONCILIATION_QUEUE", row.flow, row.answer_kind,
                                  row.comparison_outcome, comparison, *FLOW_PARTIES.get(row.flow,(None,None))))
        return row.flow in FLOWS and row.answer_kind in ANSWER_KINDS and row.comparison_outcome == source_case_outcome(row) and all(_hex(x) for x in digests) and all(isinstance(x,int) and not isinstance(x,bool) and x>0 for x in versions) and row.comparison_digest == comparison and row.queue_route_digest == route and row.case_digest == canonical_digest(p)

    def _anchor_valid(self, row):
        p = {k:v for k,v in row.__dict__.items() if k != "digest"}; roles = row.source_reviewers + row.source_compilers + (row.source_chair, row.source_validator)
        keys = tuple((x.flow, x.answer_kind) for x in row.source_cases)
        lineage = canonical_digest(("RECONCILIATION_QUEUE_FULL_LINEAGE", row.queue_packet_digest, row.case_set_digest,
                                    tuple(x.case_digest for x in row.source_cases), row.source_reviewers, row.source_compilers, row.source_chair, row.source_validator))
        case_set = canonical_digest(tuple(x.case_digest for x in row.source_cases))
        return self._registry_valid() and _syn(row.anchor_id, "submission-lineage-anchor") and all(_hex(x) for x in (row.queue_packet_digest, row.case_set_digest, row.lesson_registry_digest, row.remediation_manifest_digest)) and row.case_set_digest == case_set and row.applied_lesson_ids == APPLIED_LESSONS and row.applied_rule_ids == APPLIED_RULES and keys == tuple((f,k) for f in FLOWS for k in ANSWER_KINDS) and all(self._source_case_valid(x) for x in row.source_cases) and isinstance(row.source_sequence, int) and not isinstance(row.source_sequence,bool) and row.source_sequence > 0 and row.is_latest is True and len(row.source_reviewers) == 3 and all(_syn(x,k) for x,k in zip(row.source_reviewers, ("readiness-reviewer", "preflight-reviewer", "reconsideration-reviewer"))) and len(row.source_compilers) == 4 and all(_syn(x, "packet-compiler") for x in row.source_compilers) and _syn(row.source_chair, "human-deliberation-chair") and _syn(row.source_validator, "cross-party-validator") and len({_identity(x) for x in roles}) == 9 and row.source_lineage_digest == lineage and row.status == "RECONCILIATION_QUEUE_ANCHORED_NOT_ACCEPTED_NOT_DECIDED" and row.digest == canonical_digest(_anchor_payload(p))

    def _submission_valid(self, row, key):
        case = self._case(row.flow, row.answer_kind); expected_party = expected_author(row.flow, row.submission_kind)
        sequence = SUBMISSION_KINDS.index(row.submission_kind) + 1 if row.submission_kind in SUBMISSION_KINDS else 0
        prior = self._submissions.get((row.flow, row.answer_kind, SUBMISSION_KINDS[sequence-2])) if sequence > 1 else None
        parent = None if sequence == 1 else (prior.digest if prior else None)
        occupied = self._source_roles()
        p = {k:v for k,v in row.__dict__.items() if k != "digest"}
        return case is not None and key == (row.flow, row.answer_kind, row.submission_kind) and row.author_party == expected_party and row.source_case_digest == case.case_digest and row.parent_submission_digest == parent and row.content_digest == derived_content(case, row.submission_kind, row.author_party, sequence) and row.sequence == sequence and row.author_identity == f"synthetic:submission-author:{expected_party}" and _syn(row.lineage_validator, "submission-lineage-validator") and len({_identity(x) for x in occupied + (row.author_identity, row.lineage_validator)}) == len(occupied) + 2 and row.nonbinding is True and row.complete is True and row.status == "SUBMISSION_RECORDED_FOR_HUMAN_REVIEW_NOT_ACCEPTED" and row.digest == canonical_digest(p)

    def _bundle_valid(self, row, key):
        case = self._case(row.flow, row.answer_kind); rows = tuple(self._submissions.get((row.flow, row.answer_kind,k)) for k in SUBMISSION_KINDS)
        if case is None or any(x is None for x in rows): return False
        bdigest = canonical_digest(("RECONCILIATION_SUBMISSION_BUNDLE", case.case_digest, *(x.digest for x in rows)))
        route = canonical_digest(("HUMAN_RECONCILIATION_HOLD", row.flow, row.answer_kind, case.comparison_outcome, bdigest))
        occupied = self._source_roles() + tuple(x.author_identity for x in rows) + (rows[0].lineage_validator,)
        p = {k:v for k,v in row.__dict__.items() if k != "digest"}
        return key == (row.flow,row.answer_kind) and row.source_case_digest == case.case_digest and (row.proposal_digest,row.counterargument_digest,row.evidence_digest) == tuple(x.digest for x in rows) and row.bundle_digest == bdigest and row.hold_route_digest == route and _syn(row.bundle_id,"submission-bundle") and _syn(row.bundle_compiler,"submission-bundle-compiler") and _identity(row.bundle_compiler) not in {_identity(x) for x in occupied} and row.lineage_validator == rows[0].lineage_validator and all(x.lineage_validator == row.lineage_validator for x in rows) and row.complete is True and row.held is True and not any((row.accepted,row.recommended,row.decided,row.approved,row.activated)) and row.status == "HELD_FOR_HUMAN_RECONCILIATION_NOT_ACCEPTED_NOT_DECIDED" and row.digest == canonical_digest(p)

    def _event(self, action, artifact):
        prev = self._events[-1]["digest"] if self._events else None; p = dict(sequence=len(self._events)+1, action=action, artifact_digest=artifact, previous_digest=prev); self._events.append({**p,"digest":canonical_digest(p)})
    def _hold(self, reason, artifact):
        prev = self._holds[-1]["digest"] if self._holds else None; p = dict(sequence=len(self._holds)+1, reason=reason, attachment_digest=artifact, previous_digest=prev); self._holds.append({**p,"digest":canonical_digest(p)})
    @staticmethod
    def _chain(chain, event):
        prev = None
        for i,row in enumerate(chain,1):
            keys = ("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest"); p = {k:row.get(k) for k in keys}
            if row != {**p,"digest":canonical_digest(p)} or row["sequence"] != i or row["previous_digest"] != prev: return False
            prev = row["digest"]
        return True

    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events,True) or not self._chain(self._holds,False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._submission_valid(v,k) for k,v in self._submissions.items()) or any(not self._bundle_valid(v,k) for k,v in self._bundles.items()): return False
        if self._docket:
            row = self._docket; p = {k:v for k,v in row.__dict__.items() if k != "digest"}; validators = {x.lineage_validator for x in self._bundles.values()}; bset = canonical_digest(tuple(self._bundles[k].digest for k in sorted(self._bundles)))
            occupied = self._source_roles() + tuple(x.author_identity for x in self._submissions.values()) + tuple(x.bundle_compiler for x in self._bundles.values()) + tuple(validators)
            if len(validators) != 1 or not _syn(row.docket_id,"submission-hold-docket") or row.anchor_digest != self._anchor.digest or row.bundle_set_digest != bset or not _syn(row.docket_compiler,"submission-docket-compiler") or _identity(row.docket_compiler) in {_identity(x) for x in occupied} or row.lineage_validator != next(iter(validators)) or row.source_reviewers != self._anchor.source_reviewers or row.source_compilers != self._anchor.source_compilers or row.source_chair != self._anchor.source_chair or row.source_validator != self._anchor.source_validator or row.source_lineage_digest != self._anchor.source_lineage_digest or row.complete is not True or any((row.accepted,row.recommended,row.decided,row.approved,row.activated,row.deployed)) or row.status != "RECONCILIATION_SUBMISSION_HOLD_DOCKET_READY_NOT_ACCEPTED_NOT_DECIDED" or row.digest != canonical_digest(p): return False
        expected = []
        if self._anchor: expected.append(("RECONCILIATION_QUEUE_ANCHORED",self._anchor.digest))
        expected.extend(("RECONCILIATION_SUBMISSION_RECORDED",x.digest) for x in self._submissions.values())
        expected.extend(("SUBMISSION_BUNDLE_HELD",x.digest) for x in self._bundles.values())
        if self._docket: expected.append(("SUBMISSION_HOLD_DOCKET_RECORDED",self._docket.digest))
        return [(x["action"],x["artifact_digest"]) for x in self._events] == expected and [(x["reason"],x["attachment_digest"]) for x in self._holds] == [("HUMAN_RECONCILIATION_REQUIRED",x.digest) for x in self._bundles.values()]

    def evidence(self):
        ok = self._integrity(); complete = len(self._submissions)==60 and len(self._bundles)==20 and self._docket is not None
        return {"range":[8301,8700],"control_count":400,"workstream_count":16,"controls_per_workstream":25,
                "control_matrix_valid":WORKSTREAMS==tuple((8301+i*25,8325+i*25,n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS)==25,
                "registered_control_count":len(self._controls),"submission_count":len(self._submissions),"bundle_count":len(self._bundles),"hold_count":len(self._holds),"event_count":len(self._events),"integrity_valid":ok,"complete_submission_hold_evidence":complete and ok,
                "maximum_state":"RECONCILIATION_SUBMISSION_HOLD_DOCKET_READY_NOT_ACCEPTED_NOT_DECIDED" if self._docket else "SUBMISSION_HOLD_INCOMPLETE",
                "applied_lesson_ids":list(APPLIED_LESSONS),"applied_rule_ids":list(APPLIED_RULES),
                "external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,"card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,"transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,"policy_prompt_weight_changes":0,
                "accepted":False,"recommended":False,"decided":False,"approved":False,"activated":False}
