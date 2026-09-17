"""Metadata-only drafts for synthetic limited-promotion activation dry-runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .synthetic_patch_draft_limited_promotion_activation_intake import (
    SyntheticPatchDraftLimitedPromotionActivationDecision,
)
from .synthetic_patch_draft_limited_promotion_activation_operator_packets import (
    SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
)
from .synthetic_patch_draft_limited_promotion_activation_receipt_ledger import (
    ACTIVATION_RECEIPT_STATE,
    SyntheticPatchDraftLimitedPromotionActivationReceiptLedger,
)


ACTIVATION_DRAFT_STATE = "SYNTHETIC_LIMITED_PROMOTION_ACTIVATION_DRAFTED"
ACTIVATION_DRAFT_SCOPE = "SYNTHETIC_FIXTURE_ACTIVATION_DRY_RUN_ONLY"
ACTIVATION_DRAFT_REQUIRED_CHECKS = (
    "VALIDATED_ACTIVATION_RECEIPT_ONLY",
    "CURRENT_OPERATOR_PACKET_REQUIRED",
    "EXACT_FINAL_REVIEWED_MANIFEST_ONLY",
    "EXACT_CANDIDATE_AND_COHORT_DIGESTS_ONLY",
    "EXACT_SAMPLE_SIZE_AND_OBSERVATION_WINDOW_ONLY",
    "EXACT_OBSERVATION_RESULTS_ONLY",
    "ROLLBACK_TRIGGERS_REMAIN_MANDATORY",
    "ETERNIAN_REVIEW_REQUIRED_BEFORE_DRY_RUN",
    "NO_CODE_PATCH_DIFF_OR_FILESYSTEM_CHANGE",
    "NO_ACTIVATION_OR_EXECUTION_METHOD",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _draft_id(
    receipt_id: str,
    receipt_digest: str,
    packet_digest: str,
    manifest_digest: str,
) -> str:
    identity = canonical_digest(
        {
            "receipt_id": receipt_id,
            "receipt_digest": receipt_digest,
            "packet_digest": packet_digest,
            "manifest_digest": manifest_digest,
            "scope": ACTIVATION_DRAFT_SCOPE,
        }
    )
    return "synthetic:limited-promotion-activation-draft:" + identity[:32]


@dataclass(frozen=True)
class SyntheticPatchDraftLimitedPromotionActivationDraft:
    sequence: int
    draft_id: str
    source_receipt_id: str
    source_receipt_digest: str
    source_assessment_id: str
    source_assessment_digest: str
    source_packet_id: str
    source_packet_digest: str
    manifest_id: str
    manifest_digest: str
    final_review_digest: str
    candidate_digest: str
    cohort_digest: str
    synthetic_sample_size: int
    observation_window_seconds: int
    observation_result_digests: tuple[str, ...]
    rollback_triggers: tuple[str, ...]
    activation_scope: str
    required_checks: tuple[str, ...]
    drafted_at: datetime
    previous_digest: str
    draft_digest: str
    state: str = ACTIVATION_DRAFT_STATE
    synthetic_only: bool = True
    eternian_review_required: bool = True
    actual_operator_decision_recorded: bool = False
    activation_recorded: bool = False
    candidate_content_present: bool = False
    patch_content_present: bool = False
    diff_content_present: bool = False
    source_code_changed: bool = False
    filesystem_written: bool = False
    activation_allowed: bool = False
    rollback_execution_allowed: bool = False
    execution_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        forbidden = (
            self.actual_operator_decision_recorded,
            self.activation_recorded,
            self.candidate_content_present,
            self.patch_content_present,
            self.diff_content_present,
            self.source_code_changed,
            self.filesystem_written,
            self.activation_allowed,
            self.rollback_execution_allowed,
            self.execution_allowed,
            self.production_activation_allowed,
        )
        if (
            self.sequence <= 0
            or self.draft_id
            != _draft_id(
                self.source_receipt_id,
                self.source_receipt_digest,
                self.source_packet_digest,
                self.manifest_digest,
            )
            or not self.source_receipt_id.startswith(
                "synthetic:limited-promotion-activation-receipt:"
            )
            or not self.source_assessment_id.startswith(
                "synthetic:limited-promotion-activation-intent-assessment:"
            )
            or not self.source_packet_id.startswith(
                "synthetic:limited-promotion-activation-operator-packet:"
            )
            or not self.manifest_id.startswith(
                "synthetic:limited-promotion-activation-manifest:"
            )
            or not all(
                _valid_digest(value)
                for value in (
                    self.source_receipt_digest,
                    self.source_assessment_digest,
                    self.source_packet_digest,
                    self.manifest_digest,
                    self.final_review_digest,
                    self.candidate_digest,
                    self.cohort_digest,
                    self.previous_digest,
                )
            )
            or self.synthetic_sample_size <= 0
            or self.observation_window_seconds <= 0
            or not self.observation_result_digests
            or not all(
                _valid_digest(value) for value in self.observation_result_digests
            )
            or not self.rollback_triggers
            or self.activation_scope != ACTIVATION_DRAFT_SCOPE
            or self.required_checks != ACTIVATION_DRAFT_REQUIRED_CHECKS
            or self.drafted_at.tzinfo is None
            or self.state != ACTIVATION_DRAFT_STATE
            or not self.synthetic_only
            or not self.eternian_review_required
            or any(forbidden)
            or self.draft_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid metadata-only activation draft required")

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "draft_id": self.draft_id,
            "source_receipt_id": self.source_receipt_id,
            "source_receipt_digest": self.source_receipt_digest,
            "source_assessment_id": self.source_assessment_id,
            "source_assessment_digest": self.source_assessment_digest,
            "source_packet_id": self.source_packet_id,
            "source_packet_digest": self.source_packet_digest,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "final_review_digest": self.final_review_digest,
            "candidate_digest": self.candidate_digest,
            "cohort_digest": self.cohort_digest,
            "synthetic_sample_size": self.synthetic_sample_size,
            "observation_window_seconds": self.observation_window_seconds,
            "observation_result_digests": list(self.observation_result_digests),
            "rollback_triggers": list(self.rollback_triggers),
            "activation_scope": self.activation_scope,
            "required_checks": list(self.required_checks),
            "drafted_at": self.drafted_at.isoformat(),
            "previous_digest": self.previous_digest,
            "state": self.state,
            "synthetic_only": True,
            "eternian_review_required": True,
            "actual_operator_decision_recorded": False,
            "activation_recorded": False,
            "candidate_content_present": False,
            "patch_content_present": False,
            "diff_content_present": False,
            "source_code_changed": False,
            "filesystem_written": False,
            "activation_allowed": False,
            "rollback_execution_allowed": False,
            "execution_allowed": False,
            "production_activation_allowed": False,
        }


class SyntheticPatchDraftLimitedPromotionActivationDraftBook:
    """Drafts bounded dry-run metadata and exposes no activation method."""

    def __init__(self) -> None:
        self._drafts: list[SyntheticPatchDraftLimitedPromotionActivationDraft] = []
        self._by_receipt: dict[
            str, SyntheticPatchDraftLimitedPromotionActivationDraft
        ] = {}
        self._lock = RLock()

    @property
    def drafts(self) -> tuple[SyntheticPatchDraftLimitedPromotionActivationDraft, ...]:
        with self._lock:
            return tuple(self._drafts)

    def draft_from_receipt(
        self,
        ledger: SyntheticPatchDraftLimitedPromotionActivationReceiptLedger,
        receipt_id: str,
        packet_book: SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
        *,
        drafted_at: datetime,
    ) -> SyntheticPatchDraftLimitedPromotionActivationDraft:
        if drafted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware activation draft time required")
        if not isinstance(
            ledger,
            SyntheticPatchDraftLimitedPromotionActivationReceiptLedger,
        ):
            raise GovernanceRejected("typed activation receipt ledger required")
        if not isinstance(
            packet_book,
            SyntheticPatchDraftLimitedPromotionActivationOperatorPacketBook,
        ):
            raise GovernanceRejected("typed activation packet book required")
        if (
            not ledger.verify_metadata()
            or not ledger.verify_audit_chain()
            or not ledger.verify_record_bindings()
            or not packet_book.verify_packet_chain()
        ):
            raise GovernanceRejected("intact activation draft sources required")
        ledger_before = ledger.evidence()["report_digest"]
        packet_before = packet_book.evidence()["report_digest"]
        receipt = ledger.get(receipt_id)
        if (
            receipt.state != ACTIVATION_RECEIPT_STATE
            or receipt.decision is not (
                SyntheticPatchDraftLimitedPromotionActivationDecision
                .AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION
            )
        ):
            raise GovernanceRejected(
                "activation receipt does not permit draft preparation"
            )
        if drafted_at < receipt.recorded_at:
            raise GovernanceRejected("activation draft cannot predate receipt")
        packet = packet_book.current_packet(
            receipt.manifest_id,
            now=drafted_at,
        )
        if (
            receipt.packet_id != packet.packet_id
            or receipt.packet_digest != packet.packet_digest
            or receipt.manifest_id != packet.manifest_id
        ):
            raise GovernanceRejected("receipt is not bound to current packet")
        receipt_digest = receipt.receipt_digest()

        with self._lock:
            if not self.verify_draft_chain():
                raise GovernanceRejected("existing activation draft chain is invalid")
            created = False
            existing = self._by_receipt.get(receipt_id)
            if existing is not None:
                if (
                    existing.source_receipt_digest != receipt_digest
                    or existing.source_packet_digest != packet.packet_digest
                    or existing.manifest_digest != packet.manifest_digest
                ):
                    raise GovernanceRejected("activation draft source collision")
                draft = existing
            else:
                sequence = len(self._drafts) + 1
                previous = self._drafts[-1].draft_digest if self._drafts else "0" * 64
                draft_id = _draft_id(
                    receipt.receipt_id,
                    receipt_digest,
                    packet.packet_digest,
                    packet.manifest_digest,
                )
                values = {
                    "sequence": sequence,
                    "draft_id": draft_id,
                    "source_receipt_id": receipt.receipt_id,
                    "source_receipt_digest": receipt_digest,
                    "source_assessment_id": receipt.assessment_id,
                    "source_assessment_digest": receipt.assessment_digest,
                    "source_packet_id": packet.packet_id,
                    "source_packet_digest": packet.packet_digest,
                    "manifest_id": packet.manifest_id,
                    "manifest_digest": packet.manifest_digest,
                    "final_review_digest": packet.final_review_digest,
                    "candidate_digest": packet.candidate_digest,
                    "cohort_digest": packet.cohort_digest,
                    "synthetic_sample_size": packet.synthetic_sample_size,
                    "observation_window_seconds": packet.observation_window_seconds,
                    "observation_result_digests": list(
                        packet.observation_result_digests
                    ),
                    "rollback_triggers": list(packet.rollback_triggers),
                    "activation_scope": ACTIVATION_DRAFT_SCOPE,
                    "required_checks": list(ACTIVATION_DRAFT_REQUIRED_CHECKS),
                    "drafted_at": drafted_at.isoformat(),
                    "previous_digest": previous,
                    "state": ACTIVATION_DRAFT_STATE,
                    "synthetic_only": True,
                    "eternian_review_required": True,
                    "actual_operator_decision_recorded": False,
                    "activation_recorded": False,
                    "candidate_content_present": False,
                    "patch_content_present": False,
                    "diff_content_present": False,
                    "source_code_changed": False,
                    "filesystem_written": False,
                    "activation_allowed": False,
                    "rollback_execution_allowed": False,
                    "execution_allowed": False,
                    "production_activation_allowed": False,
                }
                draft = SyntheticPatchDraftLimitedPromotionActivationDraft(
                    sequence,
                    draft_id,
                    receipt.receipt_id,
                    receipt_digest,
                    receipt.assessment_id,
                    receipt.assessment_digest,
                    packet.packet_id,
                    packet.packet_digest,
                    packet.manifest_id,
                    packet.manifest_digest,
                    packet.final_review_digest,
                    packet.candidate_digest,
                    packet.cohort_digest,
                    packet.synthetic_sample_size,
                    packet.observation_window_seconds,
                    packet.observation_result_digests,
                    packet.rollback_triggers,
                    ACTIVATION_DRAFT_SCOPE,
                    ACTIVATION_DRAFT_REQUIRED_CHECKS,
                    drafted_at,
                    previous,
                    canonical_digest(values),
                )
                self._drafts.append(draft)
                self._by_receipt[receipt_id] = draft
                created = True
            if (
                ledger_before != ledger.evidence()["report_digest"]
                or packet_before != packet_book.evidence()["report_digest"]
            ):
                if created:
                    self._drafts.pop()
                    self._by_receipt.pop(receipt_id, None)
                raise GovernanceRejected("activation draft source changed")
        return draft

    def verify_draft_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, draft in enumerate(self._drafts, start=1):
                if (
                    draft.sequence != sequence
                    or draft.previous_digest != previous
                    or draft.draft_id
                    != _draft_id(
                        draft.source_receipt_id,
                        draft.source_receipt_digest,
                        draft.source_packet_digest,
                        draft.manifest_digest,
                    )
                    or draft.draft_digest != canonical_digest(draft.digest_value())
                    or draft.state != ACTIVATION_DRAFT_STATE
                    or draft.activation_scope != ACTIVATION_DRAFT_SCOPE
                    or draft.required_checks != ACTIVATION_DRAFT_REQUIRED_CHECKS
                    or any(
                        (
                            draft.actual_operator_decision_recorded,
                            draft.activation_recorded,
                            draft.candidate_content_present,
                            draft.patch_content_present,
                            draft.diff_content_present,
                            draft.source_code_changed,
                            draft.filesystem_written,
                            draft.activation_allowed,
                            draft.rollback_execution_allowed,
                            draft.execution_allowed,
                            draft.production_activation_allowed,
                        )
                    )
                ):
                    return False
                previous = draft.draft_digest
            return len(self._drafts) == len(self._by_receipt) and all(
                self._by_receipt.get(item.source_receipt_id) is item
                for item in self._drafts
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": (
                    "nurion.pg.synthetic-limited-promotion-activation-"
                    "draft-evidence.v1"
                ),
                "mode": "UNREGISTERED_SYNTHETIC_ONLY",
                "draft_count": len(self._drafts),
                "draft_digests": [item.draft_digest for item in self._drafts],
                "draft_chain_valid": self.verify_draft_chain(),
                "maximum_state": ACTIVATION_DRAFT_STATE,
                "activation_scope": ACTIVATION_DRAFT_SCOPE,
                "eternian_review_required": True,
                "actual_operator_decision_recorded": False,
                "activation_recording_method_present": False,
                "candidate_content_present": False,
                "patch_content_present": False,
                "diff_content_present": False,
                "source_code_change_method_present": False,
                "filesystem_write_method_present": False,
                "activation_method_present": False,
                "rollback_execution_method_present": False,
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
