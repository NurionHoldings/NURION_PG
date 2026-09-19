from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_remediation_proposals import (
    RemediationActionType,
    SyntheticRemediationProposalBook,
)
from nurion_pg.remediation_review_docket import (
    RemediationReviewDecision,
    SyntheticRemediationReviewDocket,
)
from nurion_pg.remediation_synthetic_shadow import (
    RemediationShadowDecision,
    ShadowItemDecision,
    SyntheticRemediationShadowBook,
    SyntheticRemediationShadowFixture,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)
CASE_FINDINGS = sha256(b"synthetic shadow source case").hexdigest()
REVIEW_FINDINGS = sha256(b"synthetic shadow proposal review").hexdigest()


def source_report(codes: tuple[str, ...]) -> dict[str, object]:
    findings = [
        {
            "code": code,
            "severity": "BLOCKED",
            "subject_id": f"synthetic:shadow-subject:{index}",
            "detail": "synthetic discrepancy",
            "suggested_action": "Eternian review required",
            "automatic_repair_allowed": False,
        }
        for index, code in enumerate(codes, start=1)
    ]
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": "BLOCKED",
        "component_snapshot_digests": {
            name: sha256(name.encode("ascii")).hexdigest()
            for name in ("payment", "inbox", "proposals", "docket")
        },
        "findings": findings,
        "finding_counts": {"WARNING": 0, "BLOCKED": len(findings)},
        "read_only_verified": True,
        "synthetic_only": True,
        "automatic_repair_allowed": False,
        "operator_decision_recorded": False,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_activation_allowed": False,
    }
    return {**value, "report_digest": canonical_digest(value)}


def ready_proposal(codes: tuple[str, ...] = ("PROPOSAL_MISSING_DOCKET",)):
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(codes), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:shadow-source",
        reviewer_id="synthetic:eternian-reviewer:shadow-case",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=CASE_FINDINGS,
        reviewed_at=NOW,
    )
    proposal_book = SyntheticRemediationProposalBook()
    assessment = proposal_book.draft(case_docket, case.case_id, now=NOW)
    review_docket = SyntheticRemediationReviewDocket(":memory:")
    record = review_docket.submit_from_book(proposal_book, case.case_id, submitted_at=NOW)
    review_docket.record_eternian_review(
        record.proposal_id,
        review_id="synthetic:remediation-review:shadow-source",
        reviewer_id="synthetic:eternian-reviewer:shadow-proposal",
        decision=RemediationReviewDecision.PASS,
        findings_digest=REVIEW_FINDINGS,
        reviewed_at=NOW,
    )
    return case_docket, review_docket, assessment.proposal


def fixture(item, index: int, **changes) -> SyntheticRemediationShadowFixture:
    values = {
        "fixture_id": f"synthetic:remediation-shadow-fixture:{index}",
        "plan_item_digest": item.item_digest,
        "action_type": item.action_type,
        "fixture_seed_digest": sha256(f"fixture:{index}".encode("ascii")).hexdigest(),
        "trigger_observed": True,
        "fail_closed_baseline_preserved": True,
        "regression_test_passed": True,
        "sha256_evidence_reproduced": True,
        "eternian_review_retained": True,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_access_used": False,
        **changes,
    }
    digest_value = {
        **values,
        "action_type": values["action_type"].value,
    }
    return SyntheticRemediationShadowFixture(
        **values,
        fixture_digest=canonical_digest(digest_value),
    )


def fixtures_for(proposal, **changes):
    return tuple(
        fixture(item, index, **changes)
        for index, item in enumerate(proposal.plan_items, start=1)
    )


