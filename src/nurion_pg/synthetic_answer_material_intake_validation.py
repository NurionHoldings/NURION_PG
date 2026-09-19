"""Synthetic/in-memory answer and supporting-material intake controls #7501-#7900."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "QUESTION_DOCKET_SOURCE_ANCHOR", "LESSON_RULE_REGISTRY_BINDING", "TENANT_ANSWER_DOCUMENT",
    "NURION_ANSWER_DOCUMENT", "UPSTREAM_ANSWER_DOCUMENT", "FOUR_DIRECTION_ANSWER_ROUTE",
    "ANSWER_SCHEMA_VALIDATION", "SUPPORTING_MATERIAL_PROVENANCE", "DOCUMENT_VERSION_SEQUENCE",
    "ANSWER_MATERIAL_COMPLETENESS", "SEMANTIC_CONFLICT_DETECTION", "RECEIPT_LINEAGE",
    "REVIEWER_COMPILER_CHAIR_LINEAGE", "APPEND_ONLY_INTAKE_HOLD", "INDEPENDENT_INTAKE_VALIDATION",
    "NON_ACCEPTANCE_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((7501+i*25, 7525+i*25, n) for i, n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type", "tenant_scope", "role_scope",
    "state_precondition", "latest_sequence", "source_binding", "digest_recalculation", "negative_path",
    "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "concurrency",
    "partial_batch", "ordering", "append_only", "hold_propagation", "review_independence",
    "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})
PARTIES = ("TENANT_AGENCY", "NURION_PG", "UPSTREAM_PG")
FLOWS = ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")
FLOW_PARTIES = {"tenant_to_nurion": ("TENANT_AGENCY", "NURION_PG"), "nurion_to_upstream": ("NURION_PG", "UPSTREAM_PG"), "upstream_to_nurion": ("UPSTREAM_PG", "NURION_PG"), "nurion_to_tenant": ("NURION_PG", "TENANT_AGENCY")}
ANSWER_KINDS = ("ASSUMPTION_RESPONSE", "RESIDUAL_RISK_RESPONSE", "ADDITIONAL_EVIDENCE", "MEANING_CLARIFICATION", "SAFE_BOUNDARY_ACKNOWLEDGEMENT")
APPLIED_LESSONS = ("ARL-3901-001", "ARL-4301-001", "ARL-4301-002", "ARL-4301-003", "ARL-4701-001", "ARL-5101-001", "ARL-5501-001", "ARL-5901-001", "ARL-6301-001", "ARL-6701-001", "ARL-7101-001", "ARL-7501-001")
APPLIED_RULES = tuple(f"ARP-{i:02}" for i in range(1, 9))

def _syn(v, kind): return isinstance(v, str) and v.startswith(f"synthetic:{kind}:")
def _hex(v): return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
def _identity(v): return v.rsplit(":", 1)[-1].casefold()

@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str; fixture_digest: str; expected_result: str; digest: str

@dataclass(frozen=True)
class QuestionDocketAnchor:
    anchor_id: str; question_docket_digest: str; question_set_digest: str; lesson_registry_digest: str; remediation_manifest_digest: str
    applied_lesson_ids: tuple[str, ...]; applied_rule_ids: tuple[str, ...]; party_document_digests: tuple[tuple[str, str], ...]
    route_binding_digests: tuple[tuple[str, str], ...]; source_sequence: int; is_latest: bool; source_reviewers: tuple[str, str, str]
    source_compilers: tuple[str, str, str]; source_chair: str; source_lineage_digest: str; status: str; digest: str

@dataclass(frozen=True)
class AnswerMaterial:
    intake_id: str; flow: str; kind: str; source_party: str; counterparty: str; anchor_digest: str
    source_document_digest: str; route_binding_digest: str; question_digest: str; answer_document_digest: str
    material_manifest_digest: str; source_receipt_digest: str; document_version: int; previous_version_digest: str | None
    semantic_claim_digest: str; submitter: str; intake_reviewer: str; complete: bool; conflict_free: bool; status: str; digest: str

@dataclass(frozen=True)
class IntakeValidationPacket:
    packet_id: str; anchor_digest: str; answer_set_digest: str; validator: str; source_reviewers: tuple[str, str, str]
    source_compilers: tuple[str, str, str]; source_chair: str; source_lineage_digest: str; complete: bool
    accepted: bool; transmitted: bool; signed: bool; recommended: bool; decided: bool; approved: bool; activated: bool
    deployed: bool; status: str; digest: str

class SyntheticAnswerMaterialIntakeValidation:
    """Validates inert synthetic answer packages without receiving or accepting external answers."""
    def __init__(self):
        self._controls = {}; self._anchor = None; self._answers = {}; self._packet = None
        self._events = []; self._holds = []; self._lock = RLock()

    def _expected(self, cid):
        i = cid-7501; return WORKSTREAM_NAMES[i//25], CONTROL_ASPECTS[i%25]

    def add_control(self, cid, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        p = dict(control_id=cid, workstream=workstream, aspect=aspect, requirement_ref=requirement_ref, fixture_digest=fixture_digest, expected_result=expected_result)
        r = Control(**p, digest=canonical_digest(p))
        with self._lock:
            if not self._valid_control(r): raise GovernanceRejected("valid #7501-#7900 control required")
            old = self._controls.get(cid)
            if old:
                if old == r: return old
                raise GovernanceRejected("control conflict")
            self._controls[cid] = r; return r

    def anchor_source(self, anchor_id, question_docket_digest, question_set_digest, lesson_registry_digest,
                      remediation_manifest_digest, applied_lesson_ids, applied_rule_ids, party_document_digests,
                      route_binding_digests, source_sequence, is_latest, source_reviewers, source_compilers, source_chair):
        reviewers, compilers = tuple(source_reviewers), tuple(source_compilers)
        lineage = canonical_digest(("QUESTION_DOCKET_FULL_LINEAGE", question_docket_digest, question_set_digest, reviewers, compilers, source_chair))
        p = dict(anchor_id=anchor_id, question_docket_digest=question_docket_digest, question_set_digest=question_set_digest,
                 lesson_registry_digest=lesson_registry_digest, remediation_manifest_digest=remediation_manifest_digest,
                 applied_lesson_ids=tuple(applied_lesson_ids), applied_rule_ids=tuple(applied_rule_ids),
                 party_document_digests=tuple(party_document_digests), route_binding_digests=tuple(route_binding_digests),
                 source_sequence=source_sequence, is_latest=is_latest, source_reviewers=reviewers,
                 source_compilers=compilers, source_chair=source_chair, source_lineage_digest=lineage,
                 status="QUESTION_DOCKET_ANCHORED_NOT_ANSWERED_NOT_DECIDED")
        r = QuestionDocketAnchor(**p, digest=canonical_digest(p))
        with self._lock:
            if not self._anchor_valid(r): raise GovernanceRejected("latest complete question docket lineage required")
            if self._anchor:
                if self._anchor == r: return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor = r; self._event("QUESTION_DOCKET_ANCHORED", r.digest); return r

    def add_answer_material(self, intake_id, flow, kind, question_digest, answer_document_digest,
                            material_manifest_digest, source_receipt_digest, document_version,
                            previous_version_digest, semantic_claim_digest, submitter, intake_reviewer,
                            complete=True, conflict_free=True):
        with self._lock:
            if not self._anchor: raise GovernanceRejected("question docket anchor required")
            source, counter = FLOW_PARTIES.get(flow, (None, None)); docs = dict(self._anchor.party_document_digests)
            route = dict(self._anchor.route_binding_digests).get(flow)
            p = dict(intake_id=intake_id, flow=flow, kind=kind, source_party=source, counterparty=counter,
                     anchor_digest=self._anchor.digest, source_document_digest=docs.get(source), route_binding_digest=route,
                     question_digest=question_digest, answer_document_digest=answer_document_digest,
                     material_manifest_digest=material_manifest_digest, source_receipt_digest=source_receipt_digest,
                     document_version=document_version, previous_version_digest=previous_version_digest,
                     semantic_claim_digest=semantic_claim_digest, submitter=submitter, intake_reviewer=intake_reviewer,
                     complete=complete, conflict_free=conflict_free, status="ANSWER_MATERIAL_HELD_FOR_INDEPENDENT_VALIDATION")
            r = AnswerMaterial(**p, digest=canonical_digest(p)); key = (flow, kind)
            if not self._answer_valid(r, key): raise GovernanceRejected("complete conflict-free synthetic answer material required")
            old = self._answers.get(key)
            if old:
                if old == r: return old
                raise GovernanceRejected("answer material conflict")
            self._answers[key] = r; self._event("ANSWER_MATERIAL_RECORDED", r.digest); self._hold("EXTERNAL_ACCEPTANCE_AND_HUMAN_DECISION_REQUIRED", r.digest); return r

    def finalize(self, packet_id, validator):
        with self._lock:
            if self._packet or set(self._answers) != {(f, k) for f in FLOWS for k in ANSWER_KINDS} or not self._integrity():
                raise GovernanceRejected("exact intact answer-material set required")
            if not _syn(packet_id, "answer-intake-packet") or not _syn(validator, "intake-validator"):
                raise GovernanceRejected("synthetic independent validator required")
            occupied = self._all_source_roles() + tuple(x.submitter for x in self._answers.values()) + tuple(x.intake_reviewer for x in self._answers.values())
            if _identity(validator) in {_identity(x) for x in occupied}: raise GovernanceRejected("independent validator required")
            aset = canonical_digest(tuple(self._answers[k].digest for k in sorted(self._answers)))
            p = dict(packet_id=packet_id, anchor_digest=self._anchor.digest, answer_set_digest=aset, validator=validator,
                     source_reviewers=self._anchor.source_reviewers, source_compilers=self._anchor.source_compilers,
                     source_chair=self._anchor.source_chair, source_lineage_digest=self._anchor.source_lineage_digest,
                     complete=True, accepted=False, transmitted=False, signed=False, recommended=False, decided=False,
                     approved=False, activated=False, deployed=False,
                     status="ANSWER_MATERIAL_VALIDATION_READY_NOT_ACCEPTED_NOT_DECIDED")
            self._packet = IntakeValidationPacket(**p, digest=canonical_digest(p)); self._event("INTAKE_VALIDATION_PACKET_RECORDED", self._packet.digest); return self._packet

    def _valid_control(self, r):
        p = {k:v for k,v in r.__dict__.items() if k != "digest"}
        return isinstance(r.control_id, int) and not isinstance(r.control_id, bool) and 7501 <= r.control_id <= 7900 and self._expected(r.control_id) == (r.workstream, r.aspect) and r.requirement_ref == f"synthetic:answer-intake-requirement:{(r.control_id-7501)//25:02}" and _hex(r.fixture_digest) and r.expected_result == ("EXPECTED_REJECTION" if r.aspect in NEGATIVE else "PASS") and r.digest == canonical_digest(p)

    def _registry_valid(self):
        return set(self._controls) == set(range(7501, 7901)) and all(k == v.control_id and self._valid_control(v) for k, v in self._controls.items())

    def _all_source_roles(self):
        return self._anchor.source_reviewers + self._anchor.source_compilers + (self._anchor.source_chair,)

    def _anchor_valid(self, a):
        p = {k:v for k,v in a.__dict__.items() if k != "digest"}; docs = dict(a.party_document_digests)
        routes = tuple((f, canonical_digest(("ANSWER_INTAKE_ROUTE", f, FLOW_PARTIES[f], tuple(a.party_document_digests), a.question_docket_digest, a.question_set_digest))) for f in FLOWS)
        roles = a.source_reviewers + a.source_compilers + (a.source_chair,)
        return self._registry_valid() and _syn(a.anchor_id, "answer-intake-anchor") and all(_hex(x) for x in (a.question_docket_digest, a.question_set_digest, a.lesson_registry_digest, a.remediation_manifest_digest)) and a.applied_lesson_ids == APPLIED_LESSONS and a.applied_rule_ids == APPLIED_RULES and tuple(x for x,_ in a.party_document_digests) == PARTIES and len(docs) == 3 and all(_hex(x) for x in docs.values()) and a.route_binding_digests == routes and isinstance(a.source_sequence, int) and not isinstance(a.source_sequence, bool) and a.source_sequence > 0 and a.is_latest is True and len(a.source_reviewers) == 3 and all(_syn(x,k) for x,k in zip(a.source_reviewers, ("readiness-reviewer", "preflight-reviewer", "reconsideration-reviewer"))) and len(a.source_compilers) == 3 and all(_syn(x, "packet-compiler") for x in a.source_compilers) and _syn(a.source_chair, "human-deliberation-chair") and len({_identity(x) for x in roles}) == 7 and a.source_lineage_digest == canonical_digest(("QUESTION_DOCKET_FULL_LINEAGE", a.question_docket_digest, a.question_set_digest, a.source_reviewers, a.source_compilers, a.source_chair)) and a.status == "QUESTION_DOCKET_ANCHORED_NOT_ANSWERED_NOT_DECIDED" and a.digest == canonical_digest(p)

    def _answer_valid(self, r, key):
        if not self._anchor: return False
        p = {k:v for k,v in r.__dict__.items() if k != "digest"}; source, counter = FLOW_PARTIES.get(r.flow, (None, None))
        doc = dict(self._anchor.party_document_digests).get(source); route = dict(self._anchor.route_binding_digests).get(r.flow)
        question = canonical_digest(("SOURCE_QUESTION", self._anchor.question_set_digest, r.flow, r.kind, source, counter, route))
        claim = canonical_digest(("SYNTHETIC_SEMANTIC_CLAIM", question, source, counter, doc, route))
        manifest = canonical_digest(("SYNTHETIC_MATERIAL_MANIFEST", question, source, counter, claim, route, r.document_version))
        answer = canonical_digest(("SYNTHETIC_ANSWER_DOCUMENT", question, source, counter, r.document_version, r.semantic_claim_digest, r.material_manifest_digest))
        receipt = canonical_digest(("SYNTHETIC_SOURCE_RECEIPT", source, r.flow, r.kind, answer, r.material_manifest_digest, r.document_version, r.previous_version_digest))
        return key == (r.flow, r.kind) and r.flow in FLOWS and r.kind in ANSWER_KINDS and _syn(r.intake_id, "answer-material") and (r.source_party, r.counterparty) == (source, counter) and r.anchor_digest == self._anchor.digest and r.source_document_digest == doc and r.route_binding_digest == route and r.question_digest == question and r.semantic_claim_digest == claim and r.material_manifest_digest == manifest and r.answer_document_digest == answer and r.source_receipt_digest == receipt and r.document_version == 1 and r.previous_version_digest is None and r.submitter == f"synthetic:answer-submitter:{source}" and r.intake_reviewer == f"synthetic:intake-reviewer:{counter}" and _identity(r.submitter) != _identity(r.intake_reviewer) and r.complete is True and r.conflict_free is True and r.status == "ANSWER_MATERIAL_HELD_FOR_INDEPENDENT_VALIDATION" and r.digest == canonical_digest(p)

    def _event(self, action, artifact):
        prev = self._events[-1]["digest"] if self._events else None; p = dict(sequence=len(self._events)+1, action=action, artifact_digest=artifact, previous_digest=prev); self._events.append({**p, "digest":canonical_digest(p)})
    def _hold(self, reason, artifact):
        prev = self._holds[-1]["digest"] if self._holds else None; p = dict(sequence=len(self._holds)+1, reason=reason, attachment_digest=artifact, previous_digest=prev); self._holds.append({**p, "digest":canonical_digest(p)})
    @staticmethod
    def _chain(chain, event):
        prev = None
        for i, x in enumerate(chain, 1):
            keys = ("sequence", "action", "artifact_digest", "previous_digest") if event else ("sequence", "reason", "attachment_digest", "previous_digest"); p = {k:x.get(k) for k in keys}
            if x != {**p, "digest":canonical_digest(p)} or x["sequence"] != i or x["previous_digest"] != prev: return False
            prev = x["digest"]
        return True

    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events, True) or not self._chain(self._holds, False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._answer_valid(v,k) for k,v in self._answers.items()): return False
        if self._packet:
            r = self._packet; p = {k:v for k,v in r.__dict__.items() if k != "digest"}; aset = canonical_digest(tuple(self._answers[k].digest for k in sorted(self._answers)))
            occupied = self._all_source_roles() + tuple(x.submitter for x in self._answers.values()) + tuple(x.intake_reviewer for x in self._answers.values())
            if not _syn(r.packet_id, "answer-intake-packet") or r.anchor_digest != self._anchor.digest or r.answer_set_digest != aset or not _syn(r.validator, "intake-validator") or _identity(r.validator) in {_identity(x) for x in occupied} or r.source_reviewers != self._anchor.source_reviewers or r.source_compilers != self._anchor.source_compilers or r.source_chair != self._anchor.source_chair or r.source_lineage_digest != self._anchor.source_lineage_digest or not r.complete or any((r.accepted, r.transmitted, r.signed, r.recommended, r.decided, r.approved, r.activated, r.deployed)) or r.status != "ANSWER_MATERIAL_VALIDATION_READY_NOT_ACCEPTED_NOT_DECIDED" or r.digest != canonical_digest(p): return False
        expected = []
        if self._anchor: expected.append(("QUESTION_DOCKET_ANCHORED", self._anchor.digest))
        expected.extend(("ANSWER_MATERIAL_RECORDED", x.digest) for x in self._answers.values())
        if self._packet: expected.append(("INTAKE_VALIDATION_PACKET_RECORDED", self._packet.digest))
        return [(x["action"], x["artifact_digest"]) for x in self._events] == expected and [(x["reason"], x["attachment_digest"]) for x in self._holds] == [("EXTERNAL_ACCEPTANCE_AND_HUMAN_DECISION_REQUIRED", x.digest) for x in self._answers.values()]

    def evidence(self):
        ok = self._integrity(); complete = len(self._answers) == 20 and self._packet is not None
        matrix = WORKSTREAMS == tuple((7501+i*25, 7525+i*25, n) for i,n in enumerate(WORKSTREAM_NAMES)) and len(CONTROL_ASPECTS) == 25
        return {"range":[7501,7900], "control_count":400, "workstream_count":16, "controls_per_workstream":25,
                "control_matrix_valid":matrix, "registered_control_count":len(self._controls), "answer_material_count":len(self._answers),
                "hold_count":len(self._holds), "event_count":len(self._events), "integrity_valid":ok,
                "complete_answer_material_validation_evidence":complete and ok,
                "maximum_state":"ANSWER_MATERIAL_VALIDATION_READY_NOT_ACCEPTED_NOT_DECIDED" if self._packet else "ANSWER_MATERIAL_VALIDATION_INCOMPLETE",
                "applied_lesson_ids":list(APPLIED_LESSONS), "applied_rule_ids":list(APPLIED_RULES),
                "external_calls":0, "external_answer_receipts":0, "document_transmissions":0, "electronic_signatures":0,
                "external_pg_calls":0, "card_network_calls":0, "payment_approvals":0, "cancellations":0, "refunds":0,
                "settlements":0, "transfers":0, "ledger_writes":0, "credential_reads":0, "deployments":0,
                "policy_prompt_weight_changes":0, "accepted":False, "recommended":False, "decided":False,
                "approved":False, "activated":False}
