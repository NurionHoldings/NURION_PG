"""Generate deterministic evidence for the synthetic shadow review docket."""

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
from nurion_pg.reconciliation_remediation_proposals import SyntheticRemediationProposalBook
from nurion_pg.remediation_review_docket import (
    RemediationReviewDecision,
    SyntheticRemediationReviewDocket,
)
from nurion_pg.remediation_shadow_review_docket import (
    ShadowReviewDecision,
    ShadowReviewState,
    SyntheticRemediationShadowReviewDocket,
)
from nurion_pg.remediation_synthetic_shadow import (
    SyntheticRemediationShadowBook,
    SyntheticRemediationShadowFixture,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 17, tzinfo=UTC)


def source_report() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": "BLOCKED",
        "component_snapshot_digests": {
            name: sha256(f"shadow-review:{name}".encode("ascii")).hexdigest()
            for name in ("payment", "inbox", "proposals", "docket")
        },
        "findings": [
            {
                "code": "PROPOSAL_MISSING_DOCKET",
                "severity": "BLOCKED",
                "subject_id": "synthetic:proposal:shadow-review-evidence",
                "detail": "synthetic proposal is absent from review docket",
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
        (ROOT / "config/remediation-shadow-review-docket-policy.json").read_text(
            encoding="utf-8"
        )
    )
    forbidden = (
        "automatic_review_allowed",
        "operator_decision_recording_allowed",
        "code_change_allowed",
        "automatic_application_allowed",
        "payment_execution_allowed",
        "money_movement_allowed",
        "production_activation_allowed",
        "real_credentials_allowed",
        "real_personal_data_allowed",
    )
    if (
        policy["mode"] != "UNREGISTERED_SYNTHETIC_ONLY"
        or policy["required_shadow_decision"] != "PROPOSED_FOR_ETERNIAN_REVIEW"
        or policy["review_authority"] != "ETERNIAN_INDEPENDENT_REVIEW"
        or policy["maximum_state"] != "READY_FOR_OPERATOR_DECISION"
        or any(policy[field] is not False for field in forbidden)
    ):
        raise SystemExit("shadow review docket policy drift detected")

    findings = sha256(b"synthetic shadow review evidence").hexdigest()
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:shadow-review-evidence",
        reviewer_id="synthetic:eternian-reviewer:shadow-review-case",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    proposal_book = SyntheticRemediationProposalBook()
    proposal = proposal_book.draft(case_docket, case.case_id, now=NOW).proposal
    if proposal is None:
        raise SystemExit("synthetic remediation proposal was not created")
    remediation_docket = SyntheticRemediationReviewDocket(":memory:")
    remediation = remediation_docket.submit_from_book(
        proposal_book, case.case_id, submitted_at=NOW
    )
    remediation_docket.record_eternian_review(
        remediation.proposal_id,
        review_id="synthetic:remediation-review:shadow-review-evidence",
        reviewer_id="synthetic:eternian-reviewer:shadow-review-proposal",
        decision=RemediationReviewDecision.PASS,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    item = proposal.plan_items[0]
    fixture_value = {
        "fixture_id": "synthetic:remediation-shadow-fixture:review-evidence",
        "plan_item_digest": item.item_digest,
        "action_type": item.action_type.value,
        "fixture_seed_digest": sha256(b"shadow review fixture seed").hexdigest(),
        "trigger_observed": True,
        "fail_closed_baseline_preserved": True,
        "regression_test_passed": True,
        "sha256_evidence_reproduced": True,
        "eternian_review_retained": True,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_access_used": False,
    }
    fixture = SyntheticRemediationShadowFixture(
        fixture_value["fixture_id"],
        fixture_value["plan_item_digest"],
        item.action_type,
        fixture_value["fixture_seed_digest"],
        True,
        True,
        True,
        True,
        True,
        False,
        False,
        False,
        canonical_digest(fixture_value),
    )
    shadow_book = SyntheticRemediationShadowBook()
    shadow = shadow_book.evaluate(
        remediation_docket,
        proposal.proposal_id,
        (fixture,),
        evaluated_at=NOW,
    )
    review_docket = SyntheticRemediationShadowReviewDocket(":memory:")
    submitted = review_docket.submit_from_book(
        shadow_book, proposal.proposal_id, submitted_at=NOW
    )
    reviewed = review_docket.record_eternian_review(
        submitted.shadow_id,
        review_id="synthetic:shadow-review:evidence",
        reviewer_id="synthetic:eternian-reviewer:shadow-review-independent",
        decision=ShadowReviewDecision.PASS,
        findings_digest=findings,
        reviewed_at=NOW,
    )
    ready = review_docket.ready_source(submitted.shadow_id)
    report = review_docket.evidence()
    review_docket.close()
    remediation_docket.close()
    case_docket.close()

    if (
        reviewed.state is not ShadowReviewState.READY_FOR_OPERATOR_DECISION
        or reviewed.operator_decision_recorded
        or ready.shadow_assessment_digest != shadow.assessment_digest
        or report["audit_chain_valid"] is not True
        or report["record_bindings_valid"] is not True
        or report["maximum_state"] != "READY_FOR_OPERATOR_DECISION"
        or report["operator_decision_method_present"] is not False
        or report["code_change_method_present"] is not False
        or report["application_method_present"] is not False
        or report["execution_method_present"] is not False
        or report["money_movement_executed"] is not False
        or report["production_activation_allowed"] is not False
    ):
        raise SystemExit("synthetic shadow review docket boundary failed")

    output = ROOT / "build/synthetic-shadow-review-docket-evidence.json"
    output.parent.mkdir(exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = sha256(payload.encode("utf-8")).hexdigest()
    output.with_suffix(".json.sha256").write_text(digest + "\n", encoding="ascii")
    print(f"synthetic shadow review docket: PASS {digest}")


if __name__ == "__main__":
    main()
