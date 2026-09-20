"""Synthetic rebuttal/correction submission validation controls #10301-#10700."""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest

WORKSTREAM_NAMES = (
    "SOURCE_REVIEW_DOCKET_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "SOURCE_REVIEW_SEMANTIC_RECONSTRUCTION", "NO_SUBMISSION_MARKER_PRESERVATION",
    "REBUTTAL_DOCUMENT_PROJECTION", "CORRECTION_DOCUMENT_PROJECTION",
    "SUBMITTER_PARTY_DERIVATION", "SUBMISSION_RECEIPT_BINDING",
    "IMMEDIATE_PARENT_SUBMISSION_LINEAGE", "SOURCE_ACTOR_NAMESPACE_PROJECTION",
    "SUBMISSION_VALIDATOR_SEPARATION", "ROUTE_DOCUMENT_CONSISTENCY",
    "APPEND_ONLY_SUBMISSION_EVENT", "UNRESOLVED_REVIEW_HOLD_CHAIN",
    "PARTIAL_BATCH_FAIL_CLOSED", "NON_RESOLUTION_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((10301+i*25, 10325+i*25, n) for i, n in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type", "tenant_scope",
    "role_scope", "state_precondition", "latest_sequence", "source_binding",
    "digest_recalculation", "negative_path", "missing_input", "duplicate_input", "replay",
    "conflict", "stale_version", "concurrency", "partial_batch", "ordering", "append_only",
    "hold_propagation", "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})
FLOWS = ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")
ANSWER_KINDS = ("ASSUMPTION_RESPONSE", "RESIDUAL_RISK_RESPONSE", "ADDITIONAL_EVIDENCE", "MEANING_CLARIFICATION", "SAFE_BOUNDARY_ACKNOWLEDGEMENT")
ROUTES = ("NOT_APPLICABLE_PRESERVED", "REBUTTAL_OPPORTUNITY_REQUIRED", "REBUTTAL_OPPORTUNITY_REQUIRED", "CORRECTION_REQUEST_REQUIRED", "CORRECTION_REQUEST_REQUIRED")
RESPONDER = {"tenant_to_nurion": "TENANT_AGENCY", "nurion_to_upstream": "NURION_PG", "upstream_to_nurion": "UPSTREAM_PG", "nurion_to_tenant": "NURION_PG"}
APPLIED_LESSONS = (
    "ARL-10301-001", "ARL-10701-001", "ARL-11101-001", "ARL-3901-001", "ARL-4301-001", "ARL-4301-002", "ARL-4301-003", "ARL-4701-001",
    "ARL-5101-001", "ARL-5501-001", "ARL-5901-001", "ARL-6301-001", "ARL-6701-001",
    "ARL-7101-001", "ARL-7501-001", "ARL-7901-001", "ARL-8301-001", "ARL-8701-001",
    "ARL-9101-001", "ARL-9501-001", "ARL-9901-001",
)
APPLIED_RULES = tuple(f"ARP-{i:02}" for i in range(1, 9))

def _syn(value, kind): return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
def _identity(value): return value.rsplit(":", 1)[-1].casefold()
CASE_KEYS = tuple((f, k) for f in FLOWS for k in ANSWER_KINDS)
def _keys(): return CASE_KEYS

@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str
    fixture_digest: str; expected_result: str; digest: str

@dataclass(frozen=True)
class SourceReview:
    review_id: str; flow: str; answer_kind: str; source_intake_digest: str; route: str
    reviewer: str | None; route_custodian: str | None; parent_review_digest: str | None
    position: int; held: bool; resolved: bool; recommended: bool; accepted: bool; digest: str

@dataclass(frozen=True)
class Anchor:
    anchor_id: str; source_docket_digest: str; review_set_digest: str
    lesson_registry_digest: str; remediation_manifest_digest: str
    applied_lesson_ids: tuple[str, ...]; applied_rule_ids: tuple[str, ...]
    source_reviews: tuple[SourceReview, ...]; source_compiler: str; source_validator: str
    source_lineage_digest: str; source_sequence: int; is_latest: bool; status: str; digest: str

@dataclass(frozen=True)
class Submission:
    submission_id: str; flow: str; answer_kind: str; source_review_digest: str; route: str
    submitter_party: str | None; document_digest: str | None; receipt_digest: str | None
    marker: str; parent_submission_digest: str | None; position: int; held: bool
    validated: bool; resolved: bool; accepted: bool; digest: str

@dataclass(frozen=True)
class Docket:
    docket_id: str; anchor_digest: str; submission_set_digest: str; compiler: str; validator: str
    source_lineage_digest: str; complete: bool; held: bool; resolved: bool; recommended: bool
    accepted: bool; approved: bool; activated: bool; deployed: bool; status: str; digest: str

def review_digest(review):
    return canonical_digest({k: v for k, v in review.__dict__.items() if k != "digest"})

def submission_digest(flow, kind, review, route, submitter, document, receipt, marker, parent, position):
    return canonical_digest(("REBUTTAL_CORRECTION_SUBMISSION", flow, kind, review, route, submitter, document, receipt, marker, parent, position))

def derived_receipt_digest(flow, kind, source_review_digest, route, submitter, document_digest):
    return canonical_digest(("SUBMISSION_RECEIPT", flow, kind, source_review_digest, route, submitter, document_digest))

def _anchor_payload(payload):
    payload = dict(payload)
    payload["source_reviews"] = tuple(tuple(x.__dict__.values()) for x in payload["source_reviews"])
    return payload

class SyntheticRebuttalCorrectionSubmissionValidation:
    def __init__(self):
        self._controls = {}; self._anchor = None; self._submissions = {}; self._docket = None
        self._events = []; self._holds = []; self._lock = RLock()

    def _expected(self, control_id):
        i = control_id - 10301
        return WORKSTREAM_NAMES[i//25], CONTROL_ASPECTS[i%25]

    def add_control(self, control_id, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        payload = dict(control_id=control_id, workstream=workstream, aspect=aspect, requirement_ref=requirement_ref, fixture_digest=fixture_digest, expected_result=expected_result)
        row = Control(**payload, digest=canonical_digest(payload))
        with self._lock:
            if not self._control_valid(row): raise GovernanceRejected("valid #10301-#10700 control required")
            old = self._controls.get(control_id)
            if old:
                if old == row: return old
                raise GovernanceRejected("control conflict")
            self._controls[control_id] = row
            return row

    def anchor(self, anchor_id, source_docket_digest, review_set_digest, registry_digest, manifest_digest,
               lessons, rules, reviews, source_compiler, source_validator, sequence, is_latest):
        reviews = tuple(reviews)
        lineage = canonical_digest(("RESPONSE_REVIEW_FULL_LINEAGE", source_docket_digest, review_set_digest, tuple(x.digest for x in reviews), source_compiler, source_validator))
        payload = dict(anchor_id=anchor_id, source_docket_digest=source_docket_digest, review_set_digest=review_set_digest,
                       lesson_registry_digest=registry_digest, remediation_manifest_digest=manifest_digest,
                       applied_lesson_ids=tuple(lessons), applied_rule_ids=tuple(rules), source_reviews=reviews,
                       source_compiler=source_compiler, source_validator=source_validator,
                       source_lineage_digest=lineage, source_sequence=sequence, is_latest=is_latest,
                       status="RESPONSE_REVIEW_DOCKET_ANCHORED_ON_HOLD_NOT_SUBMITTED")
        row = Anchor(**payload, digest=canonical_digest(_anchor_payload(payload)))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("complete latest response review docket required")
            if self._anchor:
                if self._anchor == row: return row
                raise GovernanceRejected("anchor conflict")
            self._anchor = row; self._event("RESPONSE_REVIEW_DOCKET_ANCHORED", row.digest)
            return row

    def add_submission(self, submission_id, flow, kind, document_digest=None, receipt_digest=None):
        with self._lock:
            keys = _keys(); key = (flow, kind)
            if not self._anchor or key not in keys: raise GovernanceRejected("anchored source review required")
            pos = keys.index(key); source = self._anchor.source_reviews[pos]; route = ROUTES[pos % 5]
            previous = None if pos == 0 else self._submissions.get(keys[pos-1])
            if pos and previous is None: raise GovernanceRejected("immediate prior submission required")
            if route == "NOT_APPLICABLE_PRESERVED":
                if document_digest is not None or receipt_digest is not None: raise GovernanceRejected("N/A forbids submission material")
                submitter = None; marker = "NO_SUBMISSION_REQUIRED"
            else:
                if not _hex(document_digest) or not _hex(receipt_digest): raise GovernanceRejected("document and receipt required")
                submitter = RESPONDER[flow]; marker = "SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
                if receipt_digest != derived_receipt_digest(flow, kind, source.digest, route, submitter, document_digest):
                    raise GovernanceRejected("receipt must be derived from submission semantics")
            parent = None if previous is None else previous.digest
            digest = submission_digest(flow, kind, source.digest, route, submitter, document_digest, receipt_digest, marker, parent, pos+1)
            row = Submission(submission_id, flow, kind, source.digest, route, submitter, document_digest,
                             receipt_digest, marker, parent, pos+1, True, True, False, False, digest)
            if not self._submission_valid(row, key): raise GovernanceRejected("valid derived submission required")
            old = self._submissions.get(key)
            if old:
                if old == row: return old
                raise GovernanceRejected("submission conflict")
            self._submissions[key] = row; self._event("SUBMISSION_VALIDATED", row.digest)
            if route != "NOT_APPLICABLE_PRESERVED": self._hold("HUMAN_REVIEW_REQUIRED", row.digest)
            return row

    def finalize(self, docket_id, compiler, validator):
        with self._lock:
            if self._docket or tuple(self._submissions) != _keys() or not self._integrity():
                raise GovernanceRejected("complete intact submissions required")
            actors = tuple(x for r in self._anchor.source_reviews for x in (r.reviewer, r.route_custodian) if x)
            actors += (self._anchor.source_compiler, self._anchor.source_validator, compiler, validator)
            if not _syn(compiler, "submission-docket-compiler") or not _syn(validator, "submission-docket-validator") or len({_identity(x) for x in actors}) != len(actors):
                raise GovernanceRejected("independent final actors required")
            submission_set = canonical_digest(tuple(self._submissions[k].digest for k in _keys()))
            payload = dict(docket_id=docket_id, anchor_digest=self._anchor.digest, submission_set_digest=submission_set,
                           compiler=compiler, validator=validator, source_lineage_digest=self._anchor.source_lineage_digest,
                           complete=True, held=True, resolved=False, recommended=False, accepted=False, approved=False,
                           activated=False, deployed=False,
                           status="REBUTTAL_CORRECTION_SUBMISSIONS_VALIDATED_ON_HOLD_NOT_RESOLVED")
            row = Docket(**payload, digest=canonical_digest(payload)); self._docket = row
            self._event("REBUTTAL_CORRECTION_SUBMISSION_DOCKET_HELD", row.digest)
            return row

    def _control_valid(self, row):
        payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
        return isinstance(row.control_id, int) and not isinstance(row.control_id, bool) and 10301 <= row.control_id <= 10700 and self._expected(row.control_id) == (row.workstream, row.aspect) and row.requirement_ref == f"synthetic:submission-validation-requirement:{(row.control_id-10301)//25:02}" and _hex(row.fixture_digest) and row.expected_result == ("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS") and row.digest == canonical_digest(payload)

    def _registry_valid(self):
        return set(self._controls) == set(range(10301, 10701)) and all(k == v.control_id and self._control_valid(v) for k, v in self._controls.items())

    def _source_review_valid(self, row, pos, reviews):
        flow, kind = _keys()[pos]; route = ROUTES[pos % 5]; previous = None if pos == 0 else reviews[pos-1].digest
        actor_ok = (row.reviewer is None and row.route_custodian is None) if route == "NOT_APPLICABLE_PRESERVED" else (
            _syn(row.reviewer, "response-independent-reviewer") and
            _syn(row.route_custodian, "rebuttal-custodian" if route == "REBUTTAL_OPPORTUNITY_REQUIRED" else "correction-request-compiler"))
        return _syn(row.review_id, "response-review") and (row.flow, row.answer_kind) == (flow, kind) and _hex(row.source_intake_digest) and row.route == route and actor_ok and row.parent_review_digest == previous and row.position == pos+1 and row.held is True and not any((row.resolved, row.recommended, row.accepted)) and row.digest == review_digest(row)

    def _anchor_valid(self, row):
        payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
        review_set = canonical_digest(tuple(x.digest for x in row.source_reviews))
        docket = canonical_digest(("RESPONSE_REVIEW_REBUTTAL_CORRECTION_DOCKET_SOURCE", review_set, row.source_compiler, row.source_validator))
        lineage = canonical_digest(("RESPONSE_REVIEW_FULL_LINEAGE", row.source_docket_digest, row.review_set_digest, tuple(x.digest for x in row.source_reviews), row.source_compiler, row.source_validator))
        actors = tuple(x for r in row.source_reviews for x in (r.reviewer, r.route_custodian) if x) + (row.source_compiler, row.source_validator)
        return self._registry_valid() and _syn(row.anchor_id, "submission-validation-anchor") and len(row.source_reviews) == 20 and all(self._source_review_valid(x, i, row.source_reviews) for i, x in enumerate(row.source_reviews)) and row.review_set_digest == review_set and row.source_docket_digest == docket and _hex(row.lesson_registry_digest) and _hex(row.remediation_manifest_digest) and row.applied_lesson_ids == APPLIED_LESSONS and row.applied_rule_ids == APPLIED_RULES and _syn(row.source_compiler, "review-docket-compiler") and _syn(row.source_validator, "review-docket-validator") and len({_identity(x) for x in actors}) == len(actors) and row.source_lineage_digest == lineage and isinstance(row.source_sequence, int) and not isinstance(row.source_sequence, bool) and row.source_sequence > 0 and row.is_latest is True and row.status == "RESPONSE_REVIEW_DOCKET_ANCHORED_ON_HOLD_NOT_SUBMITTED" and row.digest == canonical_digest(_anchor_payload(payload))

    def _submission_valid(self, row, key):
        if not self._anchor or key not in _keys(): return False
        pos = _keys().index(key); source = self._anchor.source_reviews[pos]; route = ROUTES[pos % 5]
        previous = None if pos == 0 else self._submissions.get(_keys()[pos-1])
        if route == "NOT_APPLICABLE_PRESERVED": material_ok = row.submitter_party is None and row.document_digest is None and row.receipt_digest is None and row.marker == "NO_SUBMISSION_REQUIRED"
        else: material_ok = row.submitter_party == RESPONDER[row.flow] and _hex(row.document_digest) and row.receipt_digest == derived_receipt_digest(row.flow, row.answer_kind, source.digest, route, row.submitter_party, row.document_digest) and row.marker == "SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        expected = submission_digest(row.flow, row.answer_kind, source.digest, route, row.submitter_party, row.document_digest, row.receipt_digest, row.marker, None if previous is None else previous.digest, pos+1)
        return _syn(row.submission_id, "rebuttal-correction-submission") and (row.flow, row.answer_kind) == key and row.source_review_digest == source.digest and row.route == route and material_ok and row.parent_submission_digest == (None if previous is None else previous.digest) and row.position == pos+1 and row.held is True and row.validated is True and not any((row.resolved, row.accepted)) and row.digest == expected

    def _event(self, action, artifact):
        previous = self._events[-1]["digest"] if self._events else None
        payload = dict(sequence=len(self._events)+1, action=action, artifact_digest=artifact, previous_digest=previous)
        self._events.append({**payload, "digest": canonical_digest(payload)})

    def _hold(self, reason, artifact):
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = dict(sequence=len(self._holds)+1, reason=reason, attachment_digest=artifact, previous_digest=previous)
        self._holds.append({**payload, "digest": canonical_digest(payload)})

    @staticmethod
    def _chain(rows, event):
        previous = None
        for i, row in enumerate(rows, 1):
            keys = ("sequence", "action", "artifact_digest", "previous_digest") if event else ("sequence", "reason", "attachment_digest", "previous_digest")
            payload = {k: row.get(k) for k in keys}
            if row != {**payload, "digest": canonical_digest(payload)} or row["sequence"] != i or row["previous_digest"] != previous: return False
            previous = row["digest"]
        return True

    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events, True) or not self._chain(self._holds, False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._submission_valid(v, k) for k, v in self._submissions.items()): return False
        expected_events = []
        if self._anchor: expected_events.append(("RESPONSE_REVIEW_DOCKET_ANCHORED", self._anchor.digest))
        expected_events.extend(("SUBMISSION_VALIDATED", x.digest) for x in self._submissions.values())
        if self._docket: expected_events.append(("REBUTTAL_CORRECTION_SUBMISSION_DOCKET_HELD", self._docket.digest))
        expected_holds = [("HUMAN_REVIEW_REQUIRED", x.digest) for x in self._submissions.values() if x.route != "NOT_APPLICABLE_PRESERVED"]
        if [(x["action"], x["artifact_digest"]) for x in self._events] != expected_events or [(x["reason"], x["attachment_digest"]) for x in self._holds] != expected_holds: return False
        if self._docket:
            row = self._docket; payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
            actors = tuple(x for r in self._anchor.source_reviews for x in (r.reviewer, r.route_custodian) if x) + (self._anchor.source_compiler, self._anchor.source_validator, row.compiler, row.validator)
            if not _syn(row.docket_id, "submission-validation-docket") or row.anchor_digest != self._anchor.digest or row.submission_set_digest != canonical_digest(tuple(self._submissions[k].digest for k in _keys())) or not _syn(row.compiler, "submission-docket-compiler") or not _syn(row.validator, "submission-docket-validator") or len({_identity(x) for x in actors}) != len(actors) or row.source_lineage_digest != self._anchor.source_lineage_digest or row.complete is not True or row.held is not True or any((row.resolved, row.recommended, row.accepted, row.approved, row.activated, row.deployed)) or row.status != "REBUTTAL_CORRECTION_SUBMISSIONS_VALIDATED_ON_HOLD_NOT_RESOLVED" or row.digest != canonical_digest(payload): return False
        return True

    def evidence(self):
        ok = self._integrity()
        return {"range": [10301, 10700], "control_count": 400, "registered_control_count": len(self._controls),
                "submission_count": len(self._submissions), "no_submission_count": sum(x.route == "NOT_APPLICABLE_PRESERVED" for x in self._submissions.values()),
                "rebuttal_submission_count": sum(x.route == "REBUTTAL_OPPORTUNITY_REQUIRED" for x in self._submissions.values()),
                "correction_submission_count": sum(x.route == "CORRECTION_REQUEST_REQUIRED" for x in self._submissions.values()),
                "hold_count": len(self._holds), "integrity_valid": ok,
                "complete_submission_docket_evidence": len(self._submissions) == 20 and self._docket is not None and ok,
                "maximum_state": "REBUTTAL_CORRECTION_SUBMISSIONS_VALIDATED_ON_HOLD_NOT_RESOLVED" if self._docket else "SUBMISSION_DOCKET_INCOMPLETE",
                "external_calls": 0, "document_transmissions": 0, "electronic_signatures": 0, "external_pg_calls": 0,
                "card_network_calls": 0, "payment_approvals": 0, "cancellations": 0, "refunds": 0,
                "settlements": 0, "transfers": 0, "ledger_writes": 0, "credential_reads": 0,
                "deployments": 0, "policy_prompt_weight_changes": 0, "resolved": False, "recommended": False,
                "accepted": False, "approved": False, "activated": False}
