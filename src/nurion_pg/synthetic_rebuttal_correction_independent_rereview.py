"""Synthetic independent re-review controls #10701-#11100.

This in-memory-only layer reconstructs the twenty #10301-#10700 submissions and
opens human re-examination dockets.  It cannot conclude, accept, resolve, approve,
activate, deploy, transmit documents, call a PG, or write a financial ledger.
"""
from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_rebuttal_correction_submission_validation import (
    ANSWER_KINDS, APPLIED_LESSONS, APPLIED_RULES, CASE_KEYS, FLOWS, RESPONDER,
    ROUTES, derived_receipt_digest, submission_digest,
)

WORKSTREAM_NAMES = (
    "SUBMISSION_DOCKET_ANCHOR", "LESSON_RULE_REGISTRY_BINDING",
    "SOURCE_SUBMISSION_SEMANTIC_RECONSTRUCTION", "NO_SUBMISSION_MARKER_REREVIEW",
    "REBUTTAL_HUMAN_REEXAMINATION", "CORRECTION_HUMAN_REEXAMINATION",
    "INDEPENDENT_REREVIEWER_ASSIGNMENT", "RECEIPT_SEMANTIC_REVALIDATION",
    "IMMEDIATE_PARENT_REREVIEW_LINEAGE", "SOURCE_ACTOR_NAMESPACE_PROJECTION",
    "REREVIEW_DOCKET_ROLE_SEPARATION", "ROUTE_MATERIAL_CONSISTENCY",
    "APPEND_ONLY_REREVIEW_EVENT", "UNRESOLVED_REREVIEW_HOLD_CHAIN",
    "PARTIAL_BATCH_FAIL_CLOSED", "NON_CONCLUSION_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((10701 + i * 25, 10725 + i * 25, name) for i, name in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type", "tenant_scope",
    "role_scope", "state_precondition", "latest_sequence", "source_binding",
    "digest_recalculation", "negative_path", "missing_input", "duplicate_input", "replay",
    "conflict", "stale_version", "concurrency", "partial_batch", "ordering", "append_only",
    "hold_propagation", "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay", "conflict", "stale_version", "partial_batch"})
SOURCE_ACTOR_KINDS = tuple(
    actor_kind
    for position in range(len(CASE_KEYS))
    if ROUTES[position % 5] != "NOT_APPLICABLE_PRESERVED"
    for actor_kind in (
        "response-independent-reviewer",
        "rebuttal-custodian" if ROUTES[position % 5] == "REBUTTAL_OPPORTUNITY_REQUIRED" else "correction-request-compiler",
    )
)

def _syn(value, kind): return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
def _identity(value): return value.rsplit(":", 1)[-1].casefold()

@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str
    fixture_digest: str; expected_result: str; digest: str

@dataclass(frozen=True)
class SourceSubmission:
    submission_id: str; flow: str; answer_kind: str; source_review_digest: str; route: str
    submitter_party: str | None; document_digest: str | None; receipt_digest: str | None
    marker: str; parent_submission_digest: str | None; position: int; held: bool
    validated: bool; resolved: bool; accepted: bool; digest: str

@dataclass(frozen=True)
class Anchor:
    anchor_id: str; source_docket_digest: str; submission_set_digest: str
    lesson_registry_digest: str; remediation_manifest_digest: str
    applied_lesson_ids: tuple[str, ...]; applied_rule_ids: tuple[str, ...]
    source_submissions: tuple[SourceSubmission, ...]; source_actor_roles: tuple[str, ...]
    source_compiler: str; source_validator: str
    source_lineage_digest: str; source_sequence: int; is_latest: bool; status: str; digest: str

@dataclass(frozen=True)
class ReReview:
    rereview_id: str; flow: str; answer_kind: str; source_submission_digest: str; route: str
    reviewer: str | None; marker: str; parent_rereview_digest: str | None; position: int
    held: bool; pending_human_reexamination: bool; concluded: bool; resolved: bool
    accepted: bool; digest: str