class RemediationSyntheticShadowTests(unittest.TestCase):
    def test_ready_source_is_integrity_bound_and_read_only(self):
        case_docket, docket, proposal = ready_proposal()
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(proposal.proposal_id)
        after = docket.evidence()["report_digest"]
        self.assertEqual(source.proposal_digest, proposal.proposal_digest)
        self.assertEqual(before, after)
        docket.close()
        case_docket.close()

    def test_all_passed_fixtures_create_review_only_shadow_assessment(self):
        case_docket, docket, proposal = ready_proposal(
            (
                "PAYMENT_EVENT_CHAIN_INVALID",
                "PAYMENT_LEDGER_JOURNAL_MISMATCH",
                "PROPOSAL_MISSING_DOCKET",
                "COMPONENT_CHANGED_DURING_INSPECTION",
            )
        )
        book = SyntheticRemediationShadowBook()
        assessment = book.evaluate(
            docket,
            proposal.proposal_id,
            fixtures_for(proposal),
            evaluated_at=NOW,
        )
        self.assertEqual(
            assessment.decision,
            RemediationShadowDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
        )
        self.assertTrue(
            all(item.decision is ShadowItemDecision.PASS for item in assessment.item_results)
        )
        self.assertEqual(
            {item.action_type for item in assessment.item_results},
            set(RemediationActionType),
        )
        self.assertTrue(book.verify_assessment_chain())
        docket.close()
        case_docket.close()

    def test_incomplete_control_requires_human_review(self):
        case_docket, docket, proposal = ready_proposal()
        assessment = SyntheticRemediationShadowBook().evaluate(
            docket,
            proposal.proposal_id,
            fixtures_for(proposal, regression_test_passed=False),
            evaluated_at=NOW,
        )
        self.assertEqual(assessment.decision, RemediationShadowDecision.HUMAN_REVIEW)
        self.assertEqual(
            assessment.item_results[0].reason,
            "incomplete_synthetic_shadow_controls",
        )
        docket.close()
        case_docket.close()

    def test_any_forbidden_side_effect_blocks_shadow(self):
        case_docket, docket, proposal = ready_proposal()
        assessment = SyntheticRemediationShadowBook().evaluate(
            docket,
            proposal.proposal_id,
            fixtures_for(proposal, money_movement_executed=True),
            evaluated_at=NOW,
        )
        self.assertEqual(assessment.decision, RemediationShadowDecision.BLOCKED)
        self.assertFalse(assessment.execution_allowed)
        docket.close()
        case_docket.close()

    def test_exact_fixture_set_and_action_binding_are_required(self):
        case_docket, docket, proposal = ready_proposal()
        book = SyntheticRemediationShadowBook()
        with self.assertRaises(GovernanceRejected):
            book.evaluate(docket, proposal.proposal_id, (), evaluated_at=NOW)
        valid = fixture(proposal.plan_items[0], 1)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                docket, proposal.proposal_id, (valid, valid), evaluated_at=NOW
            )
        wrong = fixture(
            proposal.plan_items[0],
            2,
            action_type=RemediationActionType.EVIDENCE_CHAIN_INVESTIGATION,
        )
        with self.assertRaises(GovernanceRejected):
            book.evaluate(docket, proposal.proposal_id, (wrong,), evaluated_at=NOW)
        docket.close()
        case_docket.close()

    def test_tampered_fixture_digest_is_rejected(self):
        case_docket, docket, proposal = ready_proposal()
        item = fixture(proposal.plan_items[0], 1)
        object.__setattr__(item, "trigger_observed", False)
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationShadowBook().evaluate(
                docket, proposal.proposal_id, (item,), evaluated_at=NOW
            )
        docket.close()
        case_docket.close()

    def test_concurrent_replay_is_idempotent_but_payload_change_is_rejected(self):
        case_docket, docket, proposal = ready_proposal()
        book = SyntheticRemediationShadowBook()
        items = fixtures_for(proposal)

        def evaluate(_):
            return book.evaluate(
                docket, proposal.proposal_id, items, evaluated_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(evaluate, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(book.assessments), 1)
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                docket,
                proposal.proposal_id,
                fixtures_for(proposal, trigger_observed=False),
                evaluated_at=NOW,
            )
        docket.close()
        case_docket.close()

    def test_source_tampering_and_invalid_time_fail_closed(self):
        case_docket, docket, proposal = ready_proposal()
        book = SyntheticRemediationShadowBook()
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                docket,
                proposal.proposal_id,
                fixtures_for(proposal),
                evaluated_at=NOW - timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                docket,
                proposal.proposal_id,
                fixtures_for(proposal),
                evaluated_at=datetime(2026, 9, 17),
            )
        docket._connection.execute(
            "UPDATE synthetic_remediation_docket_audit SET actor_id = 'synthetic:tampered'"
        )
        with self.assertRaises(GovernanceRejected):
            book.evaluate(
                docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW
            )
        self.assertEqual(len(book.assessments), 0)
        docket.close()
        case_docket.close()

    def test_result_or_assessment_tampering_breaks_chain(self):
        case_docket, docket, proposal = ready_proposal()
        book = SyntheticRemediationShadowBook()
        assessment = book.evaluate(
            docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW
        )
        object.__setattr__(assessment.item_results[0], "reason", "tampered")
        self.assertFalse(book.verify_assessment_chain())
        docket.close()
        case_docket.close()

    def test_evidence_proves_no_source_change_apply_or_execution(self):
        case_docket, docket, proposal = ready_proposal()
        before = docket.evidence()["report_digest"]
        book = SyntheticRemediationShadowBook()
        book.evaluate(docket, proposal.proposal_id, fixtures_for(proposal), evaluated_at=NOW)
        after = docket.evidence()["report_digest"]
        evidence = book.evidence()
        self.assertEqual(before, after)
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertEqual(evidence["maximum_decision"], "PROPOSED_FOR_ETERNIAN_REVIEW")
        for field in (
            "source_docket_state_changed",
            "code_change_method_present",
            "application_method_present",
            "operator_decision_method_present",
            "execution_method_present",
            "payment_state_changed",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        docket.close()
        case_docket.close()


if __name__ == "__main__":
    unittest.main()
