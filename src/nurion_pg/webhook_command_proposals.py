"""Human-review-only command proposals derived from accepted synthetic webhooks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from .payment_lifecycle import PaymentEngine, PaymentIntent, PaymentState
from .webhook_intake import WebhookEventType


class ProposedPaymentCommand(StrEnum):
    AUTHORIZE = "AUTHORIZE"
    CAPTURE = "CAPTURE"
    CANCEL = "CANCEL"
    REFUND = "REFUND"


class ProposalDecision(StrEnum):
    PROPOSED_FOR_HUMAN_REVIEW = "PROPOSED_FOR_HUMAN_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


_COMMAND_BY_EVENT = {
    WebhookEventType.AUTHORIZATION_RESULT: ProposedPaymentCommand.AUTHORIZE,
    WebhookEventType.CAPTURE_RESULT: ProposedPaymentCommand.CAPTURE,
    WebhookEventType.CANCEL_RESULT: ProposedPaymentCommand.CANCEL,
    WebhookEventType.REFUND_RESULT: ProposedPaymentCommand.REFUND,
}


@dataclass(frozen=True)
class WebhookCommandProposal:
    proposal_id: str
    source_event_id: str
    source_envelope_digest: str
    source_acceptance_receipt_digest: str
    intent_id: str
    intent_snapshot_digest: str
    expected_version: int
    command: ProposedPaymentCommand
    amount_minor: int | None
    policy_digest: str
    created_at: datetime
    proposal_digest: str
    review_required: bool = True
    automatic_application_allowed: bool = False
    execution_allowed: bool = False
    operator_approval_recorded: bool = False

    def __post_init__(self) -> None:
        if (
            not self.proposal_id.startswith("synthetic:proposal:")
            or not self.source_event_id.startswith("synthetic:")
            or not self.intent_id.startswith("synthetic:")
            or not isinstance(self.expected_version, int)
            or isinstance(self.expected_version, bool)
            or self.expected_version <= 0
            or not isinstance(self.command, ProposedPaymentCommand)
            or self.created_at.tzinfo is None
            or not self.review_required
            or self.automatic_application_allowed
            or self.execution_allowed
            or self.operator_approval_recorded
        ):
            raise GovernanceRejected("non-executable synthetic command proposal required")
        for digest in (
            self.source_envelope_digest,
            self.source_acceptance_receipt_digest,
            self.intent_snapshot_digest,
            self.policy_digest,
            self.proposal_digest,
        ):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise GovernanceRejected("valid proposal evidence digests required")
        if self.command is ProposedPaymentCommand.REFUND and (
            not isinstance(self.amount_minor, int)
            or isinstance(self.amount_minor, bool)
            or self.amount_minor <= 0
        ):
            raise GovernanceRejected("positive refund proposal amount required")
        if self.command is not ProposedPaymentCommand.REFUND and self.amount_minor is not None:
            raise GovernanceRejected("amount is only retained for refund proposals")
        if self.proposal_digest != canonical_digest(self.digest_value()):
            raise GovernanceRejected("proposal digest mismatch")

    def digest_value(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "source_event_id": self.source_event_id,
            "source_envelope_digest": self.source_envelope_digest,
            "source_acceptance_receipt_digest": self.source_acceptance_receipt_digest,
            "intent_id": self.intent_id,
            "intent_snapshot_digest": self.intent_snapshot_digest,
            "expected_version": self.expected_version,
            "command": self.command.value,
            "amount_minor": self.amount_minor,
            "policy_digest": self.policy_digest,
            "created_at": self.created_at.isoformat(),
            "review_required": True,
            "automatic_application_allowed": False,
            "execution_allowed": False,
            "operator_approval_recorded": False,
        }


@dataclass(frozen=True)
class ProposalAssessment:
    sequence: int
    source_event_id: str
    source_envelope_digest: str
    source_acceptance_receipt_digest: str
    decision: ProposalDecision
    reason: str
    assessed_at: datetime
    proposal: WebhookCommandProposal | None
    previous_digest: str
    assessment_digest: str
    payment_state_changed: bool = False


class SyntheticWebhookProposalBook:
    """Append-only proposal assessments with no execution method."""

    def __init__(self, *, max_source_age_seconds: int = 600) -> None:
        if max_source_age_seconds <= 0:
            raise GovernanceRejected("positive proposal source age required")
        self._assessments: list[ProposalAssessment] = []
        self._by_source: dict[str, ProposalAssessment] = {}
        self._lock = RLock()
        self._max_source_age = timedelta(seconds=max_source_age_seconds)

    @property
    def assessments(self) -> tuple[ProposalAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def assess(
        self,
        inbox: SyntheticSQLiteWebhookInbox,
        payment_engine: PaymentEngine,
        event_id: str,
        *,
        now: datetime,
    ) -> ProposalAssessment:
        if now.tzinfo is None:
            raise GovernanceRejected("timezone-aware proposal time required")
        with self._lock:
            existing = self._by_source.get(event_id)
            if existing is not None:
                return existing
            accepted = inbox.accepted_event(event_id)
            envelope = accepted.envelope
            source_age = now - envelope.occurred_at
            if source_age > self._max_source_age or source_age < timedelta(0):
                return self._record(
                    envelope.event_id,
                    envelope.envelope_digest,
                    accepted.acceptance_receipt_digest,
                    ProposalDecision.HUMAN_REVIEW,
                    "stale_or_future_source_event",
                    now,
                    None,
                )
            try:
                intent = payment_engine.get(str(envelope.payload["intent_id"]))
            except GovernanceRejected:
                return self._record(
                    envelope.event_id,
                    envelope.envelope_digest,
                    accepted.acceptance_receipt_digest,
                    ProposalDecision.BLOCKED,
                    "unknown_synthetic_payment_intent",
                    now,
                    None,
                )

            if envelope.payload["outcome"] != "SUCCEEDED":
                return self._record(
                    envelope.event_id,
                    envelope.envelope_digest,
                    accepted.acceptance_receipt_digest,
                    ProposalDecision.HUMAN_REVIEW,
                    "reported_failure_has_no_automatic_state_mapping",
                    now,
                    None,
                )
            if envelope.payload["expected_version"] != intent.version:
                return self._record(
                    envelope.event_id,
                    envelope.envelope_digest,
                    accepted.acceptance_receipt_digest,
                    ProposalDecision.HUMAN_REVIEW,
                    "payment_intent_version_mismatch",
                    now,
                    None,
                )

            command = _COMMAND_BY_EVENT[envelope.event_type]
            reason = self._compatibility_reason(command, envelope.payload, intent)
            if reason is not None:
                return self._record(
                    envelope.event_id,
                    envelope.envelope_digest,
                    accepted.acceptance_receipt_digest,
                    ProposalDecision.HUMAN_REVIEW,
                    reason,
                    now,
                    None,
                )
            proposal = self._build_proposal(
                command,
                envelope.event_id,
                envelope.envelope_digest,
                accepted.acceptance_receipt_digest,
                intent,
                int(envelope.payload["amount_minor"])
                if command is ProposedPaymentCommand.REFUND
                else None,
                now,
            )
            return self._record(
                envelope.event_id,
                envelope.envelope_digest,
                accepted.acceptance_receipt_digest,
                ProposalDecision.PROPOSED_FOR_HUMAN_REVIEW,
                "synthetic_command_draft_only",
                now,
                proposal,
            )

    @staticmethod
    def _compatibility_reason(
        command: ProposedPaymentCommand,
        payload: object,
        intent: PaymentIntent,
    ) -> str | None:
        if not isinstance(payload, dict) and not hasattr(payload, "__getitem__"):
            return "invalid_payload_mapping"
        if command is ProposedPaymentCommand.AUTHORIZE:
            return None if intent.state is PaymentState.CREATED else "authorization_state_mismatch"
        if command is ProposedPaymentCommand.CAPTURE:
            if intent.state is not PaymentState.SYNTHETIC_AUTHORIZED:
                return "capture_state_mismatch"
            if payload["amount_minor"] != intent.amount_minor:
                return "full_capture_amount_mismatch"
            return None
        if command is ProposedPaymentCommand.CANCEL:
            return (
                None
                if intent.state in {PaymentState.CREATED, PaymentState.SYNTHETIC_AUTHORIZED}
                else "cancel_state_mismatch"
            )
        if intent.state not in {PaymentState.SYNTHETIC_CAPTURED, PaymentState.PARTIALLY_REFUNDED}:
            return "refund_state_mismatch"
        remaining = intent.captured_minor - intent.refunded_minor
        return None if 0 < payload["amount_minor"] <= remaining else "refund_amount_mismatch"

    @staticmethod
    def _intent_snapshot_digest(intent: PaymentIntent) -> str:
        return canonical_digest(
            {
                "intent_id": intent.intent_id,
                "state": intent.state.value,
                "version": intent.version,
                "amount_minor": intent.amount_minor,
                "currency": intent.currency,
                "captured_minor": intent.captured_minor,
                "refunded_minor": intent.refunded_minor,
                "policy_digest": intent.policy_digest,
                "synthetic_only": intent.synthetic_only,
                "external_execution_allowed": intent.external_execution_allowed,
            }
        )

    def _build_proposal(
        self,
        command: ProposedPaymentCommand,
        event_id: str,
        envelope_digest: str,
        receipt_digest: str,
        intent: PaymentIntent,
        amount_minor: int | None,
        now: datetime,
    ) -> WebhookCommandProposal:
        identity_digest = canonical_digest(
            {
                "source_event_id": event_id,
                "source_envelope_digest": envelope_digest,
                "source_acceptance_receipt_digest": receipt_digest,
                "intent_id": intent.intent_id,
                "expected_version": intent.version,
                "command": command.value,
                "amount_minor": amount_minor,
            }
        )
        proposal_id = f"synthetic:proposal:{identity_digest[:32]}"
        snapshot_digest = self._intent_snapshot_digest(intent)
        value = {
            "proposal_id": proposal_id,
            "source_event_id": event_id,
            "source_envelope_digest": envelope_digest,
            "source_acceptance_receipt_digest": receipt_digest,
            "intent_id": intent.intent_id,
            "intent_snapshot_digest": snapshot_digest,
            "expected_version": intent.version,
            "command": command.value,
            "amount_minor": amount_minor,
            "policy_digest": intent.policy_digest,
            "created_at": now.isoformat(),
            "review_required": True,
            "automatic_application_allowed": False,
            "execution_allowed": False,
            "operator_approval_recorded": False,
        }
        return WebhookCommandProposal(
            proposal_id,
            event_id,
            envelope_digest,
            receipt_digest,
            intent.intent_id,
            snapshot_digest,
            intent.version,
            command,
            amount_minor,
            intent.policy_digest,
            now,
            canonical_digest(value),
        )

    def _record(
        self,
        event_id: str,
        envelope_digest: str,
        receipt_digest: str,
        decision: ProposalDecision,
        reason: str,
        assessed_at: datetime,
        proposal: WebhookCommandProposal | None,
    ) -> ProposalAssessment:
        previous = self._assessments[-1].assessment_digest if self._assessments else "0" * 64
        sequence = len(self._assessments) + 1
        value = {
            "sequence": sequence,
            "source_event_id": event_id,
            "source_envelope_digest": envelope_digest,
            "source_acceptance_receipt_digest": receipt_digest,
            "decision": decision.value,
            "reason": reason,
            "assessed_at": assessed_at.isoformat(),
            "proposal_digest": proposal.proposal_digest if proposal is not None else None,
            "previous_digest": previous,
            "payment_state_changed": False,
        }
        assessment = ProposalAssessment(
            sequence,
            event_id,
            envelope_digest,
            receipt_digest,
            decision,
            reason,
            assessed_at,
            proposal,
            previous,
            canonical_digest(value),
        )
        self._assessments.append(assessment)
        self._by_source[event_id] = assessment
        return assessment

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, assessment in enumerate(self._assessments, start=1):
                expected = canonical_digest(
                    {
                        "sequence": sequence,
                        "source_event_id": assessment.source_event_id,
                        "source_envelope_digest": assessment.source_envelope_digest,
                        "source_acceptance_receipt_digest": assessment.source_acceptance_receipt_digest,
                        "decision": assessment.decision.value,
                        "reason": assessment.reason,
                        "assessed_at": assessment.assessed_at.isoformat(),
                        "proposal_digest": (
                            assessment.proposal.proposal_digest
                            if assessment.proposal is not None
                            else None
                        ),
                        "previous_digest": previous,
                        "payment_state_changed": False,
                    }
                )
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or assessment.assessment_digest != expected
                    or assessment.payment_state_changed
                ):
                    return False
                previous = assessment.assessment_digest
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {decision.value: 0 for decision in ProposalDecision}
            proposals: list[str] = []
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
                if assessment.proposal is not None:
                    proposals.append(assessment.proposal.proposal_digest)
            value = {
                "schema": "nurion.pg.synthetic-webhook-command-proposal-evidence.v1",
                "decision_counts": counts,
                "proposal_digests": proposals,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "synthetic_only": True,
                "review_required": True,
                "execution_method_present": False,
                "payment_state_automatically_changed": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