@dataclass(frozen=True)
class Docket:
    docket_id: str; anchor_digest: str; rereview_set_digest: str; compiler: str; validator: str
    source_lineage_digest: str; complete: bool; held: bool; pending_human_reexamination: bool
    concluded: bool; resolved: bool; recommended: bool; accepted: bool; approved: bool
    activated: bool; deployed: bool; status: str; digest: str

def source_submission_digest(row):
    return submission_digest(row.flow, row.answer_kind, row.source_review_digest, row.route,
                             row.submitter_party, row.document_digest, row.receipt_digest,
                             row.marker, row.parent_submission_digest, row.position)

def rereview_digest(flow, kind, source, route, reviewer, marker, parent, position):
    return canonical_digest(("INDEPENDENT_REBUTTAL_CORRECTION_REREVIEW", flow, kind, source,
                             route, reviewer, marker, parent, position))

def _anchor_payload(payload):
    payload = dict(payload)
    payload["source_submissions"] = tuple(tuple(row.__dict__.values()) for row in payload["source_submissions"])
    return payload

class SyntheticRebuttalCorrectionIndependentReReview:
    def __init__(self):
        self._controls = {}; self._anchor = None; self._rereviews = {}; self._docket = None
        self._events = []; self._holds = []; self._lock = RLock()

    def _expected(self, control_id):
        index = control_id - 10701
        return WORKSTREAM_NAMES[index // 25], CONTROL_ASPECTS[index % 25]

    def add_control(self, control_id, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        payload = dict(control_id=control_id, workstream=workstream, aspect=aspect,
                       requirement_ref=requirement_ref, fixture_digest=fixture_digest,
                       expected_result=expected_result)
        row = Control(**payload, digest=canonical_digest(payload))
        with self._lock:
            if not self._control_valid(row): raise GovernanceRejected("valid #10701-#11100 control required")
            old = self._controls.get(control_id)
            if old:
                if old == row: return old
                raise GovernanceRejected("control conflict")
            self._controls[control_id] = row
            return row

    def anchor(self, anchor_id, source_docket_digest, submission_set_digest, registry_digest,
               manifest_digest, lessons, rules, submissions, source_actor_roles, source_compiler, source_validator,
               sequence, is_latest):
        submissions = tuple(submissions); source_actor_roles = tuple(source_actor_roles)
        lineage = canonical_digest(("SUBMISSION_VALIDATION_FULL_LINEAGE", source_docket_digest,
                                    submission_set_digest, tuple(x.digest for x in submissions),
                                    source_actor_roles, source_compiler, source_validator))
        payload = dict(anchor_id=anchor_id, source_docket_digest=source_docket_digest,
                       submission_set_digest=submission_set_digest, lesson_registry_digest=registry_digest,
                       remediation_manifest_digest=manifest_digest, applied_lesson_ids=tuple(lessons),
                       applied_rule_ids=tuple(rules), source_submissions=submissions,
                       source_actor_roles=source_actor_roles,
                       source_compiler=source_compiler, source_validator=source_validator,
                       source_lineage_digest=lineage, source_sequence=sequence, is_latest=is_latest,
                       status="SUBMISSION_VALIDATION_DOCKET_ANCHORED_ON_HOLD_NOT_REREVIEWED")
        row = Anchor(**payload, digest=canonical_digest(_anchor_payload(payload)))
        with self._lock:
            if not self._anchor_valid(row): raise GovernanceRejected("complete latest submission docket required")
            if self._anchor:
                if self._anchor == row: return row
                raise GovernanceRejected("anchor conflict")
            self._anchor = row; self._event("SUBMISSION_VALIDATION_DOCKET_ANCHORED", row.digest)
            return row

    def add_rereview(self, rereview_id, flow, kind, reviewer=None):
        with self._lock:
            key = (flow, kind)
            if not self._anchor or key not in CASE_KEYS: raise GovernanceRejected("anchored source submission required")
            position = CASE_KEYS.index(key); source = self._anchor.source_submissions[position]
            previous = None if position == 0 else self._rereviews.get(CASE_KEYS[position - 1])
            if position and previous is None: raise GovernanceRejected("immediate prior rereview required")
            if source.route == "NOT_APPLICABLE_PRESERVED":
                if reviewer is not None: raise GovernanceRejected("N/A forbids reviewer")
                marker = "NO_SUBMISSION_MARKER_PRESERVED"
            else:
                if not _syn(reviewer, "independent-human-rereviewer"): raise GovernanceRejected("independent human rereviewer required")
                occupied = self._anchor.source_actor_roles + (self._anchor.source_compiler, self._anchor.source_validator) + tuple(
                    x.reviewer for x in self._rereviews.values() if x.reviewer)
                if _identity(reviewer) in {_identity(x) for x in occupied}: raise GovernanceRejected("rereviewer role collision")
                marker = "HUMAN_REEXAMINATION_PENDING"
            parent = None if previous is None else previous.digest
            digest = rereview_digest(flow, kind, source.digest, source.route, reviewer, marker, parent, position + 1)
            row = ReReview(rereview_id, flow, kind, source.digest, source.route, reviewer, marker,
                           parent, position + 1, True, source.route != "NOT_APPLICABLE_PRESERVED",
                           False, False, False, digest)
            if not self._rereview_valid(row, key): raise GovernanceRejected("valid pending rereview required")
            old = self._rereviews.get(key)
            if old:
                if old == row: return old
                raise GovernanceRejected("rereview conflict")
            self._rereviews[key] = row; self._event("INDEPENDENT_REREVIEW_OPENED", row.digest)
            if row.pending_human_reexamination: self._hold("HUMAN_REEXAMINATION_REQUIRED", row.digest)
            return row

    def finalize(self, docket_id, compiler, validator):
        with self._lock:
            if self._docket or tuple(self._rereviews) != CASE_KEYS or not self._integrity():
                raise GovernanceRejected("complete intact rereviews required")
            actors = self._anchor.source_actor_roles + (self._anchor.source_compiler, self._anchor.source_validator) + tuple(
                x.reviewer for x in self._rereviews.values() if x.reviewer) + (compiler, validator)
            if not _syn(compiler, "rereview-docket-compiler") or not _syn(validator, "rereview-docket-validator") or len({_identity(x) for x in actors}) != len(actors):
                raise GovernanceRejected("independent docket actors required")
            review_set = canonical_digest(tuple(self._rereviews[k].digest for k in CASE_KEYS))
            payload = dict(docket_id=docket_id, anchor_digest=self._anchor.digest,
                           rereview_set_digest=review_set, compiler=compiler, validator=validator,
                           source_lineage_digest=self._anchor.source_lineage_digest, complete=True,
                           held=True, pending_human_reexamination=True, concluded=False, resolved=False,
                           recommended=False, accepted=False, approved=False, activated=False,
                           deployed=False, status="INDEPENDENT_REREVIEW_DOCKET_ON_HOLD_PENDING_HUMAN_REEXAMINATION")
            row = Docket(**payload, digest=canonical_digest(payload)); self._docket = row
            self._event("INDEPENDENT_REREVIEW_DOCKET_HELD", row.digest)
            return row

    def _control_valid(self, row):
        payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
        return isinstance(row.control_id, int) and not isinstance(row.control_id, bool) and 10701 <= row.control_id <= 11100 and self._expected(row.control_id) == (row.workstream, row.aspect) and row.requirement_ref == f"synthetic:independent-rereview-requirement:{(row.control_id-10701)//25:02}" and _hex(row.fixture_digest) and row.expected_result == ("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS") and row.digest == canonical_digest(payload)

    def _registry_valid(self):
        return set(self._controls) == set(range(10701, 11101)) and all(k == v.control_id and self._control_valid(v) for k, v in self._controls.items())

    def _source_valid(self, row, position, rows):
        flow, kind = CASE_KEYS[position]; route = ROUTES[position % 5]
        parent = None if position == 0 else rows[position - 1].digest
        if route == "NOT_APPLICABLE_PRESERVED":
            material = row.submitter_party is None and row.document_digest is None and row.receipt_digest is None and row.marker == "NO_SUBMISSION_REQUIRED"
        else:
            material = row.submitter_party == RESPONDER[flow] and _hex(row.document_digest) and row.receipt_digest == derived_receipt_digest(flow, kind, row.source_review_digest, route, row.submitter_party, row.document_digest) and row.marker == "SUBMISSION_RECEIVED_FOR_HUMAN_REVIEW"
        return _syn(row.submission_id, "rebuttal-correction-submission") and (row.flow, row.answer_kind) == (flow, kind) and _hex(row.source_review_digest) and row.route == route and material and row.parent_submission_digest == parent and row.position == position + 1 and row.held is True and row.validated is True and not any((row.resolved, row.accepted)) and row.digest == source_submission_digest(row)

    def _anchor_valid(self, row):
        payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
        submission_set = canonical_digest(tuple(x.digest for x in row.source_submissions))
        source_docket = canonical_digest(("REBUTTAL_CORRECTION_SUBMISSION_DOCKET_SOURCE", submission_set, row.source_compiler, row.source_validator))
        lineage = canonical_digest(("SUBMISSION_VALIDATION_FULL_LINEAGE", row.source_docket_digest, row.submission_set_digest, tuple(x.digest for x in row.source_submissions), row.source_actor_roles, row.source_compiler, row.source_validator))
        source_actors = row.source_actor_roles + (row.source_compiler, row.source_validator)
        return self._registry_valid() and _syn(row.anchor_id, "independent-rereview-anchor") and len(row.source_submissions) == 20 and all(self._source_valid(x, i, row.source_submissions) for i, x in enumerate(row.source_submissions)) and row.submission_set_digest == submission_set and row.source_docket_digest == source_docket and _hex(row.lesson_registry_digest) and _hex(row.remediation_manifest_digest) and row.applied_lesson_ids == APPLIED_LESSONS and row.applied_rule_ids == APPLIED_RULES and len(row.source_actor_roles) == len(SOURCE_ACTOR_KINDS) and all(_syn(actor, kind) for actor, kind in zip(row.source_actor_roles, SOURCE_ACTOR_KINDS)) and _syn(row.source_compiler, "submission-docket-compiler") and _syn(row.source_validator, "submission-docket-validator") and len({_identity(x) for x in source_actors}) == len(source_actors) and row.source_lineage_digest == lineage and isinstance(row.source_sequence, int) and not isinstance(row.source_sequence, bool) and row.source_sequence > 0 and row.is_latest is True and row.status == "SUBMISSION_VALIDATION_DOCKET_ANCHORED_ON_HOLD_NOT_REREVIEWED" and row.digest == canonical_digest(_anchor_payload(payload))

    def _rereview_valid(self, row, key):
        if not self._anchor or key not in CASE_KEYS: return False
        position = CASE_KEYS.index(key); source = self._anchor.source_submissions[position]
        previous = None if position == 0 else self._rereviews.get(CASE_KEYS[position - 1])
        if source.route == "NOT_APPLICABLE_PRESERVED":
            state = row.reviewer is None and row.marker == "NO_SUBMISSION_MARKER_PRESERVED" and row.pending_human_reexamination is False
        else:
            state = _syn(row.reviewer, "independent-human-rereviewer") and row.marker == "HUMAN_REEXAMINATION_PENDING" and row.pending_human_reexamination is True
        expected = rereview_digest(row.flow, row.answer_kind, source.digest, source.route, row.reviewer,
                                   row.marker, None if previous is None else previous.digest, position + 1)
        return _syn(row.rereview_id, "independent-rereview") and (row.flow, row.answer_kind) == key and row.source_submission_digest == source.digest and row.route == source.route and state and row.parent_rereview_digest == (None if previous is None else previous.digest) and row.position == position + 1 and row.held is True and not any((row.concluded, row.resolved, row.accepted)) and row.digest == expected

    def _event(self, action, artifact):
        previous = self._events[-1]["digest"] if self._events else None
        payload = dict(sequence=len(self._events) + 1, action=action, artifact_digest=artifact, previous_digest=previous)
        self._events.append({**payload, "digest": canonical_digest(payload)})

    def _hold(self, reason, artifact):
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = dict(sequence=len(self._holds) + 1, reason=reason, attachment_digest=artifact, previous_digest=previous)
        self._holds.append({**payload, "digest": canonical_digest(payload)})

    @staticmethod
    def _chain(rows, event):
        previous = None
        for sequence, row in enumerate(rows, 1):
            keys = ("sequence", "action", "artifact_digest", "previous_digest") if event else ("sequence", "reason", "attachment_digest", "previous_digest")
            payload = {k: row.get(k) for k in keys}
            if row != {**payload, "digest": canonical_digest(payload)} or row["sequence"] != sequence or row["previous_digest"] != previous: return False
            previous = row["digest"]
        return True

    def _integrity(self):
        if not self._registry_valid() or not self._chain(self._events, True) or not self._chain(self._holds, False) or (self._anchor and not self._anchor_valid(self._anchor)) or any(not self._rereview_valid(v, k) for k, v in self._rereviews.items()): return False
        events = []
        if self._anchor: events.append(("SUBMISSION_VALIDATION_DOCKET_ANCHORED", self._anchor.digest))
        events.extend(("INDEPENDENT_REREVIEW_OPENED", x.digest) for x in self._rereviews.values())
        if self._docket: events.append(("INDEPENDENT_REREVIEW_DOCKET_HELD", self._docket.digest))
        holds = [("HUMAN_REEXAMINATION_REQUIRED", x.digest) for x in self._rereviews.values() if x.pending_human_reexamination]
        if [(x["action"], x["artifact_digest"]) for x in self._events] != events or [(x["reason"], x["attachment_digest"]) for x in self._holds] != holds: return False
        if self._docket:
            row = self._docket; payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
            actors = self._anchor.source_actor_roles + (self._anchor.source_compiler, self._anchor.source_validator) + tuple(x.reviewer for x in self._rereviews.values() if x.reviewer) + (row.compiler, row.validator)
            if not _syn(row.docket_id, "independent-rereview-docket") or row.anchor_digest != self._anchor.digest or row.rereview_set_digest != canonical_digest(tuple(self._rereviews[k].digest for k in CASE_KEYS)) or not _syn(row.compiler, "rereview-docket-compiler") or not _syn(row.validator, "rereview-docket-validator") or len({_identity(x) for x in actors}) != len(actors) or row.source_lineage_digest != self._anchor.source_lineage_digest or row.complete is not True or row.held is not True or row.pending_human_reexamination is not True or any((row.concluded, row.resolved, row.recommended, row.accepted, row.approved, row.activated, row.deployed)) or row.status != "INDEPENDENT_REREVIEW_DOCKET_ON_HOLD_PENDING_HUMAN_REEXAMINATION" or row.digest != canonical_digest(payload): return False
        return True

    def evidence(self):
        ok = self._integrity()
        return {"range": [10701, 11100], "control_count": 400,
                "registered_control_count": len(self._controls), "rereview_count": len(self._rereviews),
                "source_actor_count": len(self._anchor.source_actor_roles) if self._anchor else 0,
                "source_lineage_digest": self._anchor.source_lineage_digest if self._anchor else None,
                "no_submission_marker_count": sum(x.route == "NOT_APPLICABLE_PRESERVED" for x in self._rereviews.values()),
                "rebuttal_human_review_pending_count": sum(x.route == "REBUTTAL_OPPORTUNITY_REQUIRED" and x.pending_human_reexamination for x in self._rereviews.values()),
                "correction_human_review_pending_count": sum(x.route == "CORRECTION_REQUEST_REQUIRED" and x.pending_human_reexamination for x in self._rereviews.values()),
                "hold_count": len(self._holds), "integrity_valid": ok,
                "complete_pending_rereview_docket_evidence": len(self._rereviews) == 20 and self._docket is not None and ok,
                "maximum_state": "INDEPENDENT_REREVIEW_DOCKET_ON_HOLD_PENDING_HUMAN_REEXAMINATION" if self._docket else "REREVIEW_DOCKET_INCOMPLETE",
                "external_calls": 0, "document_transmissions": 0, "electronic_signatures": 0,
                "external_pg_calls": 0, "card_network_calls": 0, "payment_approvals": 0,
                "cancellations": 0, "refunds": 0, "settlements": 0, "transfers": 0,
                "ledger_writes": 0, "credential_reads": 0, "deployments": 0,
                "policy_prompt_weight_changes": 0, "concluded": False, "resolved": False,
                "recommended": False, "accepted": False, "approved": False, "activated": False}
