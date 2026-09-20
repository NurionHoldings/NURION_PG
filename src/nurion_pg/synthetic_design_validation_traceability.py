"""Synthetic, in-memory, non-authorizing design validation controls #3501-#3900."""
from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest


WORKSTREAM_NAMES = (
    "BASELINE_REQUIREMENT_LINKAGE", "THREAT_ACCEPTANCE_TRACEABILITY",
    "TRUST_BOUNDARY_FLOW_VALIDATION", "TOKENIZED_DATA_CONSTRAINTS",
    "FUND_LEDGER_INVARIANT_PROOFS", "LIFECYCLE_TRANSITION_PROOFS",
    "TENANT_AGENCY_PARTY_ROLE_CONTRACT", "TENANT_TO_NURION_DOCUMENT_SCHEMA",
    "NURION_TO_UPSTREAM_DOCUMENT_SCHEMA", "BIDIRECTIONAL_FIELD_MAPPING",
    "CORRELATION_IDEMPOTENCY_RECEIPTS", "CONSENT_APPROVAL_HOLD_GATES",
    "DOCUMENT_VERSION_PROVENANCE", "INERT_ADAPTER_DRAFT_ISOLATION",
    "PARTIAL_BATCH_APPEND_ONLY_CHAIN", "OPERATOR_GATE_NON_EXECUTION_BOUNDARY",
)
WORKSTREAMS = tuple((3501 + i * 25, 3525 + i * 25, name)
                    for i, name in enumerate(WORKSTREAM_NAMES))
CONTROL_ASPECTS = (
    "input_schema", "required_fields", "identifier_namespace", "tenant_scope",
    "role_scope", "state_precondition", "state_postcondition", "version_binding",
    "source_binding", "digest_binding", "negative_path", "missing_input",
    "duplicate_input", "replay", "conflict", "stale_version", "concurrency",
    "partial_batch", "ordering", "append_only", "hold_propagation",
    "review_independence", "receipt_lineage", "operator_gate", "non_execution",
)
OWNER_ROLES = frozenset({"PRODUCT", "SECURITY", "COMPLIANCE", "LEDGER", "PAYMENTS",
                         "SETTLEMENT", "SRE", "UX"})
ALLOWED_RESULTS = frozenset({"PASS", "EXPECTED_REJECTION"})
MAX_REVIEW_BATCH = 20
MAXIMUM_STATE = "SYNTHETIC_VALIDATION_TRACEABILITY_RECORDED"
BASELINE_RANGE = (3101, 3500)


def _syn(value, kind):
    return isinstance(value, str) and value.startswith(f"synthetic:{kind}:")


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _identity(value):
    return value.rsplit(":", 1)[-1]


@dataclass(frozen=True)
class BaselineAnchor:
    anchor_id: str
    baseline_range: tuple[int, int]
    baseline_commit: str
    baseline_evidence_digest: str
    reviewed: bool
    digest: str


@dataclass(frozen=True)
class ValidationClaim:
    claim_id: str
    control_id: int
    workstream: str
    aspect: str
    anchor_id: str
    requirement_ref: str
    threat: str
    input_fixture_digest: str
    expected_result: str
    evidence_digest: str
    source_version: int
    owner_role: str
    operator_approval_required: bool
    digest: str


@dataclass(frozen=True)
class ValidationDossier:
    dossier_id: str
    author: str
    anchor_id: str
    claim_ids: tuple[str, ...]
    status: str
    version: int
    previous_digest: str | None
    digest: str


@dataclass(frozen=True)
class ValidationReview:
    review_id: str
    dossier_id: str
    source_version: int
    reviewer: str
    accepted: bool
    finding_digest: str
    dossier_digest: str
    digest: str


@dataclass(frozen=True)
class ValidationReceipt:
    receipt_id: str
    dossier_id: str
    source_version: int
    verifier: str
    review_digest: str
    claim_set_digest: str
    operator_approval_required: bool
    approval_recorded: bool
    digest: str


@dataclass(frozen=True)
class ElectronicDocumentDraft:
    document_id: str
    dossier_id: str
    dossier_digest: str
    receipt_digest: str
    flow: str
    sender_role: str
    receiver_role: str
    schema_id: str
    schema_version: int
    correlation_id: str
    idempotency_key: str
    field_mapping: tuple[tuple[str, str], ...]
    parent_document_digest: str | None
    status: str
    consent_recorded: bool
    approval_recorded: bool
    digest: str


