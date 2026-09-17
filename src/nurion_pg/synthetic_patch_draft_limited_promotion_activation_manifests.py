"""Metadata-only activation preflight manifests for synthetic promotion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .patch_draft_limited_promotion_operator_reconfirmation_packets import (
    SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook,
)
from .patch_draft_limited_promotion_reconfirmation_intake import (
    SyntheticPatchDraftLimitedPromotionReconfirmationDecision,
)
from .patch_draft_limited_promotion_reconfirmation_receipt_ledger import (
    SyntheticPatchDraftLimitedPromotionReconfirmationReceiptLedger,
)
from .synthetic_patch_draft_limited_promotion_plans import (
    REQUIRED_ROLLBACK_TRIGGERS,
)


LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE = (
    "SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_MANIFEST_DRAFTED"
)
LIMITED_PROMOTION_ACTIVATION_SCOPE = "EXACT_SYNTHETIC_FIXTURE_COHORT_ONLY"
REQUIRED_ACTIVATION_PREFLIGHT_CHECKS = (
    "RECONFIRMATION_RECEIPT_INTACT",
    "RECONFIRMATION_PACKET_INTACT_AND_CURRENT",
    "SOURCE_SHADOW_AND_REVIEW_DIGESTS_BOUND",
    "EXACT_CANDIDATE_AND_COHORT_DIGESTS_ONLY",
    "EXACT_SAMPLE_SIZE_AND_OBSERVATION_WINDOW_ONLY",
    "EXACT_OBSERVATION_RESULTS_ONLY",
    "ROLLBACK_CHANNEL_REQUIRED",
    "ETERNIAN_FINAL_REVIEW_REQUIRED",
    "NO_ACTIVATION_OR_EXECUTION_METHOD",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _manifest_id(
    receipt_id: str,
    receipt_digest: str,
    packet_digest: str,
    plan_digest: str,
    shadow_assessment_digest: str,
) -> str:
    identity = canonical_digest(
        {
            "receipt_id": receipt_id,
            "receipt_digest": receipt_digest,
            "packet_digest": packet_digest,
            "plan_digest": plan_digest,
            "shadow_assessment_digest": shadow_assessment_digest,
            "scope": LIMITED_PROMOTION_ACTIVATION_SCOPE,
        }
    )
    return "synthetic:limited-promotion-activation-manifest:" + identity[:32]


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionActivationManifest:
    sequence: int
    manifest_id: str
    source_receipt_id: str
    source_receipt_digest: str
    source_assessment_id: str
    source_packet_id: str
    source_packet_digest: str
    shadow_id: str
    plan_id: str
    plan_digest: str
    source_plan_review_digest: str
    candidate_digest: str
    cohort_digest: str
    shadow_assessment_digest: str
    shadow_review_digest: str
    governance_digest: str
    synthetic_sample_size: int
    observation_window_seconds: int
    observation_result_digests: tuple[str, ...]
    activation_scope: str
    rollback_triggers: tuple[str, ...]
    required_checks: tuple[str, ...]
    drafted_at: datetime
    previous_digest: str
    manifest_digest: str
    state: str = LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE
    synthetic_only: bool = True
    eternian_final_review_required: bool = True
    validated_reconfirmation_receipt_only: bool = True
    actual_operator_reconfirmation_recorded: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    activation_allowed: bool = False
    rollback_execution_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    execution_allowed: bool = False
    network_access_allowed: bool = False
    money_movement_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        forbidden = (
            self.actual_operator_reconfirmation_recorded,
            self.candidate_content_present,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.activation_allowed,
            self.rollback_execution_allowed,
            self.safety_baseline_relaxation_allowed,
            self.execution_allowed,
            self.network_access_allowed,
            self.money_movement_allowed,
            self.production_activation_allowed,
        )
        if (
            self.sequence <= 0
            or self.manifest_id
            != _manifest_id(
                self.source_receipt_id,
                self.source_receipt_digest,
                self.source_packet_digest,
                self.plan_digest,
                self.shadow_assessment_digest,
            )
            or not self.source_receipt_id.startswith(
                "synthetic:patch-draft-limited-promotion-"
                "reconfirmation-receipt:"
            )
            or not self.source_assessment_id.startswith(
                "synthetic:patch-draft-limited-promotion-"
                "reconfirmation-assessment:"
            )
            or not self.source_packet_id.startswith(
                "synthetic:patch-draft-limited-promotion-reconfirmation:"
            )
            or not self.shadow_id.startswith(
                "synthetic:patch-draft-limited-promotion-shadow:"
            )
            or not self.plan_id.startswith(
                "synthetic:patch-draft-limited-promotion-plan:"
            )
            or not all(
                _valid_digest(value)
                for value in (
                    self.source_receipt_digest,
                    self.source_packet_digest,
                    self.plan_digest,
                    self.source_plan_review_digest,
                    self.candidate_digest,
                    self.cohort_digest,
                    self.shadow_assessment_digest,
                    self.shadow_review_digest,
                    self.governance_digest,
                    self.previous_digest,
                )
            )
            or self.candidate_digest == self.cohort_digest
            or self.synthetic_sample_size <= 0
            or self.observation_window_seconds <= 0
            or not self.observation_result_digests
            or not all(
                _valid_digest(value) for value in self.observation_result_digests
            )
            or self.activation_scope != LIMITED_PROMOTION_ACTIVATION_SCOPE
            or self.rollback_triggers != REQUIRED_ROLLBACK_TRIGGERS
            or self.required_checks != REQUIRED_ACTIVATION_PREFLIGHT_CHECKS
            or self.drafted_at.tzinfo is None
            or self.state != LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE
            or not self.synthetic_only
            or not self.eternian_final_review_required
            or not self.validated_reconfirmation_receipt_only
            or any(forbidden)
            or self.manifest_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid metadata-only synthetic activation manifest required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "manifest_id": self.manifest_id,
            "source_receipt_id": self.source_receipt_id,
            "source_receipt_digest": self.source_receipt_digest,
            "source_assessment_id": self.source_assessment_id,
            "source_packet_id": self.source_packet_id,
            "source_packet_digest": self.source_packet_digest,
            "shadow_id": self.shadow_id,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "source_plan_review_digest": self.source_plan_review_digest,
            "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest,
            "shadow_assessment_digest": self.shadow_assessment_digest,
            "shadow_review_digest": self.shadow_review_digest,
            "governance_digest": self.governance_digest,
            "synthetic_sample_size": self.synthetic_sample_size,
            "observation_window_seconds": self.observation_window_seconds,
            "observation_result_digests": list(
                self.observation_result_digests
            ),
            "activation_scope": LIMITED_PROMOTION_ACTIVATION_SCOPE,
            "rollback_triggers": list(self.rollback_triggers),
            "required_checks": list(self.required_checks),
            "drafted_at": self.drafted_at.isoformat(),
            "previous_digest": self.previous_digest,
            "state": LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE,
            "synthetic_only": True,
            "eternian_final_review_required": True,
            "validated_reconfirmation_receipt_only": True,
            "actual_operator_reconfirmation_recorded": False,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "activation_allowed": False,
            "rollback_execution_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "execution_allowed": False,
            "network_access_allowed": False,
            "money_movement_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionActivationManifestBook:
    """Drafts preflight metadata and exposes no activation method."""

    def __init__(self) -> None:
        self._manifests: list[
            SyntheticPatchDraftLimitedPromotionActivationManifest
        ] = []
        self._by_receipt: dict[
            str, SyntheticPatchDraftLimitedPromotionActivationManifest
        ] = {}
        self._lock = RLock()

    @property
    def manifests(
        self,
    ) -> tuple[SyntheticPatchDraftLimitedPromotionActivationManifest, ...]:
        with self._lock:
            return tuple(self._manifests)

    def draft_from_receipt(
        self,
        ledger: SyntheticPatchDraftLimitedPromotionReconfirmationReceiptLedger,
        receipt_id: str,
        packet_book: (
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook
        ),
        *,
        drafted_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionActivationManifest:
        if drafted_at.tzinfo is None:
            raise GovernanceRejected(
                "timezone-aware activation manifest time required"
            )
        if not isinstance(
            ledger,
            SyntheticPatchDraftLimitedPromotionReconfirmationReceiptLedger,
        ):
            raise GovernanceRejected("typed reconfirmation receipt ledger required")
        if not isinstance(
            packet_book,
            SyntheticPatchDraftLimitedPromotionOperatorReconfirmationPacketBook,
        ):
            raise GovernanceRejected("typed reconfirmation packet book required")
        if (
            not ledger.verify_metadata()
            or not ledger.verify_audit_chain()
            or not ledger.verify_record_bindings()
            or not packet_book.verify_packet_chain()
        ):
            raise GovernanceRejected("intact activation manifest sources required")
        ledger_before = ledger.evidence()["report_digest"]
        packet_before = packet_book.evidence()["report_digest"]
        receipt = ledger.get(receipt_id)
        if receipt.decision is not (
            SyntheticPatchDraftLimitedPromotionReconfirmationDecision
            .RECONFIRM_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION
        ):
            raise GovernanceRejected(
                "reconfirmation receipt does not permit manifest drafting"
            )
        if drafted_at < receipt.recorded_at:
            raise GovernanceRejected("activation manifest cannot predate receipt")
        packet = packet_book.current_packet(
            receipt.shadow_id, now=drafted_at
        )
        if (
            receipt.packet_id != packet.packet_id
            or receipt.packet_digest != packet.packet_digest
            or receipt.shadow_id != packet.shadow_id
        ):
            raise GovernanceRejected(
                "receipt is not bound to current reconfirmation packet"
            )
        source_digest = receipt.receipt_digest()

        with self._lock:
            if not self.verify_manifest_chain():
                raise GovernanceRejected(
                    "existing activation manifest chain is invalid"
                )
            existing = self._by_receipt.get(receipt_id)
            if existing is not None:
                if (
                    existing.source_receipt_digest != source_digest
                    or existing.source_packet_digest != packet.packet_digest
                    or existing.plan_digest != packet.plan_digest
                    or existing.shadow_assessment_digest
                    != packet.shadow_assessment_digest
                    or existing.shadow_review_digest
                    != packet.shadow_review_digest
                ):
                    raise GovernanceRejected(
                        "activation manifest idempotency mismatch"
                    )
                manifest = existing
                created = False
            else:
                sequence = len(self._manifests) + 1
                previous = (
                    self._manifests[-1].manifest_digest
                    if self._manifests
                    else "0" * 64
                )
                manifest_id = _manifest_id(
                    receipt.receipt_id,
                    source_digest,
                    packet.packet_digest,
                    packet.plan_digest,
                    packet.shadow_assessment_digest,
                )
                values = {
                    "sequence": sequence,
                    "manifest_id": manifest_id,
                    "source_receipt_id": receipt.receipt_id,
                    "source_receipt_digest": source_digest,
                    "source_assessment_id": receipt.assessment_id,
                    "source_packet_id": packet.packet_id,
                    "source_packet_digest": packet.packet_digest,
                    "shadow_id": packet.shadow_id,
                    "plan_id": packet.plan_id,
                    "plan_digest": packet.plan_digest,
                    "source_plan_review_digest": (
                        packet.source_plan_review_digest
                    ),
                    "candidate_digest": packet.candidate_digest,
                    "cohort_digest": packet.cohort_digest,
                    "shadow_assessment_digest": (
                        packet.shadow_assessment_digest
                    ),
                    "shadow_review_digest": packet.shadow_review_digest,
                    "governance_digest": packet.governance_digest,
                    "synthetic_sample_size": packet.synthetic_sample_size,
                    "observation_window_seconds": (
                        packet.observation_window_seconds
                    ),
                    "observation_result_digests": list(
                        packet.observation_result_digests
                    ),
                    "activation_scope": LIMITED_PROMOTION_ACTIVATION_SCOPE,
                    "rollback_triggers": list(REQUIRED_ROLLBACK_TRIGGERS),
                    "required_checks": list(
                        REQUIRED_ACTIVATION_PREFLIGHT_CHECKS
                    ),
                    "drafted_at": drafted_at.isoformat(),
                    "previous_digest": previous,
                    "state": LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE,
                    "synthetic_only": True,
                    "eternian_final_review_required": True,
                    "validated_reconfirmation_receipt_only": True,
                    "actual_operator_reconfirmation_recorded": False,
                    "candidate_content_present": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "activation_allowed": False,
                    "rollback_execution_allowed": False,
                    "safety_baseline_relaxation_allowed": False,
                    "execution_allowed": False,
                    "network_access_allowed": False,
                    "money_movement_allowed": False,
                    "production_activation_allowed": False,
                }
                manifest = (
                    SyntheticPatchDraftLimitedPromotionActivationManifest(
                        sequence,
                        manifest_id,
                        receipt.receipt_id,
                        source_digest,
                        receipt.assessment_id,
                        packet.packet_id,
                        packet.packet_digest,
                        packet.shadow_id,
                        packet.plan_id,
                        packet.plan_digest,
                        packet.source_plan_review_digest,
                        packet.candidate_digest,
                        packet.cohort_digest,
                        packet.shadow_assessment_digest,
                        packet.shadow_review_digest,
                        packet.governance_digest,
                        packet.synthetic_sample_size,
                        packet.observation_window_seconds,
                        packet.observation_result_digests,
                        LIMITED_PROMOTION_ACTIVATION_SCOPE,
                        REQUIRED_ROLLBACK_TRIGGERS,
                        REQUIRED_ACTIVATION_PREFLIGHT_CHECKS,
                        drafted_at,
                        previous,
                        canonical_digest(values),
                    )
                )
                self._manifests.append(manifest)
                self._by_receipt[receipt_id] = manifest
                created = True

        if (
            ledger_before != ledger.evidence()["report_digest"]
            or packet_before != packet_book.evidence()["report_digest"]
        ):
            with self._lock:
                if created and self._by_receipt.get(receipt_id) is manifest:
                    self._manifests.pop()
                    self._by_receipt.pop(receipt_id, None)
            raise GovernanceRejected(
                "activation manifest source changed during drafting"
            )
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
                        manifest.source_packet_digest,
                        manifest.plan_digest,
                        manifest.shadow_assessment_digest,
                    )
                    or manifest.manifest_digest
                    != canonical_digest(manifest.digest_value())
                    or manifest.state
                    != LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE
                    or manifest.activation_scope
                    != LIMITED_PROMOTION_ACTIVATION_SCOPE
                    or manifest.rollback_triggers != REQUIRED_ROLLBACK_TRIGGERS
                    or manifest.required_checks
                    != REQUIRED_ACTIVATION_PREFLIGHT_CHECKS
                    or not manifest.synthetic_only
                    or not manifest.eternian_final_review_required
                    or not manifest.validated_reconfirmation_receipt_only
                    or any(
                        (
                            manifest.actual_operator_reconfirmation_recorded,
                            manifest.candidate_content_present,
                            manifest.patch_content_present,
                            manifest.diff_content_present,
                            manifest.source_code_changed,
                            manifest.filesystem_written,
                            manifest.activation_allowed,
                            manifest.rollback_execution_allowed,
                            manifest.safety_baseline_relaxation_allowed,
                            manifest.execution_allowed,
                            manifest.network_access_allowed,
                            manifest.money_movement_allowed,
                            manifest.production_activation_allowed,
                        )
                    )
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
                "schema": (
                    "nurion.pg.synthetic-patch-draft-limited-promotion-"
                    "activation-manifest-evidence.v1"
                ),
                "manifest_count": len(self._manifests),
                "manifest_digests": [
                    item.manifest_digest for item in self._manifests
                ],
                "manifest_chain_valid": self.verify_manifest_chain(),
                "maximum_state": LIMITED_PROMOTION_ACTIVATION_MANIFEST_STATE,
                "activation_scope": LIMITED_PROMOTION_ACTIVATION_SCOPE,
                "synthetic_only": True,
                "eternian_final_review_required": True,
                "validated_reconfirmation_receipt_only": True,
                "actual_operator_reconfirmation_recorded": False,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_changed": False,
                "filesystem_written": False,
                "activation_method_present": False,
                "rollback_execution_method_present": False,
                "safety_baseline_relaxation_allowed": False,
                "execution_method_present": False,
                "network_access_method_present": False,
                "external_blocker_close_method_present": False,
                "automatic_merge_method_present": False,
                "automatic_deploy_method_present": False,
                "personal_data_used": False,
                "credentials_used": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
