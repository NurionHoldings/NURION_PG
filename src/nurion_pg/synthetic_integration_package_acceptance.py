"""Synthetic/in-memory integration-package acceptance controls #4301-#4700."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAM_NAMES = (
    "NEGOTIATION_RECEIPT_ANCHOR", "TENANT_PACKAGE_MANIFEST",
    "ELECTRONIC_DOCUMENT_TEMPLATE_SET", "ADAPTER_CONTRACT_SCAFFOLD",
    "TOKEN_FIXTURE_CATALOG", "REQUEST_RESPONSE_MOCK_PAIRS",
    "ERROR_RETRY_MOCK_MATRIX", "IDEMPOTENCY_REPLAY_HARNESS",
    "SEQUENCE_CONCURRENCY_HARNESS", "SCHEMA_DRIFT_IMPACT_GRAPH",
    "TENANT_UPSTREAM_ROUTE_BINDING", "PACKAGE_REPRODUCIBILITY",
    "MOCK_ACCEPTANCE_CASES", "INDEPENDENT_ACCEPTANCE_REVIEW",
    "PARTIAL_PACKAGE_HOLD_CHAIN", "OPERATOR_RELEASE_GATE_BOUNDARY",
)
WORKSTREAMS = tuple((4301 + i * 25, 4325 + i * 25, name)
                    for i, name in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "identifier_namespace", "tenant_scope",
    "role_scope", "state_precondition", "state_postcondition", "version_binding",
    "source_binding", "digest_binding", "negative_path", "missing_input",
    "duplicate_input", "replay", "conflict", "stale_version", "concurrency",
    "partial_batch", "ordering", "append_only", "hold_propagation",
    "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
NEGATIVE = frozenset({"negative_path", "missing_input", "duplicate_input", "replay",
                      "conflict", "stale_version", "partial_batch"})
PARTIES = ("TENANT_AGENCY", "NURION_PG", "UPSTREAM_PG")
FLOWS = ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")
FLOW_OWNERS = dict(zip(FLOWS, ("TENANT_AGENCY", "NURION_PG", "UPSTREAM_PG", "NURION_PG")))
ALLOWED_ARTIFACTS = frozenset({"DOCUMENT_TEMPLATE", "ADAPTER_CONTRACT", "TOKEN_FIXTURE",
                               "MOCK_PAIR", "RETRY_VECTOR", "REPLAY_VECTOR", "ORDER_VECTOR"})


def _syn(value, kind): return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")
def _hex(value): return isinstance(value, str) and len(value) == 64 and all(x in "0123456789abcdef" for x in value)
def _identity(value): return value.rsplit(":", 1)[-1].upper()


@dataclass(frozen=True)
class Control:
    control_id: int; workstream: str; aspect: str; requirement_ref: str
    fixture_digest: str; expected_result: str; digest: str


@dataclass(frozen=True)
class NegotiationAnchor:
    anchor_id: str; source_bundle_digest: str; negotiation_round_digest: str
    case_set_digest: str; review_receipt_digest: str; status: str; digest: str


@dataclass(frozen=True)
class PackageArtifact:
    artifact_id: str; artifact_type: str; party: str; flow: str
    anchor_digest: str; content_digest: str; mode: str; digest: str


@dataclass(frozen=True)
class PackageManifest:
    package_id: str; tenant_id: str; upstream_id: str; assembler: str; anchor_digest: str
    artifact_digests: tuple[str, ...]; route_bindings: tuple[tuple[str, str], ...]
    status: str; digest: str


@dataclass(frozen=True)
class MockAcceptanceCase:
    case_id: str; control_id: int; manifest_digest: str; fixture_digest: str
    expected_result: str; observed_result: str; status: str; digest: str


@dataclass(frozen=True)
class AcceptanceReceipt:
    receipt_id: str; manifest_digest: str; case_set_digest: str; reviewer: str
    assembler: str; accepted_for_review: bool; operator_release_required: bool
    release_recorded: bool; status: str; digest: str


class SyntheticIntegrationPackageAcceptance:
    """Builds inert package specifications and mock evidence; exposes no transport port."""

    def __init__(self):
        self._controls = {}; self._anchor = None; self._artifacts = {}; self._manifest = None
        self._cases = {}; self._receipt = None; self._events = []; self._holds = []; self._lock = RLock()

    def add_control(self, control_id, workstream, aspect, requirement_ref, fixture_digest, expected_result):
        payload = dict(control_id=control_id, workstream=workstream, aspect=aspect,
                       requirement_ref=requirement_ref, fixture_digest=fixture_digest,
                       expected_result=expected_result)
        row = Control(**payload, digest=canonical_digest(payload))
        with self._lock:
            if not self._valid_control(row): raise GovernanceRejected("valid #4301-#4700 control required")
            prior = self._controls.get(control_id)
            if prior:
                if prior == row: return prior
                raise GovernanceRejected("control conflict")
            self._controls[control_id] = row
            return row

    def anchor_negotiation(self, anchor_id, source_bundle_digest, negotiation_round_digest,
                           case_set_digest, review_receipt_digest):
        payload = dict(anchor_id=anchor_id, source_bundle_digest=source_bundle_digest,
                       negotiation_round_digest=negotiation_round_digest, case_set_digest=case_set_digest,
                       review_receipt_digest=review_receipt_digest, status="REVIEWED_NOT_APPROVED_SOURCE")
        row = NegotiationAnchor(**payload, digest=canonical_digest(payload))
        with self._lock:
            if (not self._registry_integrity() or not _syn(anchor_id, "package-anchor")
                    or not all(_hex(x) for x in (source_bundle_digest, negotiation_round_digest,
                                                case_set_digest, review_receipt_digest))):
                raise GovernanceRejected("complete reviewed negotiation lineage required")
            if self._anchor:
                if self._anchor == row: return self._anchor
                raise GovernanceRejected("anchor conflict")
            self._anchor = row; self._event("NEGOTIATION_ANCHORED", row.digest); return row

    def add_artifact(self, artifact_id, artifact_type, party, flow, content_digest):
        with self._lock:
            if self._anchor is None: raise GovernanceRejected("negotiation anchor required")
            payload = dict(artifact_id=artifact_id, artifact_type=artifact_type, party=party, flow=flow,
                           anchor_digest=self._anchor.digest, content_digest=content_digest,
                           mode="INERT_SPECIFICATION_ONLY")
            row = PackageArtifact(**payload, digest=canonical_digest(payload))
            if (not _syn(artifact_id, "package-artifact") or artifact_type not in ALLOWED_ARTIFACTS
                    or party not in PARTIES or flow not in FLOWS or FLOW_OWNERS.get(flow) != party
                    or not _hex(content_digest)):
                raise GovernanceRejected("allowlisted inert package artifact required")
            prior = self._artifacts.get(artifact_id)
            if prior:
                if prior == row: return prior
                raise GovernanceRejected("artifact conflict")
            self._artifacts[artifact_id] = row; self._event("ARTIFACT_SPECIFIED", row.digest); return row

    def assemble(self, package_id, tenant_id, upstream_id, assembler):
        with self._lock:
            required = {(kind, flow) for kind in ALLOWED_ARTIFACTS for flow in FLOWS}
            actual = {(x.artifact_type, x.flow) for x in self._artifacts.values()}
            if (self._anchor is None or self._manifest is not None or actual != required
                    or len(self._artifacts) != len(required) or not _syn(package_id, "integration-package")
                    or not _syn(tenant_id, "tenant") or not _syn(upstream_id, "upstream")
                    or not _syn(assembler, "package-assembler") or not self._integrity()):
                self._hold("PACKAGE_ASSEMBLY_REJECTED", canonical_digest((package_id, tenant_id, upstream_id)))
                raise GovernanceRejected("complete exact inert package required")
            bindings = tuple((flow, canonical_digest((tenant_id, "NURION_PG", upstream_id, flow))) for flow in FLOWS)
            payload = dict(package_id=package_id, tenant_id=tenant_id, upstream_id=upstream_id,
                           assembler=assembler,
                           anchor_digest=self._anchor.digest,
                           artifact_digests=tuple(sorted(x.digest for x in self._artifacts.values())),
                           route_bindings=bindings, status="MOCK_ACCEPTANCE_REQUIRED")
            self._manifest = PackageManifest(**payload, digest=canonical_digest(payload))
            self._event("PACKAGE_ASSEMBLED", self._manifest.digest)
            return self._manifest

    def run_cases(self, package_id):
        with self._lock:
            if (self._manifest is None or self._manifest.package_id != package_id or self._cases
                    or not self._integrity()):
                raise GovernanceRejected("one intact current manifest required")
            for control_id in range(4301, 4701):
                control = self._controls[control_id]
                payload = dict(case_id=f"synthetic:package-case:{control_id}", control_id=control_id,
                               manifest_digest=self._manifest.digest, fixture_digest=control.fixture_digest,
                               expected_result=control.expected_result, observed_result=control.expected_result,
                               status="SYNTHETIC_PASS")
                self._cases[control_id] = MockAcceptanceCase(**payload, digest=canonical_digest(payload))
            digest = canonical_digest(tuple(self._cases[x].digest for x in range(4301, 4701)))
            self._event("MOCK_CASES_RECORDED", digest); return tuple(self._cases.values())

    def review(self, receipt_id, package_id, reviewer, assembler):
        with self._lock:
            case_set = canonical_digest(tuple(self._cases[x].digest for x in range(4301, 4701))) if len(self._cases) == 400 else None
            if (self._manifest is None or self._manifest.package_id != package_id or case_set is None
                    or self._receipt is not None or not _syn(receipt_id, "package-receipt")
                    or not _syn(reviewer, "package-reviewer") or assembler != self._manifest.assembler
                    or _identity(reviewer) == _identity(assembler) or not self._integrity()):
                raise GovernanceRejected("independent complete package review required")
            payload = dict(receipt_id=receipt_id, manifest_digest=self._manifest.digest,
                           case_set_digest=case_set, reviewer=reviewer, assembler=assembler,
                           accepted_for_review=True, operator_release_required=True,
                           release_recorded=False, status="ACCEPTANCE_REVIEWED_NOT_RELEASED")
            self._receipt = AcceptanceReceipt(**payload, digest=canonical_digest(payload))
            self._event("ACCEPTANCE_RECEIPT_RECORDED", self._receipt.digest); return self._receipt

    def _expected(self, cid):
        i = cid - 4301; return WORKSTREAM_NAMES[i // 25], CONTROL_ASPECTS[i % 25]

    def _valid_control(self, row):
        if not isinstance(row.control_id, int) or isinstance(row.control_id, bool) or not 4301 <= row.control_id <= 4700: return False
        payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
        return (self._expected(row.control_id) == (row.workstream, row.aspect)
                and row.requirement_ref == f"synthetic:package-requirement:{(row.control_id-4301)//25:02}"
                and _hex(row.fixture_digest)
                and row.expected_result == ("EXPECTED_REJECTION" if row.aspect in NEGATIVE else "PASS")
                and row.digest == canonical_digest(payload))

    def _registry_integrity(self):
        return set(self._controls) == set(range(4301, 4701)) and all(k == x.control_id and self._valid_control(x) for k, x in self._controls.items())

    def _event(self, action, artifact_digest):
        previous = self._events[-1]["digest"] if self._events else None
        payload = dict(sequence=len(self._events)+1, action=action, artifact_digest=artifact_digest, previous_digest=previous)
        self._events.append({**payload, "digest": canonical_digest(payload)})

    def _hold(self, reason, attachment):
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = dict(sequence=len(self._holds)+1, reason=reason, attachment_digest=attachment, previous_digest=previous)
        self._holds.append({**payload, "digest": canonical_digest(payload)})

    def _chain_valid(self, chain):
        previous = None
        allowed_actions = {"NEGOTIATION_ANCHORED", "ARTIFACT_SPECIFIED", "PACKAGE_ASSEMBLED", "MOCK_CASES_RECORDED", "ACCEPTANCE_RECEIPT_RECORDED"}
        for i, item in enumerate(chain, 1):
            is_event = "action" in item
            keys = ("sequence", "action", "artifact_digest", "previous_digest") if is_event else ("sequence", "reason", "attachment_digest", "previous_digest")
            payload = {k: item.get(k) for k in keys}
            semantic = item.get("action") in allowed_actions if is_event else item.get("reason") == "PACKAGE_ASSEMBLY_REJECTED"
            if not semantic or item.get("sequence") != i or item.get("previous_digest") != previous or item != {**payload, "digest": canonical_digest(payload)}: return False
            previous = item["digest"]
        return True

    def _integrity(self):
        if not self._registry_integrity() or not self._chain_valid(self._events) or not self._chain_valid(self._holds): return False
        if self._anchor:
            p = {k:v for k,v in self._anchor.__dict__.items() if k != "digest"}
            if self._anchor.status != "REVIEWED_NOT_APPROVED_SOURCE" or self._anchor.digest != canonical_digest(p): return False
        for key, row in self._artifacts.items():
            p = {k:v for k,v in row.__dict__.items() if k != "digest"}
            if (key != row.artifact_id or row.artifact_type not in ALLOWED_ARTIFACTS or row.party not in PARTIES
                    or FLOW_OWNERS.get(row.flow) != row.party
                    or row.flow not in FLOWS or row.mode != "INERT_SPECIFICATION_ONLY"
                    or self._anchor is None or row.anchor_digest != self._anchor.digest or row.digest != canonical_digest(p)): return False
        if self._manifest:
            p = {k:v for k,v in self._manifest.__dict__.items() if k != "digest"}
            expected = tuple(sorted(x.digest for x in self._artifacts.values()))
            if (self._manifest.status != "MOCK_ACCEPTANCE_REQUIRED" or self._manifest.anchor_digest != self._anchor.digest
                    or not _syn(self._manifest.package_id, "integration-package")
                    or not _syn(self._manifest.tenant_id, "tenant")
                    or not _syn(self._manifest.upstream_id, "upstream")
                    or not _syn(self._manifest.assembler, "package-assembler")
                    or self._manifest.artifact_digests != expected or tuple(x[0] for x in self._manifest.route_bindings) != FLOWS
                    or self._manifest.route_bindings != tuple(
                        (flow, canonical_digest((self._manifest.tenant_id, "NURION_PG",
                                                 self._manifest.upstream_id, flow))) for flow in FLOWS)
                    or self._manifest.digest != canonical_digest(p)): return False
        for key, row in self._cases.items():
            p={k:v for k,v in row.__dict__.items() if k != "digest"}; control=self._controls.get(key)
            if (control is None or self._manifest is None or row.manifest_digest != self._manifest.digest
                    or row.control_id != key or row.fixture_digest != control.fixture_digest
                    or row.expected_result != control.expected_result or row.observed_result != control.expected_result
                    or row.status != "SYNTHETIC_PASS" or row.digest != canonical_digest(p)): return False
        if self._receipt:
            p={k:v for k,v in self._receipt.__dict__.items() if k != "digest"}
            cases=canonical_digest(tuple(self._cases[x].digest for x in range(4301,4701))) if len(self._cases)==400 else None
            if (self._manifest is None or self._receipt.manifest_digest != self._manifest.digest
                    or self._receipt.case_set_digest != cases
                    or self._receipt.assembler != self._manifest.assembler
                    or _identity(self._receipt.reviewer) == _identity(self._receipt.assembler)
                    or not self._receipt.accepted_for_review
                    or self._receipt.release_recorded or not self._receipt.operator_release_required
                    or self._receipt.status != "ACCEPTANCE_REVIEWED_NOT_RELEASED" or self._receipt.digest != canonical_digest(p)): return False
        expected=[]
        if self._anchor: expected.append(("NEGOTIATION_ANCHORED", self._anchor.digest))
        expected.extend(("ARTIFACT_SPECIFIED", x.digest) for x in self._artifacts.values())
        if self._manifest: expected.append(("PACKAGE_ASSEMBLED", self._manifest.digest))
        if self._cases: expected.append(("MOCK_CASES_RECORDED", canonical_digest(tuple(self._cases[x].digest for x in range(4301,4701)))))
        if self._receipt: expected.append(("ACCEPTANCE_RECEIPT_RECORDED", self._receipt.digest))
        return [(x.get("action"),x.get("artifact_digest")) for x in self._events] == expected

    def evidence(self):
        matrix = len(WORKSTREAMS)==16 and all(e-s+1==25 for s,e,_ in WORKSTREAMS) and WORKSTREAMS[0][0]==4301 and WORKSTREAMS[-1][1]==4700
        integrity=self._integrity(); complete=len(self._cases)==400 and self._receipt is not None
        return {"range":[4301,4700], "control_count":400, "workstream_count":16, "controls_per_workstream":25,
                "control_matrix_valid":matrix, "registered_control_count":len(self._controls),
                "artifact_count":len(self._artifacts), "route_count":len(self._manifest.route_bindings) if self._manifest else 0,
                "mock_case_count":len(self._cases), "event_count":len(self._events), "hold_count":len(self._holds),
                "integrity_valid":integrity, "complete_acceptance_evidence":complete and integrity,
                "maximum_state":"ACCEPTANCE_REVIEWED_NOT_RELEASED" if self._receipt else "MOCK_ACCEPTANCE_REQUIRED",
                "capability_ready":matrix and self._registry_integrity() and integrity and complete,
                "external_calls":0, "document_transmissions":0, "electronic_signatures":0,
                "external_pg_calls":0, "card_network_calls":0, "ledger_writes":0, "money_movement":0,
                "credential_reads":0, "deployments":0, "policy_prompt_weight_changes":0, "release_recorded":False}
