"""Read-only reconciliation across synthetic NURION PG components.

The monitor creates findings for Eternian review.  It has no repair, approval,
payment, network, or production activation capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from .arkaon.governance import GovernanceRejected, canonical_digest
from .durable_webhook_inbox import SyntheticSQLiteWebhookInbox
from .payment_lifecycle import PaymentEngine, PaymentEventType
from .proposal_review_docket import SyntheticProposalReviewDocket
from .webhook_command_proposals import (
    ProposalDecision,
    SyntheticWebhookProposalBook,
)
from .webhook_intake import WebhookDecision


class ReconciliationSeverity(StrEnum):
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ReconciliationFinding:
    code: str
    severity: ReconciliationSeverity
    subject_id: str
    detail: str
    suggested_action: str
    automatic_repair_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.code
            or not self.subject_id.startswith("synthetic:")
            or not self.detail
            or not self.suggested_action
            or self.automatic_repair_allowed
        ):
            raise GovernanceRejected("complete non-repairing reconciliation finding required")

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "subject_id": self.subject_id,
            "detail": self.detail,
            "suggested_action": self.suggested_action,
            "automatic_repair_allowed": False,
        }


class SyntheticReconciliationMonitor:
    """Inspects synthetic evidence and emits immutable review proposals only."""

    def inspect(
        self,
        payment_engine: PaymentEngine,
        inbox: SyntheticSQLiteWebhookInbox,
        proposal_book: SyntheticWebhookProposalBook,
        docket: SyntheticProposalReviewDocket,
        *,
        observed_at: datetime,
    ) -> dict[str, object]:
        if observed_at.tzinfo is None:
            raise GovernanceRejected("timezone-aware reconciliation time required")

        before, snapshots = self._snapshots(payment_engine, inbox, proposal_book, docket)
        findings: list[ReconciliationFinding] = []
        self._check_integrity(snapshots, findings)
        self._check_payment_ledger(snapshots["payment"], findings)
        self._check_pipeline(snapshots, findings)
        after, _ = self._snapshots(payment_engine, inbox, proposal_book, docket)
        if before != after:
            self._add(
                findings,
                "COMPONENT_CHANGED_DURING_INSPECTION",
                ReconciliationSeverity.BLOCKED,
                "synthetic:reconciliation:components",
                "one or more component snapshots changed during read-only inspection",
                "Eternian must repeat inspection on a stable synthetic candidate",
            )

        findings.sort(key=lambda item: (item.severity.value, item.code, item.subject_id))
        counts = {severity.value: 0 for severity in ReconciliationSeverity}
        for finding in findings:
            counts[finding.severity.value] += 1
        status = (
            "BLOCKED"
            if counts[ReconciliationSeverity.BLOCKED.value]
            else "HUMAN_REVIEW"
            if counts[ReconciliationSeverity.WARNING.value]
            else "PASS"
        )
        value: dict[str, object] = {
            "schema": "nurion.pg.synthetic-reconciliation-report.v1",
            "observed_at": observed_at.isoformat(),
            "status": status,
            "component_snapshot_digests": before,
            "findings": [finding.as_dict() for finding in findings],
            "finding_counts": counts,
            "read_only_verified": before == after,
            "synthetic_only": True,
            "automatic_repair_allowed": False,
            "operator_decision_recorded": False,
            "payment_state_changed": False,
            "money_movement_executed": False,
            "production_activation_allowed": False,
        }
        return {**value, "report_digest": canonical_digest(value)}

    @staticmethod
    def _proposal_snapshot(book: SyntheticWebhookProposalBook) -> dict[str, object]:
        assessments = []
        proposal_bindings_valid = True
        for assessment in book.assessments:
            proposal = assessment.proposal
            proposal_valid = proposal is None or (
                proposal.proposal_digest == canonical_digest(proposal.digest_value())
                and proposal.source_event_id == assessment.source_event_id
                and proposal.source_envelope_digest == assessment.source_envelope_digest
                and proposal.source_acceptance_receipt_digest
                == assessment.source_acceptance_receipt_digest
                and proposal.review_required
                and not proposal.automatic_application_allowed
                and not proposal.execution_allowed
                and not proposal.operator_approval_recorded
            )
            proposal_bindings_valid = proposal_bindings_valid and proposal_valid
            assessments.append(
                {
                    "source_event_id": assessment.source_event_id,
                    "source_envelope_digest": assessment.source_envelope_digest,
                    "source_acceptance_receipt_digest": assessment.source_acceptance_receipt_digest,
                    "decision": assessment.decision.value,
                    "assessment_digest": assessment.assessment_digest,
                    "proposal_id": proposal.proposal_id if proposal is not None else None,
                    "proposal_digest": proposal.proposal_digest if proposal is not None else None,
                    "intent_id": proposal.intent_id if proposal is not None else None,
                    "payment_state_changed": assessment.payment_state_changed,
                }
            )
        value = {
            "schema": "nurion.pg.synthetic-proposal-reconciliation-snapshot.v1",
            "assessments": assessments,
            "assessment_chain_valid": book.verify_assessment_chain(),
            "proposal_bindings_valid": proposal_bindings_valid,
            "synthetic_only": True,
            "read_only": True,
        }
        return {**value, "snapshot_digest": canonical_digest(value)}

    @classmethod
    def _snapshots(
        cls,
        payment_engine: PaymentEngine,
        inbox: SyntheticSQLiteWebhookInbox,
        proposal_book: SyntheticWebhookProposalBook,
        docket: SyntheticProposalReviewDocket,
    ) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
        snapshots = {
            "payment": payment_engine.reconciliation_snapshot(),
            "inbox": inbox.reconciliation_snapshot(),
            "proposals": cls._proposal_snapshot(proposal_book),
            "docket": docket.reconciliation_snapshot(),
        }
        digests = {
            name: str(snapshot["snapshot_digest"])
            for name, snapshot in snapshots.items()
        }
        return digests, snapshots

    @classmethod
    def _check_integrity(
        cls,
        snapshots: dict[str, dict[str, object]],
        findings: list[ReconciliationFinding],
    ) -> None:
        checks = (
            ("payment", "event_chains_valid", "PAYMENT_EVENT_CHAIN_INVALID"),
            ("inbox", "receipt_chain_valid", "INBOX_RECEIPT_CHAIN_INVALID"),
            ("inbox", "accepted_bindings_valid", "INBOX_ACCEPTED_BINDING_INVALID"),
            ("proposals", "assessment_chain_valid", "PROPOSAL_ASSESSMENT_CHAIN_INVALID"),
            ("proposals", "proposal_bindings_valid", "PROPOSAL_BINDING_INVALID"),
            ("docket", "audit_chain_valid", "DOCKET_AUDIT_CHAIN_INVALID"),
            ("docket", "record_bindings_valid", "DOCKET_RECORD_BINDING_INVALID"),
        )
        for component, field, code in checks:
            if snapshots[component][field] is not True:
                cls._add(
                    findings,
                    code,
                    ReconciliationSeverity.BLOCKED,
                    f"synthetic:reconciliation:{component}",
                    f"{component} integrity check {field} failed",
                    "Eternian must quarantine the candidate and inspect its evidence chain",
                )

    @classmethod
    def _check_payment_ledger(
        cls,
        snapshot: dict[str, object],
        findings: list[ReconciliationFinding],
    ) -> None:
        intents = {str(item["intent_id"]): item for item in snapshot["intents"]}  # type: ignore[index]
        events_by_intent: dict[str, list[dict[str, Any]]] = {key: [] for key in intents}
        for event in snapshot["events"]:  # type: ignore[union-attr]
            events_by_intent.setdefault(str(event["intent_id"]), []).append(event)

        for intent_id in sorted(set(events_by_intent) - set(intents)):
            cls._add(
                findings,
                "PAYMENT_EVENT_WITHOUT_INTENT",
                ReconciliationSeverity.BLOCKED,
                intent_id,
                "payment event stream has no matching Payment Intent",
                "Eternian must quarantine the orphan event stream and inspect its provenance",
            )

        expected_journals: dict[str, dict[str, object]] = {}
        for intent_id, intent in intents.items():
            events = events_by_intent.get(intent_id, [])
            created = [
                event
                for event in events
                if event["event_type"] == PaymentEventType.CREATED.value
            ]
            captured = sum(
                int(event["amount_minor"])
                for event in events
                if event["event_type"] == PaymentEventType.CAPTURED.value
            )
            refunded = sum(
                int(event["amount_minor"])
                for event in events
                if event["event_type"] == PaymentEventType.REFUNDED.value
            )
            final = events[-1] if events else None
            if (
                final is None
                or final["version"] != intent["version"]
                or final["resulting_state"] != intent["state"]
                or captured != intent["captured_minor"]
                or refunded != intent["refunded_minor"]
                or len(created) != 1
                or created[0]["amount_minor"] != intent["amount_minor"]
                or intent["synthetic_only"] is not True
                or intent["external_execution_allowed"] is not False
            ):
                cls._add(
                    findings,
                    "PAYMENT_INTENT_EVENT_MISMATCH",
                    ReconciliationSeverity.BLOCKED,
                    intent_id,
                    "Payment Intent totals or final state do not match its event stream",
                    "Eternian must inspect the intent and event evidence without changing either record",
                )

            running_refund = 0
            for event in events:
                event_type = event["event_type"]
                if event_type == PaymentEventType.CAPTURED.value:
                    journal_id = f"synthetic:journal:capture:{intent_id}"
                    expected_journals[journal_id] = cls._expected_capture(intent, event)
                elif event_type == PaymentEventType.REFUNDED.value:
                    running_refund += int(event["amount_minor"])
                    journal_id = f"synthetic:journal:refund:{intent_id}:{running_refund}"
                    expected_journals[journal_id] = cls._expected_refund(intent, event)

        journal_rows = snapshot["journals"]  # type: ignore[assignment]
        actual_journals = {
            str(journal["journal_id"]): journal
            for journal in journal_rows  # type: ignore[union-attr]
        }
        all_ids = sorted(set(expected_journals) | set(actual_journals))
        for journal_id in all_ids:
            expected = expected_journals.get(journal_id)
            actual = actual_journals.get(journal_id)
            if expected is None or actual is None or not cls._journal_matches(actual, expected):
                cls._add(
                    findings,
                    "PAYMENT_LEDGER_JOURNAL_MISMATCH",
                    ReconciliationSeverity.BLOCKED,
                    journal_id,
                    "lifecycle event and balanced-ledger journal do not have an exact binding",
                    "Eternian must quarantine the candidate and compare lifecycle and ledger evidence",
                )
        if len(actual_journals) != len(journal_rows):  # type: ignore[arg-type]
            cls._add(
                findings,
                "PAYMENT_LEDGER_DUPLICATE_JOURNAL_ID",
                ReconciliationSeverity.BLOCKED,
                "synthetic:reconciliation:ledger",
                "ledger contains duplicate journal identities",
                "Eternian must quarantine the ledger candidate and inspect journal provenance",
            )

    @staticmethod
    def _expected_capture(intent: dict[str, Any], event: dict[str, Any]) -> dict[str, object]:
        amount = int(event["amount_minor"])
        return {
            "evidence_digest": intent["policy_digest"],
            "entries": [
                {
                    "account_ref": "synthetic:provider-clearing-receivable",
                    "side": "DEBIT",
                    "amount_minor": amount,
                    "currency": intent["currency"],
                },
                {
                    "account_ref": f"synthetic:merchant-payable:{intent['merchant_ref']}",
                    "side": "CREDIT",
                    "amount_minor": amount,
                    "currency": intent["currency"],
                },
            ],
        }

    @staticmethod
    def _expected_refund(intent: dict[str, Any], event: dict[str, Any]) -> dict[str, object]:
        amount = int(event["amount_minor"])
        return {
            "evidence_digest": intent["policy_digest"],
            "entries": [
                {
                    "account_ref": f"synthetic:merchant-payable:{intent['merchant_ref']}",
                    "side": "DEBIT",
                    "amount_minor": amount,
                    "currency": intent["currency"],
                },
                {
                    "account_ref": "synthetic:provider-clearing-refund",
                    "side": "CREDIT",
                    "amount_minor": amount,
                    "currency": intent["currency"],
                },
            ],
        }

    @staticmethod
    def _journal_matches(actual: dict[str, Any], expected: dict[str, object]) -> bool:
        return (
            actual["evidence_digest"] == expected["evidence_digest"]
            and actual["entries"] == expected["entries"]
            and actual["synthetic_only"] is True
            and actual["execution_allowed"] is False
        )

    @classmethod
    def _check_pipeline(
        cls,
        snapshots: dict[str, dict[str, object]],
        findings: list[ReconciliationFinding],
    ) -> None:
        accepted = {
            str(event["event_id"]): event
            for event in snapshots["inbox"]["events"]  # type: ignore[index]
            if event["decision"] == WebhookDecision.ACCEPTED.value
        }
        assessments = {
            str(item["source_event_id"]): item
            for item in snapshots["proposals"]["assessments"]  # type: ignore[index]
        }
        docket_records = {
            str(record["proposal_id"]): record
            for record in snapshots["docket"]["records"]  # type: ignore[index]
        }

        for event_id, event in accepted.items():
            assessment = assessments.get(event_id)
            if assessment is None:
                cls._add(
                    findings,
                    "ACCEPTED_EVENT_UNASSESSED",
                    ReconciliationSeverity.WARNING,
                    event_id,
                    "accepted synthetic webhook has no ARKAON proposal assessment",
                    "Eternian should request a synthetic assessment before any further review",
                )
                continue
            if (
                assessment["source_envelope_digest"] != event["envelope_digest"]
                or assessment["source_acceptance_receipt_digest"]
                != event["acceptance_receipt_digest"]
            ):
                cls._add(
                    findings,
                    "ASSESSMENT_SOURCE_BINDING_MISMATCH",
                    ReconciliationSeverity.BLOCKED,
                    event_id,
                    "proposal assessment is not bound to the accepted envelope and receipt",
                    "Eternian must quarantine the assessment and inspect source evidence",
                )

        for event_id, assessment in assessments.items():
            if event_id not in accepted:
                cls._add(
                    findings,
                    "ASSESSMENT_SOURCE_NOT_ACCEPTED",
                    ReconciliationSeverity.BLOCKED,
                    event_id,
                    "proposal assessment source is absent or is not currently accepted",
                    "Eternian must quarantine the assessment and verify inbox history",
                )
            proposal_id = assessment["proposal_id"]
            if assessment["decision"] == ProposalDecision.PROPOSED_FOR_HUMAN_REVIEW.value:
                if proposal_id is None or proposal_id not in docket_records:
                    cls._add(
                        findings,
                        "PROPOSAL_MISSING_DOCKET",
                        ReconciliationSeverity.WARNING,
                        event_id,
                        "reviewable ARKAON proposal has no durable Eternian docket record",
                        "Eternian should submit the proposal to the synthetic review docket",
                    )

        proposals_by_id = {
            str(item["proposal_id"]): item
            for item in assessments.values()
            if item["proposal_id"] is not None
        }
        for proposal_id, record in docket_records.items():
            assessment = proposals_by_id.get(proposal_id)
            if assessment is None:
                cls._add(
                    findings,
                    "DOCKET_WITHOUT_PROPOSAL",
                    ReconciliationSeverity.BLOCKED,
                    proposal_id,
                    "docket record has no matching proposal assessment",
                    "Eternian must quarantine the docket record and inspect its source chain",
                )
                continue
            if (
                record["source_event_id"] != assessment["source_event_id"]
                or record["proposal_digest"] != assessment["proposal_digest"]
                or record["source_assessment_digest"] != assessment["assessment_digest"]
            ):
                cls._add(
                    findings,
                    "DOCKET_BINDING_MISMATCH",
                    ReconciliationSeverity.BLOCKED,
                    proposal_id,
                    "docket identity or evidence digest does not match its proposal assessment",
                    "Eternian must quarantine the docket record and compare all source digests",
                )

    @staticmethod
    def _add(
        findings: list[ReconciliationFinding],
        code: str,
        severity: ReconciliationSeverity,
        subject_id: str,
        detail: str,
        action: str,
    ) -> None:
        findings.append(
            ReconciliationFinding(code, severity, subject_id, detail, action)
        )