@dataclass(frozen=True)
class AdapterDraft:
    adapter_id: str
    dossier_id: str
    dossier_digest: str
    receipt_digest: str
    party_role: str
    inbound_schema_id: str
    outbound_schema_id: str
    schema_version: int
    document_digests: tuple[str, ...]
    mode: str
    transport_enabled: bool
    signing_enabled: bool
    external_api_enabled: bool
    digest: str


class SyntheticDesignValidationTraceability:
    """Validation registry only; deliberately has no payment or operational adapter."""

    def __init__(self):
        self._anchors = {}
        self._claims = {}
        self._control_claims = {}
        self._dossiers = {}
        self._history = []
        self._reviews = {}
        self._dossier_reviews = {}
        self._receipts = {}
        self._dossier_receipts = {}
        self._members = {}
        self._events = []
        self._holds = []
        self._documents = {}
        self._adapters = {}
        self._integration_events = []
        self._lock = RLock()

    @staticmethod
    def anchor_digest(anchor_id, baseline_range, baseline_commit, baseline_evidence_digest, reviewed):
        return canonical_digest(locals())

    @staticmethod
    def claim_digest(claim_id, control_id, workstream, aspect, anchor_id, requirement_ref,
                     threat, input_fixture_digest, expected_result, evidence_digest,
                     source_version, owner_role, operator_approval_required):
        return canonical_digest(locals())

    @staticmethod
    def dossier_digest(dossier_id, author, anchor_id, claim_ids, status, version, previous_digest):
        return canonical_digest(locals())

    def add_anchor(self, anchor_id, baseline_commit, baseline_evidence_digest, reviewed=True):
        payload = dict(anchor_id=anchor_id, baseline_range=BASELINE_RANGE,
                       baseline_commit=baseline_commit,
                       baseline_evidence_digest=baseline_evidence_digest, reviewed=reviewed)
        row = BaselineAnchor(**payload, digest=self.anchor_digest(**payload))
        with self._lock:
            if not self._valid_anchor(row):
                raise GovernanceRejected("reviewed P0 baseline anchor required")
            prior = self._anchors.get(anchor_id)
            if prior:
                if prior == row:
                    return prior
                raise GovernanceRejected("anchor conflict")
            if self._anchors:
                raise GovernanceRejected("single baseline anchor required")
            self._anchors[anchor_id] = row
            return row

    def add_claim(self, claim_id, control_id, workstream, aspect, anchor_id,
                  requirement_ref, threat, input_fixture_digest, expected_result,
                  evidence_digest, source_version, owner_role,
                  operator_approval_required=True):
        payload = dict(claim_id=claim_id, control_id=control_id, workstream=workstream,
                       aspect=aspect, anchor_id=anchor_id, requirement_ref=requirement_ref,
                       threat=threat, input_fixture_digest=input_fixture_digest,
                       expected_result=expected_result, evidence_digest=evidence_digest,
                       source_version=source_version, owner_role=owner_role,
                       operator_approval_required=operator_approval_required)
        row = ValidationClaim(**payload, digest=self.claim_digest(**payload))
        with self._lock:
            if not self._valid_claim(row):
                raise GovernanceRejected("semantically complete validation claim required")
            prior = self._claims.get(claim_id)
            if prior:
                if prior == row:
                    return prior
                raise GovernanceRejected("claim conflict")
            if control_id in self._control_claims:
                raise GovernanceRejected("control already claimed")
            self._claims[claim_id] = row
            self._control_claims[control_id] = claim_id
            return row

    def author(self, dossier_id, author, anchor_id, claim_ids):
        claim_ids = tuple(claim_ids)
        with self._lock:
            prior = self._dossiers.get(dossier_id)
            if prior:
                if (prior.author, prior.anchor_id, prior.claim_ids) == (author, anchor_id, claim_ids):
                    return prior
                raise GovernanceRejected("dossier conflict")
            claims = [self._claims.get(x) for x in claim_ids]
            if (not _syn(dossier_id, "validation-dossier") or not _syn(author, "validation-author")
                    or anchor_id not in self._anchors or len(claim_ids) != 400
                    or len(set(claim_ids)) != 400 or any(x is None for x in claims)
                    or {x.control_id for x in claims} != set(range(3501, 3901))
                    or any(x.anchor_id != anchor_id for x in claims)
                    or any(x in self._members for x in claim_ids)
                    or not self._registry_integrity()):
                raise GovernanceRejected("complete unassigned 400-control dossier required")
            base = dict(dossier_id=dossier_id, author=author, anchor_id=anchor_id,
                        claim_ids=claim_ids, status="DRAFTED", version=1, previous_digest=None)
            row = ValidationDossier(**base, digest=self.dossier_digest(**base))
            for claim_id in claim_ids:
                self._members[claim_id] = dossier_id
            return self._append("DOSSIER_DRAFTED", row)

    def review(self, review_id, dossier_id, expected_version, reviewer, accepted, finding_digest):
        with self._lock:
            prior = self._reviews.get(review_id)
            args = (dossier_id, expected_version, reviewer, accepted, finding_digest)
            if prior:
                if args == (prior.dossier_id, prior.source_version, prior.reviewer,
                            prior.accepted, prior.finding_digest):
                    return self._dossiers[dossier_id]
                raise GovernanceRejected("review conflict")
            old = self._dossiers.get(dossier_id)
            if (old is None or old.status != "DRAFTED" or old.version != expected_version
                    or not _syn(review_id, "validation-review")
                    or not _syn(reviewer, "validation-reviewer") or not isinstance(accepted, bool)
                    or not _hex(finding_digest) or _identity(reviewer) in self._roles(old)
                    or dossier_id in self._dossier_reviews or not self._integrity()):
                raise GovernanceRejected("independent current complete review required")
            payload = dict(review_id=review_id, dossier_id=dossier_id,
                           source_version=expected_version, reviewer=reviewer,
                           accepted=accepted, finding_digest=finding_digest,
                           dossier_digest=old.digest)
            artifact = ValidationReview(**payload, digest=canonical_digest(payload))
            self._reviews[review_id] = artifact
            self._dossier_reviews[dossier_id] = review_id
            row = self._transition(old, "DOSSIER_REVIEWED" if accepted else "DOSSIER_HELD",
                                   "REVIEWED" if accepted else "HELD", artifact.digest)
            if not accepted:
                self._hold(row, reviewer, "REVIEW_REJECTED", artifact.digest)
            return row

    def record(self, receipt_id, dossier_id, expected_version, verifier, review_digest):
        with self._lock:
            prior = self._receipts.get(receipt_id)
            args = (dossier_id, expected_version, verifier, review_digest)
            if prior:
                if args == (prior.dossier_id, prior.source_version, prior.verifier, prior.review_digest):
                    return self._dossiers[dossier_id]
                raise GovernanceRejected("receipt conflict")
            old = self._dossiers.get(dossier_id)
            review = self._reviews.get(self._dossier_reviews.get(dossier_id, ""))
            if (old is None or old.status != "REVIEWED" or old.version != expected_version
                    or review is None or not review.accepted or review.digest != review_digest
                    or not _syn(receipt_id, "validation-receipt")
                    or not _syn(verifier, "validation-verifier")
                    or _identity(verifier) in self._roles(old)
                    or dossier_id in self._dossier_receipts or not self._integrity()):
                raise GovernanceRejected("reviewed current dossier required")
            claim_set_digest = canonical_digest(tuple(sorted(self._claims[x].digest for x in old.claim_ids)))
            payload = dict(receipt_id=receipt_id, dossier_id=dossier_id,
                           source_version=expected_version, verifier=verifier,
                           review_digest=review_digest, claim_set_digest=claim_set_digest,
                           operator_approval_required=True, approval_recorded=False)
            receipt = ValidationReceipt(**payload, digest=canonical_digest(payload))
            self._receipts[receipt_id] = receipt
            self._dossier_receipts[dossier_id] = receipt_id
            return self._transition(old, "DOSSIER_RECEIPT_RECORDED", MAXIMUM_STATE, receipt.digest)

    def audit_hold(self, dossier_id, expected_version, auditor, finding_digest):
        with self._lock:
            old = self._dossiers.get(dossier_id)
            if (old is None or old.status == "HELD" or old.version != expected_version
                    or not _syn(auditor, "validation-auditor") or not _hex(finding_digest)
                    or _identity(auditor) in self._roles(old) or not self._integrity()):
                raise GovernanceRejected("independent current audit required")
            row = self._transition(old, "DOSSIER_HELD", "HELD", finding_digest)
            self._hold(row, auditor, "AUDIT_FINDING", finding_digest)
            return row

    def generate_integration_drafts(self, dossier_id, tenant_id, upstream_id, schema_version,
                                    correlation_id, idempotency_key, field_mapping):
        """Create inert three-party document/adapter specifications; never transmit or sign."""
        mapping = tuple(tuple(x) for x in field_mapping)
        with self._lock:
            dossier = self._dossiers.get(dossier_id)
            if (dossier is None or dossier.status != MAXIMUM_STATE or not self._integrity()
                    or not _syn(tenant_id, "tenant") or not _syn(upstream_id, "upstream-pg")
                    or not isinstance(schema_version, int) or schema_version < 1
                    or not _syn(correlation_id, "correlation")
                    or not _syn(idempotency_key, "idempotency")
                    or not mapping or len(mapping) != len(set(mapping))
                    or any(len(x) != 2 or not all(isinstance(v, str) and v.strip() for v in x)
                           for x in mapping)):
                raise GovernanceRejected("complete recorded synthetic integration draft input required")
            if self._documents or self._adapters:
                existing = self.integration_drafts()
                request = (dossier_id, tenant_id, upstream_id, schema_version, correlation_id,
                           idempotency_key, mapping)
                if existing["request"] == request:
                    return existing
                raise GovernanceRejected("integration draft conflict")
            flows = (
                ("tenant_to_nurion", tenant_id, "NURION_PG", None),
                ("nurion_to_upstream", "NURION_PG", upstream_id, "tenant_to_nurion"),
                ("upstream_to_nurion", upstream_id, "NURION_PG", "nurion_to_upstream"),
                ("nurion_to_tenant", "NURION_PG", tenant_id, "upstream_to_nurion"),
            )
            receipt = self._receipts.get(self._dossier_receipts.get(dossier_id, ""))
            if receipt is None:
                raise GovernanceRejected("recorded dossier receipt required")
            by_flow = {}
            for flow, sender, receiver, parent_flow in flows:
                parent = by_flow.get(parent_flow)
                payload = dict(document_id=f"synthetic:electronic-document:{flow}",
                               dossier_id=dossier_id, dossier_digest=dossier.digest,
                               receipt_digest=receipt.digest, flow=flow,
                               sender_role=sender, receiver_role=receiver,
                               schema_id=f"synthetic:schema:{flow}", schema_version=schema_version,
                               correlation_id=correlation_id, idempotency_key=idempotency_key,
                               field_mapping=mapping, parent_document_digest=parent.digest if parent else None,
                               status="DRAFT_ONLY", consent_recorded=False, approval_recorded=False)
                row = ElectronicDocumentDraft(**payload, digest=canonical_digest(payload))
                self._documents[row.document_id] = row
                self._append_integration_event("DOCUMENT_DRAFTED", row.document_id, row.digest,
                                               dossier.digest, receipt.digest)
                by_flow[flow] = row
            adapter_specs = (
                ("tenant", tenant_id, by_flow["nurion_to_tenant"].schema_id,
                 by_flow["tenant_to_nurion"].schema_id,
                 (by_flow["tenant_to_nurion"].digest, by_flow["nurion_to_tenant"].digest)),
                ("nurion", "NURION_PG", by_flow["tenant_to_nurion"].schema_id,
                 by_flow["nurion_to_upstream"].schema_id, tuple(x.digest for x in by_flow.values())),
                ("upstream", upstream_id, by_flow["nurion_to_upstream"].schema_id,
                 by_flow["upstream_to_nurion"].schema_id,
                 (by_flow["nurion_to_upstream"].digest, by_flow["upstream_to_nurion"].digest)),
            )
            for name, party, inbound, outbound, digests in adapter_specs:
                payload = dict(adapter_id=f"synthetic:adapter-draft:{name}",
                               dossier_id=dossier_id, dossier_digest=dossier.digest,
                               receipt_digest=receipt.digest, party_role=party,
                               inbound_schema_id=inbound, outbound_schema_id=outbound,
                               schema_version=schema_version, document_digests=digests,
                               mode="SPECIFICATION_ONLY", transport_enabled=False,
                               signing_enabled=False, external_api_enabled=False)
                row = AdapterDraft(**payload, digest=canonical_digest(payload))
                self._adapters[row.adapter_id] = row
                self._append_integration_event("ADAPTER_SPECIFIED", row.adapter_id, row.digest,
                                               dossier.digest, receipt.digest)
            self._integration_request = (dossier_id, tenant_id, upstream_id, schema_version, correlation_id,
                                         idempotency_key, mapping)
            if not self._integration_integrity():
                self._documents.clear(); self._adapters.clear(); self._integration_events.clear()
                raise GovernanceRejected("integration lineage invalid")
            return self.integration_drafts()

    def integration_drafts(self):
        return {"request": getattr(self, "_integration_request", None),
                "documents": tuple(self._documents.values()),
                "adapters": tuple(self._adapters.values())}

    def _append_integration_event(self, action, artifact_id, artifact_digest,
                                  dossier_digest, receipt_digest):
        previous = self._integration_events[-1]["digest"] if self._integration_events else None
        payload = dict(sequence=len(self._integration_events) + 1, action=action,
                       artifact_id=artifact_id, artifact_digest=artifact_digest,
                       dossier_digest=dossier_digest, receipt_digest=receipt_digest,
                       previous_digest=previous)
        self._integration_events.append({**payload, "digest": canonical_digest(payload)})

    def review_batch(self, reviewer, dossier_ids):
        ids = tuple(dossier_ids)
        if (not _syn(reviewer, "validation-reviewer") or not 1 <= len(ids) <= MAX_REVIEW_BATCH
                or len(set(ids)) != len(ids)):
            raise GovernanceRejected("bounded unique review batch required")
        rows = [self._dossiers.get(x) for x in ids]
        if any(row is None or row.status != "DRAFTED" or _identity(reviewer) in self._roles(row)
               for row in rows):
            raise GovernanceRejected("complete independent draft batch required")
        return tuple(rows)

    def artifact(self, review_id):
        return self._reviews[review_id]

    def _expected(self, control_id):
        index = control_id - 3501
        return WORKSTREAM_NAMES[index // 25], CONTROL_ASPECTS[index % 25]

    def _valid_anchor(self, row):
        p = {k: v for k, v in row.__dict__.items() if k != "digest"}
        return (_syn(row.anchor_id, "p0-anchor") and row.baseline_range == BASELINE_RANGE
                and _hex(row.baseline_commit) and _hex(row.baseline_evidence_digest)
                and row.reviewed is True and row.digest == self.anchor_digest(**p))

    def _valid_claim(self, row):
        p = {k: v for k, v in row.__dict__.items() if k != "digest"}
        expected = self._expected(row.control_id) if isinstance(row.control_id, int) and 3501 <= row.control_id <= 3900 else None
        anchor = self._anchors.get(row.anchor_id)
        requirement = f"synthetic:p0-requirement:{(row.control_id - 3501) // 25:02}"
        return (expected == (row.workstream, row.aspect) and _syn(row.claim_id, "validation-claim")
                and anchor is not None and self._valid_anchor(anchor)
                and row.requirement_ref == requirement and bool(row.threat.strip())
                and _hex(row.input_fixture_digest) and row.expected_result in ALLOWED_RESULTS
                and _hex(row.evidence_digest) and isinstance(row.source_version, int)
                and row.source_version >= 1 and row.owner_role in OWNER_ROLES
                and row.operator_approval_required is True
                and row.digest == self.claim_digest(**p))

    def _registry_integrity(self):
        if len(self._anchors) != 1 or any(k != x.anchor_id or not self._valid_anchor(x)
                                          for k, x in self._anchors.items()):
            return False
        if any(k != x.claim_id or not self._valid_claim(x) for k, x in self._claims.items()):
            return False
        return (self._control_claims == {x.control_id: x.claim_id for x in self._claims.values()}
                and len(self._control_claims) == len(self._claims))

    def _roles(self, row):
        roles = {_identity(row.author)}
        review = self._reviews.get(self._dossier_reviews.get(row.dossier_id, ""))
        receipt = self._receipts.get(self._dossier_receipts.get(row.dossier_id, ""))
        if review:
            roles.add(_identity(review.reviewer))
        if receipt:
            roles.add(_identity(receipt.verifier))
        return roles

    def _append(self, action, row, attachment=None):
        previous = self._events[-1]["digest"] if self._events else None
        payload = dict(sequence=len(self._events) + 1, action=action,
                       dossier_digest=row.digest, attachment_digest=attachment,
                       previous_digest=previous)
        self._events.append({**payload, "digest": canonical_digest(payload)})
        self._history.append(row)
        self._dossiers[row.dossier_id] = row
        return row

    def _transition(self, old, action, status, attachment):
        values = old.__dict__ | {"status": status, "version": old.version + 1,
                                 "previous_digest": old.digest}
        values["digest"] = self.dossier_digest(**{k: v for k, v in values.items() if k != "digest"})
        return self._append(action, ValidationDossier(**values), attachment)

    def _hold(self, row, actor, reason, attachment):
        previous = self._holds[-1]["digest"] if self._holds else None
        payload = dict(sequence=len(self._holds) + 1, dossier_id=row.dossier_id,
                       actor=actor, reason=reason, dossier_digest=row.digest,
                       attachment_digest=attachment, previous_digest=previous)
        self._holds.append({**payload, "digest": canonical_digest(payload)})

    def _dossier_integrity(self):
        latest, versions, previous = {}, {}, {}
        for row in self._history:
            claims = [self._claims.get(x) for x in row.claim_ids]
            prior = latest.get(row.dossier_id)
            transition = ((prior is None and row.version == 1 and row.status == "DRAFTED")
                          or (prior and prior.status == "DRAFTED" and row.status in {"REVIEWED", "HELD"})
                          or (prior and prior.status == "REVIEWED" and row.status in {MAXIMUM_STATE, "HELD"})
                          or (prior and prior.status == MAXIMUM_STATE and row.status == "HELD"))
            p = {k: v for k, v in row.__dict__.items() if k != "digest"}
            if (not transition or row.version != versions.get(row.dossier_id, 0) + 1
                    or row.previous_digest != previous.get(row.dossier_id)
                    or not _syn(row.dossier_id, "validation-dossier")
                    or not _syn(row.author, "validation-author") or len(claims) != 400
                    or any(x is None for x in claims)
                    or {x.control_id for x in claims} != set(range(3501, 3901))
                    or any(x.anchor_id != row.anchor_id for x in claims)
                    or row.digest != self.dossier_digest(**p)):
                return False
            latest[row.dossier_id] = row
            versions[row.dossier_id] = row.version
            previous[row.dossier_id] = row.digest
        expected = {claim_id: row.dossier_id for row in self._history if row.version == 1
                    for claim_id in row.claim_ids}
        return latest == self._dossiers and expected == self._members

    def _artifact_integrity(self):
        history = {(x.dossier_id, x.version): x for x in self._history}
        for key, artifact in self._reviews.items():
            p = {k: v for k, v in artifact.__dict__.items() if k != "digest"}
            source = history.get((artifact.dossier_id, artifact.source_version))
            output = history.get((artifact.dossier_id, artifact.source_version + 1))
            if (key != artifact.review_id or self._dossier_reviews.get(artifact.dossier_id) != key
                    or source is None or output is None or source.status != "DRAFTED"
                    or output.status != ("REVIEWED" if artifact.accepted else "HELD")
                    or not _syn(artifact.review_id, "validation-review")
                    or not _syn(artifact.reviewer, "validation-reviewer")
                    or not isinstance(artifact.accepted, bool) or not _hex(artifact.finding_digest)
                    or artifact.dossier_digest != source.digest
                    or _identity(artifact.reviewer) == _identity(source.author)
                    or artifact.digest != canonical_digest(p)):
                return False
        for key, artifact in self._receipts.items():
            p = {k: v for k, v in artifact.__dict__.items() if k != "digest"}
            review = self._reviews.get(self._dossier_reviews.get(artifact.dossier_id, ""))
            source = history.get((artifact.dossier_id, artifact.source_version))
            output = history.get((artifact.dossier_id, artifact.source_version + 1))
            claim_set = canonical_digest(tuple(sorted(self._claims[x].digest for x in source.claim_ids))) if source else None
            if (key != artifact.receipt_id or self._dossier_receipts.get(artifact.dossier_id) != key
                    or review is None or not review.accepted or source is None or output is None
                    or source.status != "REVIEWED" or output.status != MAXIMUM_STATE
                    or artifact.source_version != review.source_version + 1
                    or artifact.review_digest != review.digest or artifact.claim_set_digest != claim_set
                    or not _syn(artifact.receipt_id, "validation-receipt")
                    or not _syn(artifact.verifier, "validation-verifier")
                    or _identity(artifact.verifier) in {_identity(source.author), _identity(review.reviewer)}
                    or not artifact.operator_approval_required or artifact.approval_recorded
                    or artifact.digest != canonical_digest(p)):
                return False
        return True

    def _chain_integrity(self):
        if len(self._events) != len(self._history):
            return False
        previous = None
        actions = {"DRAFTED": "DOSSIER_DRAFTED", "REVIEWED": "DOSSIER_REVIEWED",
                   "HELD": "DOSSIER_HELD", MAXIMUM_STATE: "DOSSIER_RECEIPT_RECORDED"}
        for index, (event, row) in enumerate(zip(self._events, self._history), 1):
            if row.status == "DRAFTED":
                attachment = None
            elif row.status == "REVIEWED":
                item = self._reviews.get(self._dossier_reviews.get(row.dossier_id, "")); attachment = item.digest if item else None
            elif row.status == MAXIMUM_STATE:
                item = self._receipts.get(self._dossier_receipts.get(row.dossier_id, "")); attachment = item.digest if item else None
            else:
                item = next((x for x in self._holds if x.get("dossier_digest") == row.digest), None); attachment = item.get("attachment_digest") if item else None
            payload = dict(sequence=index, action=event.get("action"), dossier_digest=row.digest,
                           attachment_digest=event.get("attachment_digest"), previous_digest=previous)
            if (event.get("action") != actions[row.status]
                    or event.get("attachment_digest") != attachment
                    or event != {**payload, "digest": canonical_digest(payload)}):
                return False
            previous = event["digest"]
        previous = None
        for index, hold in enumerate(self._holds, 1):
            payload = {k: hold.get(k) for k in ("sequence", "dossier_id", "actor", "reason",
                                                "dossier_digest", "attachment_digest", "previous_digest")}
            row = next((x for x in self._history if x.digest == hold.get("dossier_digest")), None)
            review = self._reviews.get(self._dossier_reviews.get(str(hold.get("dossier_id")), ""))
            semantic = ((hold.get("reason") == "REVIEW_REJECTED" and review is not None
                         and not review.accepted and hold.get("actor") == review.reviewer
                         and hold.get("attachment_digest") == review.digest)
                        or (hold.get("reason") == "AUDIT_FINDING" and row is not None
                            and _syn(hold.get("actor"), "validation-auditor")
                            and _identity(hold.get("actor")) not in self._roles(row)
                            and _hex(hold.get("attachment_digest"))))
            if (hold.get("sequence") != index or hold.get("previous_digest") != previous
                    or not semantic or hold != {**payload, "digest": canonical_digest(payload)}):
                return False
            previous = hold["digest"]
        return True

    def _integrity(self):
        return (self._registry_integrity() and self._dossier_integrity()
                and self._artifact_integrity() and self._chain_integrity()
                and self._integration_integrity())

    def _integration_integrity(self):
        if not self._documents and not self._adapters:
            return True
        if len(self._documents) != 4 or len(self._adapters) != 3:
            return False
        ordered = [self._documents.get(f"synthetic:electronic-document:{flow}") for flow in
                   ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")]
        if any(x is None for x in ordered):
            return False
        previous = None
        request = getattr(self, "_integration_request", None)
        if request is None:
            return False
        dossier_id, tenant, upstream, version, correlation, idempotency, mapping = request
        dossier = self._dossiers.get(dossier_id)
        receipt = self._receipts.get(self._dossier_receipts.get(dossier_id, ""))
        if dossier is None or dossier.status != MAXIMUM_STATE or receipt is None:
            return False
        flows = ("tenant_to_nurion", "nurion_to_upstream", "upstream_to_nurion", "nurion_to_tenant")
        roles = ((tenant, "NURION_PG"), ("NURION_PG", upstream),
                 (upstream, "NURION_PG"), ("NURION_PG", tenant))
        for row, flow, pair in zip(ordered, flows, roles):
            payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
            if (row.flow != flow or row.schema_id != f"synthetic:schema:{flow}"
                    or row.dossier_id != dossier_id or row.dossier_digest != dossier.digest
                    or row.receipt_digest != receipt.digest
                    or (row.sender_role, row.receiver_role) != pair or row.schema_version != version
                    or row.correlation_id != correlation or row.idempotency_key != idempotency
                    or row.field_mapping != mapping or row.parent_document_digest != previous
                    or row.status != "DRAFT_ONLY" or row.consent_recorded or row.approval_recorded
                    or row.digest != canonical_digest(payload)):
                return False
            previous = row.digest
        known = {x.digest for x in ordered}
        expected_adapters = {
            "synthetic:adapter-draft:tenant": (tenant, ordered[3].schema_id, ordered[0].schema_id,
                                                (ordered[0].digest, ordered[3].digest)),
            "synthetic:adapter-draft:nurion": ("NURION_PG", ordered[0].schema_id, ordered[1].schema_id,
                                                tuple(x.digest for x in ordered)),
            "synthetic:adapter-draft:upstream": (upstream, ordered[1].schema_id, ordered[2].schema_id,
                                                  (ordered[1].digest, ordered[2].digest)),
        }
        for key, row in self._adapters.items():
            payload = {k: v for k, v in row.__dict__.items() if k != "digest"}
            expected = expected_adapters.get(key)
            if (key != row.adapter_id or not _syn(row.adapter_id, "adapter-draft")
                    or row.dossier_id != dossier_id or row.dossier_digest != dossier.digest
                    or row.receipt_digest != receipt.digest
                    or expected is None
                    or (row.party_role, row.inbound_schema_id, row.outbound_schema_id,
                        row.document_digests) != expected
                    or row.schema_version != version or not row.document_digests
                    or any(x not in known for x in row.document_digests)
                    or row.mode != "SPECIFICATION_ONLY" or row.transport_enabled
                    or row.signing_enabled or row.external_api_enabled
                    or row.digest != canonical_digest(payload)):
                return False
        artifacts = [*ordered, *self._adapters.values()]
        if len(self._integration_events) != len(artifacts):
            return False
        previous = None
        for index, (event, artifact) in enumerate(zip(self._integration_events, artifacts), 1):
            action = "DOCUMENT_DRAFTED" if isinstance(artifact, ElectronicDocumentDraft) else "ADAPTER_SPECIFIED"
            payload = dict(sequence=index, action=action, artifact_id=(artifact.document_id
                           if isinstance(artifact, ElectronicDocumentDraft) else artifact.adapter_id),
                           artifact_digest=artifact.digest, dossier_digest=dossier.digest,
                           receipt_digest=receipt.digest, previous_digest=previous)
            if event != {**payload, "digest": canonical_digest(payload)}:
                return False
            previous = event["digest"]
        return True

    def evidence(self):
        observed = [n for start, end, _ in WORKSTREAMS for n in range(start, end + 1)]
        matrix = (len(WORKSTREAMS) == 16 and observed == list(range(3501, 3901))
                  and len(CONTROL_ASPECTS) == 25 and all(end - start == 24 for start, end, _ in WORKSTREAMS))
        coverage = set(self._control_claims) == set(range(3501, 3901))
        checks = {"control_matrix": matrix, "coverage": coverage,
                  "registry": self._registry_integrity(), "dossier": self._dossier_integrity(),
                  "artifact": self._artifact_integrity(), "append_only": self._chain_integrity(),
                  "integration": self._integration_integrity()}
        gaps = tuple(k for k, valid in checks.items() if not valid)
        return {
            "control_range": [3501, 3900], "control_count": 400,
            "workstream_count": 16, "controls_per_workstream": 25,
            "workstreams": list(WORKSTREAM_NAMES), "control_aspects": list(CONTROL_ASPECTS),
            "control_matrix_valid": matrix, "claim_coverage_complete": coverage,
            "anchor_count": len(self._anchors), "claim_count": len(self._claims),
            "dossier_count": len(self._dossiers), "registry_integrity_valid": checks["registry"],
            "dossier_integrity_valid": checks["dossier"], "artifact_integrity_valid": checks["artifact"],
            "append_only_chain_valid": checks["append_only"], "integrity_valid": all(checks.values()),
            "integration_lineage_valid": checks["integration"],
            "electronic_document_draft_count": len(self._documents),
            "adapter_draft_count": len(self._adapters), "document_status": "DRAFT_ONLY",
            "integration_event_count": len(self._integration_events),
            "bidirectional_parties": ["TENANT_AGENCY", "NURION_PG", "UPSTREAM_PG"],
            "capability_ready": not gaps, "capability_gap_evidence": {"fail_closed": bool(gaps), "gaps": gaps},
            "maximum_review_batch": MAX_REVIEW_BATCH, "operator_approval_required": True,
            "approval_recorded": False, "non_authorizing": True, "synthetic_only": True,
            "in_memory_only": True, "non_deployable": True, "free_prompt_generation": False,
            "external_calls": 0, "external_pg_calls": 0, "card_network_calls": 0,
            "credential_reads": 0, "ledger_writes": 0, "money_movement": 0,
            "runtime_policy_mutations": 0, "document_transmissions": 0,
            "electronic_signatures": 0, "external_registrations": 0,
            "maximum_state": MAXIMUM_STATE,
        }
