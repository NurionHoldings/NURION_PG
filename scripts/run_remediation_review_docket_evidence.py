"""Generate deterministic evidence for the synthetic remediation review docket."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import canonical_digest
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_remediation_proposals import (
    RemediationProposalDecision,
    SyntheticRemediationProposalBook,
)
from nurion_pg.remediation_review_docket import (
    RemediationDocketState,
    RemediationReviewDecision,
    SyntheticRemediationReviewDocket,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 17, tzinfo=UTC)
CASE_FINDINGS = sha256(b"synthetic remediation docket source review").hexdigest()
PROPOSAL_FINDINGS = sha256(b"synthetic remediation docket review").hexdigest()


def reconciliation_report() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": "BLOCKED",
        "component_snapshot_digests": {
            name: sha256(f"synthetic:{name}".encode("ascii")).hexdigest()
            for name in ("payment", "inbox", "proposals", "docket")
        },
        "findings": [
            {
                "code": "PROPOSAL_MISSING_DOCKET",
                "severity": "BLOCKED",
                "subject_id": "synthetic:proposal:remediation-docket-evidence",
                "detail": "synthetic accepted proposal has no review docket",
                "suggested_action": "Eternian review required",
                "automatic_repair_allowed": False,
            }
        ],
        "finding_counts": {"WARNING": 0, "BLOCKED": 1},
        "read_only_verified": True,
        "synthetic_only": True,
        "automatic_repair_allowed": False,
        "operator_decision_recorded": False,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_activation_allowed": False,
    }
    return {**value, "report_digest": canonical_digest(value)}


def main() -> None:
    policy = json.loads(
        (ROOT / "config/remediation-review-docket-policy.json").read_text(
            encoding="utf-8"
        )
    )
    forbidden = (
        "automatic_review_allowed",
        "synthetic_shadow_generation_allowed",
        "code_change_allowed",
        "automatic_application_allowed",
        "operator_decision_allowed",
        "payment_execution_allowed",
        "money_movement_allowed",
        "production_activation_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_proposal_decision"]
        != "PROPOSED_FOR_ETERNIAN_REVIEW"
        or policy["maximum_state"] != "READY_FOR_SYNTHETIC_SHADOW"
        or policy["review_authority"] != "ETERNIAN_INDEPENDENT_REVIEW"
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("remediation review docket policy drift detected")

    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(reconciliation_report(), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:remediation-docket-evidence",
        reviewer_id="synthetic:eternian-reviewer:remediation-docket-source",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=CASE_FINDINGS,
        reviewed_at=NOW,
    )
    proposal_book = SyntheticRemediationProposalBook()
    assessment = proposal_book.draft(case_docket, case.case_id, now=NOW)
    proposal = assessment.proposal
    review_docket = SyntheticRemediationReviewDocket(":memory:")
    submitted = review_docket.submit_from_book(
        proposal_book, case.case_id, submitted_at=NOW
    )
    reviewed = review_docket.record_eternian_review(
        submitted.proposal_id,
        review_id="synthetic:remediation-review:evidence",
        reviewer_id="synthetic:eternian-reviewer:independent-evidence",
        decision=RemediationReviewDecision.PASS,
        findings_digest=PROPOSAL_FINDINGS,
        reviewed_at=NOW,
    )
    report = review_docket.evidence()
    case_docket.close()
    review_docket.close()

    if (
        assessment.decision
        is not RemediationProposalDecision.PROPOSED_FOR_ETERNIAN_REVIEW
        or proposal is None
        or reviewed.state is not RemediationDocketState.READY_FOR_SYNTHETIC_SHADOW
        or reviewed.proposal_digest != proposal.proposal_digest
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["maximum_state"] != "READY_FOR_SYNTHETIC_SHADOW"
        or report["synthetic_shadow_method_present"] is not False
        or report["code_change_method_present"] is not False
        or report["application_method_present"] is not False
        or report["operator_decision_method_present"] is not False
        or report["execution_method_present"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("synthetic remediation review docket boundary failed")

    output = ROOT / "build/synthetic-remediation-review-docket-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic remediation review docket: PASS {digest}")


if __name__ == "__main__":
    main()
