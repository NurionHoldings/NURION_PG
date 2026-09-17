"""Non-executable implementation proposal drafts from synthetic decision receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .operator_decision_intake import SyntheticOperatorDecision
from .operator_decision_receipt_ledger import (
    SyntheticDecisionReceipt,
    SyntheticOperatorDecisionReceiptLedger,
)


IMPLEMENTATION_PROPOSAL_STATE = "SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFTED"
ALLOWED_DRAFT_SCOPES = (
    "SYNTHETIC_FIXTURE_PATCH_DRAFT_ONLY",
    "TEST_HARDENING_PATCH_DRAFT_ONLY",
    "POLICY_CLARIFICATION_PATCH_DRAFT_ONLY",
    "DOCUMENTATION_PATCH_DRAFT_ONLY",
)
REQUIRED_DRAFT_CHECKS = (
    "PRESERVE_FAIL_CLOSED_BASELINE",
    "REPRODUCE_SOURCE_SHA256_EVIDENCE",
    "RUN_SYNTHETIC_REGRESSION",
    "RUN_CONCURRENCY_AND_FAILURE_TESTS_WHEN_APPLICABLE",
    "ETERNIAN_REVIEW_REQUIRED_BEFORE_ANY_CHANGE",
    "OPERATOR_APPROVAL_REQUIRED_BEFORE_LIMITED_PROMOTION",
)


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _receipt_digest(receipt: SyntheticDecisionReceipt) -> str:
    return canonical_digest(
        {
            "receipt_id": receipt.receipt_id,
            "assessment_id": receipt.assessment_id,
            "assessment_digest": receipt.assessment_digest,
            "envelope_id": receipt.envelope_id,
            "envelope_digest": receipt.envelope_digest,
            "packet_id": receipt.packet_id,
            "packet_digest": receipt.packet_digest,
            "operator_id": receipt.operator_id,
            "decision": receipt.decision.value,
            "state": receipt.state,
            "recorded_at": receipt.recorded_at.isoformat(),
            "actual_operator_decision_recorded": False,
            "packet_state_changed": False,
            "code_change_allowed": False,
            "automatic_application_allowed": False,
            "execution_allowed": False,
        }
    )


@dataclass(frozen=True)
class SyntheticImplementationProposalDraft:
    sequence: int
    proposal_id: str
    source_receipt_id: str
    source_receipt_digest: str
    source_assessment_id: str
    source_packet_id: str
    operator_id: str
    decision: SyntheticOperatorDecision
    draft_scopes: tuple[str, ...]
    required_checks: tuple[str, ...]
    drafted_at: datetime
    previous_digest: str
    proposal_digest: str
    state: str = IMPLEMENTATION_PROPOSAL_STATE
    eternian_review_required: bool = True
    actual_operator_decision_recorded: bool = False
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    execution_allowed: bool = False
    money_movement_allowed: bool = False
    production_activation_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.sequence <= 0
            or not self.proposal_id.startswith(
                "synthetic:implementation-proposal-draft:"
            )
            or not self.source_receipt_id.startswith(
                "synthetic:operator-decision-receipt:"
            )
            or not _valid_digest(self.source_receipt_digest)
            or not self.source_assessment_id.startswith(
                "synthetic:operator-decision-assessment:"
            )
            or not self.source_packet_id.startswith(
                "synthetic:operator-decision-packet:"
            )
            or self.operator_id != "synthetic:operator:CHOI_IN_SEOK"
            or self.decision
            is not SyntheticOperatorDecision.AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT
            or not _valid_scopes(self.draft_scopes)
            or self.required_checks != REQUIRED_DRAFT_CHECKS
            or self.drafted_at.tzinfo is None
            or not _valid_digest(self.previous_digest)
            or self.state != IMPLEMENTATION_PROPOSAL_STATE
            or not self.eternian_review_required
            or self.actual_operator_decision_recorded
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.execution_allowed
            or self.money_movement_allowed
            or self.production_activation_allowed
            or self.proposal_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected(
                "valid non-executable synthetic implementation proposal required"
            )

    def digest_value(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "proposal_id": self.proposal_id,
            "source_receipt_id": self.source_receipt_id,
            "source_receipt_digest": self.source_receipt_digest,
            "source_assessment_id": self.source_assessment_id,
            "source_packet_id": self.source_packet_id,
            "operator_id": self.operator_id,
            "decision": self.decision.value,
            "draft_scopes": list(self.draft_scopes),
            "required_checks": list(self.required_checks),
            "drafted_at": self.drafted_at.isoformat(),
            "previous_digest": self.previous_digest,
            "state": IMPLEMENTATION_PROPOSAL_STATE,
            "eternian_review_required": True,
            "actual_operator_decision_recorded": False,
            "code_change_allowed": False,
            "automatic_application_allowed": False,
            "execution_allowed": False,
            "money_movement_allowed": False,
            "production_activation_allowed": False,
        }


def _valid_scopes(scopes: tuple[str, ...]) -> bool:
    if not scopes or len(set(scopes)) != len(scopes):
        return False
    expected_order = tuple(scope for scope in ALLOWED_DRAFT_SCOPES if scope in scopes)
    return scopes == expected_order


class SyntheticImplementationProposalBook:
    """Drafts review-only implementation skeletons and exposes no apply method."""

    def __init__(self) -> None:
        self._proposals: list[SyntheticImplementationProposalDraft] = []
        self._by_receipt: dict[str, SyntheticImplementationProposalDraft] = {}
        self._lock = RLock()

    @property
    def proposals(self) -> tuple[SyntheticImplementationProposalDraft, ...]:
        with self._lock:
            return tuple(self._proposals)

    def draft_from_receipt(
        self,
        ledger: SyntheticOperatorDecisionReceiptLedger,
        receipt_id: str,
        *,
        draft_scopes: tuple[str, ...],
        drafted_at: datetime,
    ) -> SyntheticImplementationProposalDraft:
        if drafted_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware implementation draft time required")
        if not isinstance(ledger, SyntheticOperatorDecisionReceiptLedger):
            raise GovernanceRejected("typed synthetic decision receipt ledger required")
        if not _valid_scopes(draft_scopes):
            raise GovernanceRejected("ordered allowlisted implementation draft scopes required")
        if (
            not ledger.verify_metadata()
            or not ledger.verify_audit_chain()
            or not ledger.verify_record_bindings()
        ):
            raise GovernanceRejected("intact synthetic decision receipt ledger required")
        before = ledger.evidence()["report_digest"]
        receipt = ledger.get(receipt_id)
        if (
            receipt.decision
            is not SyntheticOperatorDecision.AUTHORIZE_SYNTHETIC_IMPLEMENTATION_PROPOSAL_DRAFT
        ):
            raise GovernanceRejected("synthetic receipt does not authorize a draft")
        if drafted_at < receipt.recorded_at:
            raise GovernanceRejected("implementation draft cannot predate receipt")
        source_digest = _receipt_digest(receipt)

        with self._lock:
            existing = self._by_receipt.get(receipt_id)
            if existing is not None:
                if (
                    existing.draft_scopes != draft_scopes
                    or existing.source_receipt_digest != source_digest
                    or existing.source_assessment_id != receipt.assessment_id
                    or existing.source_packet_id != receipt.packet_id
                    or existing.operator_id != receipt.operator_id
                    or existing.decision is not receipt.decision
                ):
                    raise GovernanceRejected("implementation draft idempotency mismatch")
                if not self.verify_proposal_chain():
                    raise GovernanceRejected("existing implementation draft is invalid")
                proposal = existing
            else:
                sequence = len(self._proposals) + 1
                previous = (
                    self._proposals[-1].proposal_digest
                    if self._proposals
                    else "0" * 64
                )
                identity = canonical_digest(
                    {
                        "source_receipt_id": receipt.receipt_id,
                        "source_receipt_digest": source_digest,
                        "draft_scopes": list(draft_scopes),
                    }
                )
                proposal_id = (
                    "synthetic:implementation-proposal-draft:" + identity[:32]
                )
                value = {
                    "sequence": sequence,
                    "proposal_id": proposal_id,
                    "source_receipt_id": receipt.receipt_id,
                    "source_receipt_digest": source_digest,
                    "source_assessment_id": receipt.assessment_id,
                    "source_packet_id": receipt.packet_id,
                    "operator_id": receipt.operator_id,
                    "decision": receipt.decision.value,
                    "draft_scopes": list(draft_scopes),
                    "required_checks": list(REQUIRED_DRAFT_CHECKS),
                    "drafted_at": drafted_at.isoformat(),
                    "previous_digest": previous,
                    "state": IMPLEMENTATION_PROPOSAL_STATE,
                    "eternian_review_required": True,
                    "actual_operator_decision_recorded": False,
                    "code_change_allowed": False,
                    "automatic_application_allowed": False,
                    "execution_allowed": False,
                    "money_movement_allowed": False,
                    "production_activation_allowed": False,
                }
                proposal = SyntheticImplementationProposalDraft(
                    sequence,
                    proposal_id,
                    receipt.receipt_id,
                    source_digest,
                    receipt.assessment_id,
                    receipt.packet_id,
                    receipt.operator_id,
                    receipt.decision,
                    draft_scopes,
                    REQUIRED_DRAFT_CHECKS,
                    drafted_at,
                    previous,
                    canonical_digest(value),
                )
                self._proposals.append(proposal)
                self._by_receipt[receipt_id] = proposal

        after = ledger.evidence()["report_digest"]
        if before != after:
            with self._lock:
                if self._by_receipt.get(receipt_id) is proposal and proposal is not existing:
                    self._proposals.pop()
                    self._by_receipt.pop(receipt_id, None)
            raise GovernanceRejected("decision receipt changed during proposal drafting")
        return proposal

    def verify_proposal_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, proposal in enumerate(self._proposals, start=1):
                if (
                    proposal.sequence != sequence
                    or proposal.previous_digest != previous
                    or proposal.proposal_digest
                    != canonical_digest(proposal.digest_value())
                    or proposal.state != IMPLEMENTATION_PROPOSAL_STATE
                    or not proposal.eternian_review_required
                    or proposal.actual_operator_decision_recorded
                    or proposal.code_change_allowed
                    or proposal.automatic_application_allowed
                    or proposal.execution_allowed
                    or proposal.money_movement_allowed
                    or proposal.production_activation_allowed
                    or not _valid_scopes(proposal.draft_scopes)
                    or proposal.required_checks != REQUIRED_DRAFT_CHECKS
                ):
                    return False
                previous = proposal.proposal_digest
            return len(self._by_receipt) == len(self._proposals) and all(
                self._by_receipt.get(proposal.source_receipt_id) is proposal
                for proposal in self._proposals
            )

    def evidence(self) -> dict[str, object]:
        with self._lock:
            value = {
                "schema": "nurion.pg.synthetic-implementation-proposal-evidence.v1",
                "proposal_count": len(self._proposals),
                "proposal_digests": [
                    proposal.proposal_digest for proposal in self._proposals
                ],
                "proposal_chain_valid": self.verify_proposal_chain(),
                "maximum_state": IMPLEMENTATION_PROPOSAL_STATE,
                "eternian_review_required": True,
                "actual_operator_decision_recording_method_present": False,
                "code_change_method_present": False,
                "application_method_present": False,
                "execution_method_present": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
