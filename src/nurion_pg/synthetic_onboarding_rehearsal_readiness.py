"""Synthetic/in-memory onboarding rehearsal readiness controls #4701-#5100."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAM_NAMES = (
    "ACCEPTED_PACKAGE_SOURCE_ANCHOR", "LESSON_REGISTRY_APPLICATION",
    "PARTY_CAPABILITY_INTERSECTION", "TENANT_ONBOARDING_BLUEPRINT",
    "UPSTREAM_ONBOARDING_BLUEPRINT", "FOUR_DIRECTION_ROUTE_REHEARSAL",
    "DOCUMENT_SCHEMA_REHEARSAL", "TOKEN_BOUNDARY_REHEARSAL",
    "IDEMPOTENCY_REPLAY_REHEARSAL", "ORDERING_CONCURRENCY_REHEARSAL",
    "FAILURE_RECOVERY_REHEARSAL", "PARTIAL_BATCH_FAIL_CLOSED",
    "REHEARSAL_RESULT_LINEAGE", "INDEPENDENT_READINESS_REVIEW",
    "APPEND_ONLY_HOLD_CHAIN", "OPERATOR_ACTIVATION_GATE_BOUNDARY",
)
WORKSTREAMS = tuple((4701 + i * 25, 4725 + i * 25, name)
                    for i, name in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "semantic_label", "source_type",
    "tenant_scope", "role_scope", "state_precondition", "latest_sequence",
    "source_binding", "digest_recalculation", "negative_path", "missing_input",
    "duplicate_input", "replay", "conflict", "stale_version", "concurrency",
    "partial_batch", "ordering", "append_only", "hold_propagation",
    "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay",
                      "conflict", "stale_version", "partial_batch"})
FLOWS = ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")
SCENARIOS = ("DOCUMENT", "TOKEN", "REPLAY", "ORDERING", "FAILURE", "PARTIAL_BATCH")
PARTIES = ("TENANT_AGENCY", "NURION_PG", "UPSTREAM_PG")
COMMON_OPERATIONS = ("MAP", "VALIDATE", "MOCK_ACK")
COMMON_TOKEN_CLASSES = ("REFERENCE", "SESSIONLESS_FIXTURE")
APPLIED_LESSONS = ("ARL-3901-001", "ARL-4301-001", "ARL-4301-002", "ARL-4301-003", "ARL-4701-001")


def _syn(value, kind): return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
def _identity(value): return value.rsplit(":", 1)[-1].casefold()


@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str
    fixture_digest: str; expected_result: str; digest: str


@dataclass(frozen=True)
class SourceAnchor:
    anchor_id: str; package_manifest_digest: str; acceptance_receipt_digest: str
    lesson_registry_digest: str; applied_lesson_ids: tuple[str, ...]
    capability_profile_digests: tuple[tuple[str, str], ...]
    capability_profile_operations: tuple[tuple[str, tuple[str, ...]], ...]
    capability_profile_token_classes: tuple[tuple[str, tuple[str, ...]], ...]
    common_operations: tuple[str, ...]; common_token_classes: tuple[str, ...]
    source_sequence: int; is_latest: bool; package_assembler: str; status: str; digest: str


@dataclass(frozen=True)
class RehearsalPlan:
    plan_id: str; flow: str; scenario: str; anchor_digest: str; route_digest: str
    capability_digest: str; mode: str; status: str; digest: str


@dataclass(frozen=True)
class RehearsalResult:
    result_id: str; plan_digest: str; expected: str; observed: str
    external_calls: int; status: str; digest: str


@dataclass(frozen=True)
class ReadinessReceipt:
    receipt_id: str; anchor_digest: str; plan_set_digest: str; result_set_digest: str
    reviewer: str; package_assembler: str; ready_for_operator_review: bool
    activation_recorded: bool; deployment_recorded: bool; status: str; digest: str


class SyntheticOnboardingRehearsalReadiness:
    """Produces only inert plans and deterministic synthetic results."""

    def __init__(self):
        self._controls = {}; self._anchor = None; self._plans = {}; self._results = {}
        self._receipt = None; self._events = []; self._holds = []; self._lock = RLock()

    def add_control(self, control_id, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        payload = dict(control_id=control_id, workstream=workstream, aspect=aspect,
                       requirement_ref=requirement_ref, fixture_digest=fixture_digest,
                       expected_result=expected_result)
        row = Control(**payload, digest=canonical_digest(payload))
        with self._lock:
            if not self._valid_control(row): raise GovernanceRejected("valid #4701-#5100 control required")
            prior = self._controls.get(control_id)
            if prior:
                if prior == row: return prior
                raise GovernanceRejected("control conflict")
            self._controls[control_id] = row; return row

    def anchor_source(self, anchor_id, package_manifest_digest, acceptance_receipt_digest,
                      lesson_registry_digest, applied_lesson_ids, capability_profile_digests,
                      capability_profile_operations, capability_profile_token_classes,
                      common_operations, common_token_classes, source_sequence, is_latest,
                      package_assembler):
        payload = dict(anchor_id=anchor_id, package_manifest_digest=package_manifest_digest,
                       acceptance_receipt_digest=acceptance_receipt_digest,
                       lesson_registry_digest=lesson_registry_digest,
                       applied_lesson_ids=tuple(applied_lesson_ids),
                       capability_profile_digests=tuple(capability_profile_digests),
                       capability_profile_operations=tuple((p, tuple(v)) for p,v in capability_profile_operations),
                       capability_profile_token_classes=tuple((p, tuple(v)) for p,v in capability_profile_token_classes),
                       common_operations=tuple(common_operations),
                       common_token_classes=tuple(common_token_classes), source_sequence=source_sequence,
                       is_latest=is_latest, package_assembler=package_assembler,
                       status="ACCEPTED_PACKAGE_NOT_ACTIVATED")
        row = SourceAnchor(**payload, digest=canonical_digest(payload))
        with self._lock:
            profiles = tuple(x[0] for x in row.capability_profile_digests)
            operation_parties=tuple(x[0] for x in row.capability_profile_operations)
            token_parties=tuple(x[0] for x in row.capability_profile_token_classes)
            operation_intersection=set.intersection(*(set(x[1]) for x in row.capability_profile_operations)) if row.capability_profile_operations else set()
            token_intersection=set.intersection(*(set(x[1]) for x in row.capability_profile_token_classes)) if row.capability_profile_token_classes else set()
            valid = (self._registry_integrity() and _syn(anchor_id, "onboarding-anchor")
                     and all(_hex(x) for x in (package_manifest_digest, acceptance_receipt_digest,
                                               lesson_registry_digest))
                     and row.applied_lesson_ids == APPLIED_LESSONS
                     and profiles == PARTIES and all(_hex(x[1]) for x in row.capability_profile_digests)
                     and operation_parties == PARTIES and token_parties == PARTIES
                     and operation_intersection == set(COMMON_OPERATIONS)
                     and token_intersection == set(COMMON_TOKEN_CLASSES)
                     and row.common_operations == COMMON_OPERATIONS
                     and row.common_token_classes == COMMON_TOKEN_CLASSES
                     and isinstance(source_sequence, int) and not isinstance(source_sequence, bool)
                     and source_sequence > 0 and is_latest is True
                     and _syn(package_assembler, "package-assembler"))
            if not valid: raise GovernanceRejected("latest accepted package and applied lessons required")
            if self._anchor:
                if self._anchor == row: return self._anchor
                raise GovernanceRejected("source anchor conflict")
            self._anchor = row; self._event("SOURCE_ANCHORED", row.digest); return row

    def add_plan(self, plan_id, flow, scenario, operations, token_classes):
        with self._lock:
            if self._anchor is None: raise GovernanceRejected("source anchor required")
            operations, token_classes = tuple(operations), tuple(token_classes)
            route = canonical_digest(("ROUTE", self._anchor.package_manifest_digest, flow))
            capability = canonical_digest(("COMMON_CAPABILITY", operations, token_classes))
            payload = dict(plan_id=plan_id, flow=flow, scenario=scenario,
                           anchor_digest=self._anchor.digest, route_digest=route,
                           capability_digest=capability, mode="IN_MEMORY_NO_TRANSPORT",
                           status="REHEARSAL_PLANNED")
            row = RehearsalPlan(**payload, digest=canonical_digest(payload))
            if (not _syn(plan_id, "rehearsal-plan") or flow not in FLOWS or scenario not in SCENARIOS
                    or not set(operations) <= set(self._anchor.common_operations)
                    or not set(token_classes) <= set(self._anchor.common_token_classes)
                    or not operations or not token_classes):
                raise GovernanceRejected("common-capability inert plan required")
            key = (flow, scenario); prior = self._plans.get(key)
            if prior:
                if prior == row: return prior
                raise GovernanceRejected("plan conflict")
            self._plans[key] = row; self._event("PLAN_RECORDED", row.digest); return row

    def run_rehearsal(self):
        with self._lock:
            required = {(f, s) for f in FLOWS for s in SCENARIOS}
            if set(self._plans) != required or self._results or not self._integrity():
                self._hold("INCOMPLETE_REHEARSAL_BLOCKED", canonical_digest(tuple(sorted(self._plans))))
                raise GovernanceRejected("exact current plan set required")
            for key in sorted(required):
                plan = self._plans[key]; expected = "FAIL_CLOSED" if plan.scenario == "PARTIAL_BATCH" else "SYNTHETIC_PASS"
                payload = dict(result_id=f"synthetic:rehearsal-result:{plan.flow}:{plan.scenario}",
                               plan_digest=plan.digest, expected=expected, observed=expected,
                               external_calls=0, status="IN_MEMORY_RESULT")
                row = RehearsalResult(**payload, digest=canonical_digest(payload)); self._results[key] = row
                self._event("RESULT_RECORDED", row.digest)
            return tuple(self._results.values())

    def review(self, receipt_id, reviewer):
        with self._lock:
            if self._anchor is None or len(self._results) != 24 or self._receipt is not None or not self._integrity():
                raise GovernanceRejected("complete intact rehearsal required")
            if not _syn(receipt_id, "readiness-receipt") or not _syn(reviewer, "readiness-reviewer"):
                raise GovernanceRejected("synthetic independent reviewer required")
            if _identity(reviewer) == _identity(self._anchor.package_assembler):
                raise GovernanceRejected("maker checker separation required")
            plans = canonical_digest(tuple(self._plans[k].digest for k in sorted(self._plans)))
            results = canonical_digest(tuple(self._results[k].digest for k in sorted(self._results)))
            payload = dict(receipt_id=receipt_id, anchor_digest=self._anchor.digest,
                           plan_set_digest=plans, result_set_digest=results, reviewer=reviewer,
                           package_assembler=self._anchor.package_assembler,
                           ready_for_operator_review=True, activation_recorded=False,
                           deployment_recorded=False, status="READY_FOR_OPERATOR_REVIEW_NOT_ACTIVATED")
            self._receipt = ReadinessReceipt(**payload, digest=canonical_digest(payload))
            self._event("READINESS_REVIEWED", self._receipt.digest); return self._receipt

    def _expected(self, cid):
        i = cid - 4701; return WORKSTREAM_NAMES[i // 25], CONTROL_ASPECTS[i % 25]

    def _valid_control(self, row):
        if not isinstance(row.control_id, int) or isinstance(row.control_id, bool) or not 4701 <= row.control_id <= 5100: return False
        p = {k:v for k,v in row.__dict__.items() if k != "digest"}
        return (self._expected(row.control_id) == (row.workstream, row.aspect)
                and row.requirement_ref == f"synthetic:onboarding-requirement:{(row.control_id-4701)//25:02}"
                and _hex(row.fixture_digest)
                and row.expected_result == ("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS")
                and row.digest == canonical_digest(p))

    def _registry_integrity(self):
        return set(self._controls) == set(range(4701, 5101)) and all(k == v.control_id and self._valid_control(v) for k,v in self._controls.items())

    def _event(self, action, artifact_digest):
        previous = self._events[-1]["digest"] if self._events else None
        payload = dict(sequence=len(self._events)+1, action=action, artifact_digest=artifact_digest, previous_digest=previous)
        self._events.append({**payload, "digest":canonical_digest(payload)})

    def _hold(self, reason, attachment_digest):
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = dict(sequence=len(self._holds)+1, reason=reason, attachment_digest=attachment_digest, previous_digest=previous)
        self._holds.append({**payload, "digest":canonical_digest(payload)})

    @staticmethod
    def _chain_valid(chain):
        previous = None
        for i, item in enumerate(chain, 1):
            event = "action" in item
            keys = ("sequence","action","artifact_digest","previous_digest") if event else ("sequence","reason","attachment_digest","previous_digest")
            p = {k:item.get(k) for k in keys}
            if item.get("sequence") != i or item.get("previous_digest") != previous or item != {**p,"digest":canonical_digest(p)}: return False
            if event and item["action"] not in {"SOURCE_ANCHORED","PLAN_RECORDED","RESULT_RECORDED","READINESS_REVIEWED"}: return False
            if not event and item["reason"] != "INCOMPLETE_REHEARSAL_BLOCKED": return False
            previous = item["digest"]
        return True

    def _integrity(self):
        if not self._registry_integrity() or not self._chain_valid(self._events) or not self._chain_valid(self._holds): return False
        if self._anchor:
            a=self._anchor; p={k:v for k,v in a.__dict__.items() if k!="digest"}
            if (a.status != "ACCEPTED_PACKAGE_NOT_ACTIVATED" or not a.is_latest or a.source_sequence <= 0
                    or not _syn(a.anchor_id,"onboarding-anchor")
                    or not all(_hex(x) for x in (a.package_manifest_digest,a.acceptance_receipt_digest,a.lesson_registry_digest))
                    or a.applied_lesson_ids != APPLIED_LESSONS or tuple(x[0] for x in a.capability_profile_digests) != PARTIES
                    or tuple(x[0] for x in a.capability_profile_operations) != PARTIES
                    or tuple(x[0] for x in a.capability_profile_token_classes) != PARTIES
                    or set.intersection(*(set(x[1]) for x in a.capability_profile_operations)) != set(COMMON_OPERATIONS)
                    or set.intersection(*(set(x[1]) for x in a.capability_profile_token_classes)) != set(COMMON_TOKEN_CLASSES)
                    or a.common_operations != COMMON_OPERATIONS or a.common_token_classes != COMMON_TOKEN_CLASSES
                    or not _syn(a.package_assembler,"package-assembler") or a.digest != canonical_digest(p)): return False
        for key,row in self._plans.items():
            p={k:v for k,v in row.__dict__.items() if k!="digest"}
            route=canonical_digest(("ROUTE",self._anchor.package_manifest_digest,row.flow))
            capability=canonical_digest(("COMMON_CAPABILITY",COMMON_OPERATIONS,COMMON_TOKEN_CLASSES))
            if (key != (row.flow,row.scenario) or row.anchor_digest != self._anchor.digest
                    or not _syn(row.plan_id,"rehearsal-plan") or row.flow not in FLOWS or row.scenario not in SCENARIOS
                    or row.route_digest != route or row.capability_digest != capability
                    or row.mode != "IN_MEMORY_NO_TRANSPORT" or row.status != "REHEARSAL_PLANNED"
                    or row.digest != canonical_digest(p)): return False
        for key,row in self._results.items():
            p={k:v for k,v in row.__dict__.items() if k!="digest"}; plan=self._plans.get(key)
            expected="FAIL_CLOSED" if key[1]=="PARTIAL_BATCH" else "SYNTHETIC_PASS"
            if (plan is None or row.plan_digest != plan.digest or row.expected != expected or row.observed != expected
                    or not _syn(row.result_id,"rehearsal-result")
                    or row.external_calls != 0 or row.status != "IN_MEMORY_RESULT" or row.digest != canonical_digest(p)): return False
        if self._receipt:
            r=self._receipt; p={k:v for k,v in r.__dict__.items() if k!="digest"}
            plans=canonical_digest(tuple(self._plans[k].digest for k in sorted(self._plans)))
            results=canonical_digest(tuple(self._results[k].digest for k in sorted(self._results)))
            if (r.anchor_digest != self._anchor.digest or r.plan_set_digest != plans or r.result_set_digest != results
                    or not _syn(r.receipt_id,"readiness-receipt") or not _syn(r.reviewer,"readiness-reviewer")
                    or r.package_assembler != self._anchor.package_assembler or _identity(r.reviewer)==_identity(r.package_assembler)
                    or not r.ready_for_operator_review or r.activation_recorded or r.deployment_recorded
                    or r.status != "READY_FOR_OPERATOR_REVIEW_NOT_ACTIVATED" or r.digest != canonical_digest(p)): return False
        expected=[]
        if self._anchor: expected.append(("SOURCE_ANCHORED",self._anchor.digest))
        expected.extend(("PLAN_RECORDED",x.digest) for x in self._plans.values())
        expected.extend(("RESULT_RECORDED",x.digest) for x in self._results.values())
        if self._receipt: expected.append(("READINESS_REVIEWED",self._receipt.digest))
        return [(x.get("action"),x.get("artifact_digest")) for x in self._events] == expected

    def evidence(self):
        matrix=len(WORKSTREAMS)==16 and all(e-s+1==25 for s,e,_ in WORKSTREAMS) and WORKSTREAMS[0][0]==4701 and WORKSTREAMS[-1][1]==5100
        integrity=self._integrity(); complete=len(self._plans)==24 and len(self._results)==24 and self._receipt is not None
        return {"range":[4701,5100],"control_count":400,"workstream_count":16,"controls_per_workstream":25,
                "control_matrix_valid":matrix,"registered_control_count":len(self._controls),
                "plan_count":len(self._plans),"result_count":len(self._results),"event_count":len(self._events),
                "hold_count":len(self._holds),"integrity_valid":integrity,"complete_readiness_evidence":complete and integrity,
                "maximum_state":"READY_FOR_OPERATOR_REVIEW_NOT_ACTIVATED" if self._receipt else "REHEARSAL_PLANNED",
                "capability_ready":matrix and self._registry_integrity() and complete and integrity,
                "external_calls":0,"document_transmissions":0,"electronic_signatures":0,"external_pg_calls":0,
                "card_network_calls":0,"payment_approvals":0,"cancellations":0,"refunds":0,"settlements":0,
                "transfers":0,"ledger_writes":0,"credential_reads":0,"deployments":0,
                "policy_prompt_weight_changes":0,"activation_recorded":False,"release_recorded":False}
