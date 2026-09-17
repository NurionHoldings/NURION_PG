"""Metadata-only synthetic patch draft manifests from patch decision receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .patch_operator_decision_intake import SyntheticPatchOperatorDecision
from .patch_operator_decision_receipt_ledger import (
    SyntheticPatchDecisionReceipt,
    SyntheticPatchDecisionReceiptLedger,
)


PATCH_DRAFT_MANIFEST_STATE = "SYNTHETIC_PATCH_DRAFT_MANIFESTED"
ALLOWED_PATCH_DRAFT_SCOPES = (
    "SYNTHETIC_FIXTURE_PATCH_DRAFT_ONLY",
    "TEST_HARDENING_PATCH_DRAFT_ONLY",
    "POLICY_CLARIFICATION_PATCH_DRAFT_ONLY",
    "DOCUMENTATION_PATCH_DRAFT_ONLY",
)
REQUIRED_PATCH_DRAFT_CHECKS = (
    "PRESERVE_FAIL_CLOSED_BASELINE",
    "REPRODUCE_SOURCE_SHA256_EVIDENCE",
    "DECLARE_OPAQUE_TARGET_DIGESTS_ONLY",
    "NO_PATCH_CONTENT_OR_DIFF",
    "RUN_SYNTHETIC_REGRESSION",
    "RUN_CONCURRENCY_AND_FAILURE_TESTS_WHEN_APPLICABLE",
    "ETERNIAN_REVIEW_REQUIRED_BEFORE_PATCH_SHADOW",
    "SEPARATE_PATCH_SHADOW_REQUIRED",
    "OPERATOR_APPROVAL_REQUIRED_BEFORE_LIMITED_PROMOTION",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_scopes(scopes: tuple[str, ...]) -> bool:
    if not scopes or len(scopes) != len(set(scopes)):
        return False
    expected = tuple(scope for scope in ALLOWED_PATCH_DRAFT_SCOPES if scope in scopes)
    return scopes == expected


def _manifest_id(
    receipt_id: str,
    receipt_digest: str,
    scopes: tuple[str, ...],
    target_digests: tuple[str, ...],
) -> str:
    identity = canonical_digest(
        {
            "source_receipt_id": receipt_id,
            "source_receipt_digest": receipt_digest,
            "draft_scopes": list(scopes),
            "target_path_digests": list(target_digests),
        }
    )
    return "synthetic:patch-draft-manifest:" + identity[:32]


@dataclass(frozen=True)
class SyntheticPatchDraftManifest:
    sequence: int
    manifest_id: str
    source_receipt_id: str
    source_receipt_digest: str
    source_assessment_id: str
    source_packet_id: str
    operator_id: str
    decision: SyntheticPatchOperatorDecision
    draft_scopes: tuple[str, ...]
    target_path_digests: tuple[str, ...]
    required_checks: tuple[str, ...]
    drafted_at: datetime
    previous_digest: str
    manifest_digest: str
    state: str = PATCH_DRAFT_MANIFEST_STATE
    eternian_review_required: bool = True
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    network_access_allowed: bool = False
    money_movement_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or self.manifest_id
            != _manifest_id(
                self.source_receipt_id,
                self.source_receipt_digest,
                self.draft_scopes,
                self.target_path_digests,
            )
            or not self.source_receipt_id.startswith(
                "synthetic:patch-decision-receipt:"
            )
            or not _valid_digest(self.source_receipt_digest)
            or not self.source_assessment_id.startswith(
                "synthetic:patch-operator-decision-assessment:"
            )
            or not self.source_packet_id.startswith(
                "synthetic:patch-operator-decision-packet:"
            )
            or self.operator_id != "synthetic:operator:CHOI_IN_SEOK"
            or self.decision
            is not SyntheticPatchOperatorDecision.AUTHORIZE_SYNTHETIC_PATCH_DRAFT
            or not _valid_scopes(self.draft_scopes)
            or len(self.target_path_digests) != len(self.draft_scopes)
            or len(set(self.target_path_digests)) != len(self.target_path_digests)
            or not all(_valid_digest(item) for item in self.target_path_digests)
            or self.required_checks != REQUIRED_PATCH_DRAFT_CHECKS
            or self.drafted_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.state != PATCH_DRAFT_MANIFEST_STATE
            or not self.eternian_review_required
            or self.patch_content_present
            or self.diff_content_present
            or self.source_code_changed
            or self.filesystem_written
            or self.automatic_application_allowed
            or self.safety_baseline_relaxation_allowed
            or self.execution_allowed
            or self.network_access_allowed
            or self.money_movement_allowed
            or self.production_activation_allowed
            or self.manifest_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid metadata-only synthetic patch draft required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "manifest_id": self.manifest_id,
            "source_receipt_id": self.source_receipt_id,
            "source_receipt_digest": self.source_receipt_digest,
            "source_assessment_id": self.source_assessment_id,
            "source_packet_id": self.source_packet_id,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "draft_scopes": list(self.draft_scopes),
            "target_path_digests": list(self.target_path_digests),
            "required_checks": list(self.required_checks),
            "drafted_at": self.drafted_at.isoformat(),
            "previous_digest": self.previous_digest,
            "state": PATCH_DRAFT_MANIFEST_STATE,
            "eternian_review_required": True,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "network_access_allowed": False,
            "money_movement_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftManifestBook:
    """Creates review-only manifests and exposes no patch generation or apply method."""

    def __init__(self) -> None:
        self._manifests: list[SyntheticPatchDraftManifest] = []
        self._by_receipt: dict[str, SyntheticPatchDraftManifest] = {}
        self._lock = RLock()

    @property
    def manifests(self) -> tuple[SyntheticPatchDraftManifest, ...]:
        with self._lock:
            return tuple(self._manifests)

    def draft_from_receipt(
        self,
        ledger: SyntheticPatchDecisionReceiptLedger,
        receipt_id: str,
        *,
        draft_scopes: tuple[str, ...],
        target_path_digests: tuple[str, ...],
        drafted_at: datetime,
    ) -> SyntheticPatchDraftManifest:
        if drafted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware patch draft time required")
        if not isinstance(ledger, SyntheticPatchDecisionReceiptLedger):
            raise GovernanceRejected("typed synthetic patch receipt ledger required")
        if not _valid_scopes(draft_scopes):
            raise GovernanceRejected("ordered allowlisted patch draft scopes required")
        if (
            len(target_path_digests) != len(draft_scopes)
            or len(set(target_path_digests)) != len(target_path_digests)
            or not all(_valid_digest(item) for item in target_path_digests)
        ):
            raise GovernanceRejected("one unique opaque target digest per scope required")
        if (
            not ledger.verify_metadata()
            or not ledger.verify_audit_chain()
            or not ledger.verify_record_bindings()
        ):
            raise GovernanceRejected("intact synthetic patch receipt ledger required")
        before = ledger.evidence()["report_digest"]
        receipt = ledger.get(receipt_id)
        if (
            receipt.decision
            is not SyntheticPatchOperatorDecision.AUTHORIZE_SYNTHETIC_PATCH_DRAFT
        ):
            raise GovernanceRejected("synthetic patch receipt does not authorize a draft")
        if drafted_at < receipt.recorded_at:
            raise GovernanceRejected("patch draft cannot predate receipt")
        source_digest = receipt.receipt_digest()

        with self._lock:
            existing = self._by_receipt.get(receipt_id)
            if existing is not None:
                if (
                    existing.draft_scopes != draft_scopes
                    or existing.target_path_digests != target_path_digests
                    or existing.source_receipt_digest != source_digest
                    or existing.source_assessment_id != receipt.assessment_id
                    or existing.source_packet_id != receipt.packet_id
                    or existing.operator_id != receipt.operator_id
                    or existing.decision is not receipt.decision
                ):
                    raise GovernanceRejected("patch draft idempotency mismatch")
                if not self.verify_manifest_chain():
                    raise GovernanceRejected("existing patch draft manifest is invalid")
                manifest = existing
                created = False
            else:
                sequence = len(self._manifests) + 1
                previous = self._manifests[-1].manifest_digest if self._manifests else "0" * 64
                manifest_id = _manifest_id(
                    receipt.receipt_id,
                    source_digest,
                    draft_scopes,
                    target_path_digests,
                )
                value = {
                    "sequence": sequence,
                    "manifest_id": manifest_id,
                    "source_receipt_id": receipt.receipt_id,
                    "source_receipt_digest": source_digest,
                    "source_assessment_id": receipt.assessment_id,
                    "source_packet_id": receipt.packet_id,
                    "operator_id": receipt.operator_id,
                    "decision": receipt.decision.value,
                    "draft_scopes": list(draft_scopes),
                    "target_path_digests": list(target_path_digests),
                    "required_checks": list(REQUIRED_PATCH_DRAFT_CHECKS),
                    "drafted_at": drafted_at.isoformat(),
                    "previous_digest": previous,
                    "state": PATCH_DRAFT_MANIFEST_STATE,
                    "eternian_review_required": True,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "automatic_application_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "network_access_allowed": False,
                    "money_movement_allowed": False,
                    "production_activation_allowed": False,
                }
                manifest = SyntheticPatchDraftManifest(
                    sequence,
                    manifest_id,
                    receipt.receipt_id,
                    source_digest,
                    receipt.assessment_id,
                    receipt.packet_id,
                    receipt.operator_id,
                    receipt.decision,
                    draft_scopes,
                    target_path_digests,
                    REQUIRED_PATCH_DRAFT_CHECKS,
                    drafted_at,
                    previous,
                    canonical_digest(value),
                )
                self._manifests.append(manifest)
                self._by_receipt[receipt_id] = manifest
                created = True

        if before != ledger.evidence()["report_digest"]:
            with self._lock:
                if created and self._by_receipt.get(receipt_id) is manifest:
                    self._manifests.pop()
                    self._by_receipt.pop(receipt_id, None)
            raise GovernanceRejected("patch receipt changed during manifest drafting")
        return manifest

    def verify_manifest_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, manifest in enumerate(self._manifests, start=1):
                if (
                    manifest.sequence != sequence
                    or manifest.previous_digest != previous
                    or manifest.manifest_id
                    != _manifest_id(
                        manifest.source_receipt_id,
                        manifest.source_receipt_digest,
                        manifest.draft_scopes,
                        manifest.target_path_digests,
                    )
                    or manifest.manifest_digest
                    != canonical_digest(manifest.digest_value())
                    or manifest.state != PATCH_DRAFT_MANIFEST_STATE
                    or not manifest.eternian_review_required
                    or manifest.patch_content_present
                    or manifest.diff_content_present
                    or manifest.source_code_changed
                    or manifest.filesystem_written
                    or manifest.automatic_application_allowed
                    or manifest.safety_baseline_relaxation_allowed
                    or manifest.execution_allowed
                    or manifest.network_access_allowed
                    or manifest.money_movement_allowed
                    or manifest.production_activation_allowed
                    or not _valid_scopes(manifest.draft_scopes)
                    or manifest.required_checks != REQUIRED_PATCH_DRAFT_CHECKS
                ):
                    return False
                previous = manifest.manifest_digest
            return len(self._by_receipt) == len(self._manifests) and all(
                self._by_receipt.get(item.source_receipt_id) is item
                for item in self._manifests
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": "nurion.pg.synthetic-patch-draft-manifest-evidence.v1",
                "manifest_count": len(self._manifests),
                "manifest_digests": [item.manifest_digest for item in self._manifests],
                "manifest_chain_valid": self.verify_manifest_chain(),
                "maximum_state": PATCH_DRAFT_MANIFEST_STATE,
                "metadata_only": True,
                "eternian_review_required": True,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "application_method_present": False,
                "safety_baseline_relaxation_allowed": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
