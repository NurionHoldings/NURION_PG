"""Non-executable ARKAON remediation proposal drafts for confirmed synthetic cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock

from .arkaon.governance import GovernanceRejected, canonical_digest
from .reconciliation_case_docket import SyntheticReconciliationCaseDocket


class RemediationActionType(StrEnum):
    EVIDENCE_CHAIN_INVESTIGATION = "EVIDENCE_CHAIN_INVESTIGATION"
    WORKFLOW_LINKAGE_REVIEW = "WORKFLOW_LINKAGE_REVIEW"
    PAYMENT_LEDGER_RECONCILIATION = "PAYMENT_LEDGER_RECONCILIATION"
    STABLE_SNAPSHOT_REPRODUCTION = "STABLE_SNAPSHOT_REPRODUCTION"


class RemediationProposalDecision(StrEnum):
    PROPOSED_FOR_ETERNIAN_REVIEW = "PROPOSED_FOR_ETERNIAN_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"


_ACTION_BY_FINDING = {
    "PAYMENT_EVENT_CHAIN_INVALID": RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
    "INBOX_RECEIPT_CHAIN_INVALID": RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
    "INBOX_ACCEPTED_BINDING_INVALID": RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
    "PROPOSAL_ASSESSMENT_CHAIN_INVALID": RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
    "PROPOSAL_BINDING_INVALID": RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
    "DOCKET_AUDIT_CHAIN_INVALID": RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
    "DOCKET_RECORD_BINDING_INVALID": RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
    "PAYMENT_EVENT_WITHOUT_INTENT": RemediationActionType.PAYMENT_LEDGER_RECONCILIATION,
    "PAYMENT_INTENT_EVENT_MISMATCH": RemediationActionType.PAYMENT_LEDGER_RECONCILIATION,
    "PAYMENT_LEDGER_JOURNAL_MISMATCH": RemediationActionType.PAYMENT_LEDGER_RECONCILIATION,
    "PAYMENT_LEDGER_DUPLICATE_JOURNAL_ID": RemediationActionType.PAYMENT_LEDGER_RECONCILIATION,
    "ACCEPTED_EVENT_UNASSESSED": RemediationActionType.WORKFLOW_LINKAGE_REVIEW,
    "ASSESSMENT_SOURCE_BINDING_MISMATCH": RemediationActionType.WORKFLOW_LINKAGE_REVIEW,
    "ASSESSMENT_SOURCE_NOT_ACCEPTED": RemediationActionType.WORKFLOW_LINKAGE_REVIEW,
    "PROPOSAL_MISSING_DOCKET": RemediationActionType.WORKFLOW_LINKAGE_REVIEW,
    "DOCKET_WITHOUT_PROPOSAL": RemediationActionType.WORKFLOW_LINKAGE_REVIEW,
    "DOCKET_BINDING_MISMATCH": RemediationActionType.WORKFLOW_LINKAGE_REVIEW,
    "COMPONENT_CHANGED_DURING_INSPECTION": RemediationActionType.STABLE_SNAPSHOT_REPRODUCTION,
}

_SCOPES_BY_ACTION = {
    RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION: (
        "EVIDENCE_ANALYSIS_ONLY",
        "SYNTHETIC_FIXTURE_DRAFT_ONLY",
    ),
    RemediationActionType.WORKFLOW_LINKAGE_REVIEW: (
        "WORKFLOW_CONTRACT_DRAFT_ONLY",
        "SYNTHETIC_FIXTURE_DRAFT_ONLY",
    ),
    RemediationActionType.PAYMENT_LEDGER_RECONCILIATION: (
        "DOMAIN_INVARIANT_DRAFT_ONLY",
        "SYNTHETIC_FIXTURE_DRAFT_ONLY",
    ),
    RemediationActionType.STABLE_SNAPSHOT_REPRODUCTION: (
        "CONCURRENCY_TEST_DRAFT_ONLY",
        "SYNTHETIC_FIXTURE_DRAFT_ONLY",
    ),
}

_BASELINE_CHECKS = (
    "PRESERVE_FAIL_CLOSED_BASELINE",
    "ADD_OR_KEEP_REGRESSION_TEST",
    "REGENERATE_SHA256_EVIDENCE",
    "ETERNIAN_REVIEW_REQUIRED",
)


@dataclass(frozen=True)
class RemediationPlanItem:
    ordinal: int
    finding_code: str
    subject_id: str
    action_type: RemediationActionType
    allowed_scopes: tuple[str, ...]
    required_checks: tuple[str, ...]
    item_digest: str
    code_change_allowed: bool = False
    production_access_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            self.ordinal <= 0
            or self.finding_code not in _ACTION_BY_FINDING
            or not self.subject_id.startswith("synthetic:")
            or _ACTION_BY_FINDING[self.finding_code] is not self.action_type
            or self.allowed_scopes != _SCOPES_BY_ACTION[self.action_type]
            or self.required_checks != _BASELINE_CHECKS
            or self.code_change_allowed
            or self.production_access_allowed
            or self.item_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid non-executable remediation plan item required")

    def digest_value(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "finding_code": self.finding_code,
            "subject_id": self.subject_id,
            "action_type": self.action_type.value,
            "allowed_scopes": list(self.allowed_scopes),
            "required_checks": list(self.required_checks),
            "code_change_allowed": False,
            "production_access_allowed": False,
        }


@dataclass(frozen=True)
class ReconciliationRemediationProposal:
    proposal_id: str
    source_case_id: str
    source_report_digest: str
    source_case_review_digest: str
    source_status: str
    plan_items: tuple[RemediationPlanItem, ...]
    created_at: datetime
    proposal_digest: str
    review_required: bool = True
    code_change_allowed: bool = False
    automatic_application_allowed: bool = False
    safety_baseline_relaxation_allowed: bool = False
    operator_approval_recorded: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.proposal_id.startswith("synthetic:remediation-proposal:")
            or not self.source_case_id.startswith("synthetic:reconciliation-case:")
            or not _valid_digest(self.source_report_digest)
            or not _valid_digest(self.source_case_review_digest)
            or self.source_status not in {"HUMAN_REVIEW", "BLOCKED"}
            or not self.plan_items
            or self.created_at.tzinfo is None
            or not self.review_required
            or self.code_change_allowed
            or self.automatic_application_allowed
            or self.safety_baseline_relaxation_allowed
            or self.operator_approval_recorded
            or self.execution_allowed
            or self.proposal_digest != canonical_digest(self.digest_value())
        ):
            raise GovernanceRejected("valid non-executable remediation proposal required")
        if tuple(item.ordinal for item in self.plan_items) != tuple(
            range(1, len(self.plan_items) + 1)
        ):
            raise GovernanceRejected("contiguous remediation plan ordinals required")

    def digest_value(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "source_case_id": self.source_case_id,
            "source_report_digest": self.source_report_digest,
            "source_case_review_digest": self.source_case_review_digest,
            "source_status": self.source_status,
            "plan_item_digests": [item.item_digest for item in self.plan_items],
            "created_at": self.created_at.isoformat(),
            "review_required": True,
            "code_change_allowed": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "operator_approval_recorded": False,
            "execution_allowed": False,
        }


@dataclass(frozen=True)
class RemediationProposalAssessment:
    sequence: int
    source_case_id: str
    source_report_digest: str
    source_case_review_digest: str
    decision: RemediationProposalDecision
    reason: str
    assessed_at: datetime
    proposal: ReconciliationRemediationProposal | None
    previous_digest: str
    assessment_digest: str
    source_case_state_changed: bool = False


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class SyntheticRemediationProposalBook:
    """Creates review-only remediation drafts and exposes no apply method."""

    def __init__(self) -> None:
        self._assessments: list[RemediationProposalAssessment] = []
        self._by_case: dict[str, RemediationProposalAssessment] = {}
        self._lock = RLock()

    @property
    def assessments(self) -> tuple[RemediationProposalAssessment, ...]:
        with self._lock:
            return tuple(self._assessments)

    def draft(
        self,
        docket: SyntheticReconciliationCaseDocket,
        case_id: str,
        *,
        now: datetime,
    ) -> RemediationProposalAssessment:
        if now.tzinfo is None:
            raise GovernanceRejected("timezone-aware remediation proposal time required")
        with self._lock:
            existing = self._by_case.get(case_id)
            if existing is not None:
                return existing
            before = docket.evidence()["report_digest"]
            source = docket.ready_source(case_id)
            try:
                report = json.loads(source.report_json)
            except (TypeError, ValueError) as exc:
                raise GovernanceRejected("ready case report JSON is invalid") from exc
            if not isinstance(report, dict) or report.get("report_digest") != source.report_digest:
                raise GovernanceRejected("ready case report binding is invalid")
            observed_at = datetime.fromisoformat(str(report["observed_at"]))
            if now < observed_at:
                raise GovernanceRejected("proposal cannot predate reconciliation observation")
            unsupported = sorted(
                {
                    str(finding.get("code"))
                    for finding in report["findings"]
                    if finding.get("code") not in _ACTION_BY_FINDING
                }
            )
            if unsupported:
                assessment = self._record(
                    source.case_id,
                    source.report_digest,
                    source.review_digest,
                    RemediationProposalDecision.HUMAN_REVIEW,
                    "unsupported_finding_codes:" + ",".join(unsupported),
                    now,
                    None,
                )
            else:
                proposal = self._build_proposal(source, report, now)
                assessment = self._record(
                    source.case_id,
                    source.report_digest,
                    source.review_digest,
                    RemediationProposalDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
                    "structured_non_executable_remediation_draft_only",
                    now,
                    proposal,
                )
            after = docket.evidence()["report_digest"]
            if before != after:
                self._assessments.pop()
                self._by_case.pop(case_id, None)
                raise GovernanceRejected("source case changed during proposal drafting")
            return assessment

    @staticmethod
    def _build_proposal(source, report: dict[str, object], now: datetime):
        items = []
        ordered_findings = sorted(
            report["findings"],  # type: ignore[arg-type]
            key=lambda item: (str(item["code"]), str(item["subject_id"])),
        )
        for ordinal, finding in enumerate(ordered_findings, start=1):
            code = str(finding["code"])
            action = _ACTION_BY_FINDING[code]
            value = {
                "ordinal": ordinal,
                "finding_code": code,
                "subject_id": str(finding["subject_id"]),
                "action_type": action.value,
                "allowed_scopes": list(_SCOPES_BY_ACTION[action]),
                "required_checks": list(_BASELINE_CHECKS),
                "code_change_allowed": False,
                "production_access_allowed": False,
            }
            items.append(
                RemediationPlanItem(
                    ordinal,
                    code,
                    str(finding["subject_id"]),
                    action,
                    _SCOPES_BY_ACTION[action],
                    _BASELINE_CHECKS,
                    canonical_digest(value),
                )
            )
        identity = canonical_digest(
            {
                "source_case_id": source.case_id,
                "source_report_digest": source.report_digest,
                "source_case_review_digest": source.review_digest,
                "plan_item_digests": [item.item_digest for item in items],
            }
        )
        proposal_id = f"synthetic:remediation-proposal:{identity[:32]}"
        value = {
            "proposal_id": proposal_id,
            "source_case_id": source.case_id,
            "source_report_digest": source.report_digest,
            "source_case_review_digest": source.review_digest,
            "source_status": report["status"],
            "plan_item_digests": [item.item_digest for item in items],
            "created_at": now.isoformat(),
            "review_required": True,
            "code_change_allowed": False,
            "automatic_application_allowed": False,
            "safety_baseline_relaxation_allowed": False,
            "operator_approval_recorded": False,
            "execution_allowed": False,
        }
        return ReconciliationRemediationProposal(
            proposal_id,
            source.case_id,
            source.report_digest,
            source.review_digest,
            str(report["status"]),
            tuple(items),
            now,
            canonical_digest(value),
        )

    def _record(
        self,
        case_id: str,
        report_digest: str,
        review_digest: str,
        decision: RemediationProposalDecision,
        reason: str,
        assessed_at: datetime,
        proposal: ReconciliationRemediationProposal | None,
    ) -> RemediationProposalAssessment:
        previous = self._assessments[-1].assessment_digest if self._assessments else "0" * 64
        sequence = len(self._assessments) + 1
        value = {
            "sequence": sequence,
            "source_case_id": case_id,
            "source_report_digest": report_digest,
            "source_case_review_digest": review_digest,
            "decision": decision.value,
            "reason": reason,
            "assessed_at": assessed_at.isoformat(),
            "proposal_digest": proposal.proposal_digest if proposal is not None else None,
            "previous_digest": previous,
            "source_case_state_changed": False,
        }
        assessment = RemediationProposalAssessment(
            sequence,
            case_id,
            report_digest,
            review_digest,
            decision,
            reason,
            assessed_at,
            proposal,
            previous,
            canonical_digest(value),
        )
        self._assessments.append(assessment)
        self._by_case[case_id] = assessment
        return assessment

    def verify_assessment_chain(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for sequence, assessment in enumerate(self._assessments, start=1):
                proposal = assessment.proposal
                proposal_valid = proposal is None or (
                    proposal.proposal_digest == canonical_digest(proposal.digest_value())
                    and proposal.source_case_id == assessment.source_case_id
                    and proposal.source_report_digest == assessment.source_report_digest
                    and proposal.source_case_review_digest
                    == assessment.source_case_review_digest
                    and proposal.review_required
                    and not proposal.code_change_allowed
                    and not proposal.automatic_application_allowed
                    and not proposal.safety_baseline_relaxation_allowed
                    and not proposal.operator_approval_recorded
                    and not proposal.execution_allowed
                    and tuple(item.ordinal for item in proposal.plan_items)
                    == tuple(range(1, len(proposal.plan_items) + 1))
                    and all(
                        item.item_digest == canonical_digest(item.digest_value())
                        and item.finding_code in _ACTION_BY_FINDING
                        and _ACTION_BY_FINDING[item.finding_code] is item.action_type
                        and item.allowed_scopes == _SCOPES_BY_ACTION[item.action_type]
                        and item.required_checks == _BASELINE_CHECKS
                        and not item.code_change_allowed
                        and not item.production_access_allowed
                        for item in proposal.plan_items
                    )
                )
                value = {
                    "sequence": sequence,
                    "source_case_id": assessment.source_case_id,
                    "source_report_digest": assessment.source_report_digest,
                    "source_case_review_digest": assessment.source_case_review_digest,
                    "decision": assessment.decision.value,
                    "reason": assessment.reason,
                    "assessed_at": assessment.assessed_at.isoformat(),
                    "proposal_digest": proposal.proposal_digest if proposal is not None else None,
                    "previous_digest": previous,
                    "source_case_state_changed": False,
                }
                if (
                    assessment.sequence != sequence
                    or assessment.previous_digest != previous
                    or assessment.assessment_digest != canonical_digest(value)
                    or assessment.source_case_state_changed
                    or not proposal_valid
                    or (
                        assessment.decision
                        is RemediationProposalDecision.PROPOSED_FOR_ETERNIAN_REVIEW
                        and proposal is None
                    )
                    or (
                        assessment.decision is RemediationProposalDecision.HUMAN_REVIEW
                        and proposal is not None
                    )
                ):
                    return False
                previous = assessment.assessment_digest
            return True

    def evidence(self) -> dict[str, object]:
        with self._lock:
            counts = {decision.value: 0 for decision in RemediationProposalDecision}
            proposals = []
            for assessment in self._assessments:
                counts[assessment.decision.value] += 1
                if assessment.proposal is not None:
                    proposals.append(assessment.proposal.proposal_digest)
            value = {
                "schema": "nurion.pg.synthetic-remediation-proposal-evidence.v1",
                "decision_counts": counts,
                "proposal_digests": proposals,
                "assessment_chain_valid": self.verify_assessment_chain(),
                "review_required": True,
                "code_change_method_present": False,
                "application_method_present": False,
                "safety_baseline_relaxation_method_present": False,
                "operator_decision_method_present": False,
                "execution_method_present": False,
                "source_case_state_changed": False,
                "money_movement_executed": False,
                "production_activation_allowed": False,
            }
            return {**value, "report_digest": canonical_digest(value)}
