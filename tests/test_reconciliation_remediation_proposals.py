from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    ReconciliationCaseState,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_remediation_proposals import (
    RemediationActionType,
    RemediationProposalDecision,
    SyntheticRemediationProposalBook,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)
REVIEW_FINDINGS = sha256(b"synthetic remediation proposal source review").hexdigest()


def source_report(codes: tuple[str, ...]) -> dict[str, object]:
    findings = [
        {
            "code": code,
            "severity": "BLOCKED",
            "subject_id": f"synthetic:subject:{number}",
            "detail": "synthetic discrepancy",
            "suggested_action": "Eternian review required",
            "automatic_repair_allowed": False,
        }
        for number, code in enumerate(codes, start=1)
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


def confirmed_case(*, codes: tuple[str, ...]):
    docket = SyntheticReconciliationCaseDocket(":memory:")
    record = docket.submit_report(source_report(codes), submitted_at=NOW)
    record = docket.record_eternian_review(
        record.case_id,
        review_id="synthetic:reconciliation-review:remediation-source",
        reviewer_id="synthetic:eternian-reviewer:remediation-source",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=REVIEW_FINDINGS,
        reviewed_at=NOW,
    )
    return docket, record


class ReconciliationRemediationProposalTests(unittest.TestCase):
    def test_confirmed_case_source_is_integrity_bound_and_read_only(self):
        docket, record = confirmed_case(codes=("PROPOSAL_MISSING_DOCKET",))
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(record.case_id)
        after = docket.evidence()["report_digest"]
        self.assertEqual(source.case_id, record.case_id)
        self.assertEqual(before, after)
        self.assertEqual(
            docket.get(record.case_id).state,
            ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL,
        )
        docket.close()

    def test_known_finding_creates_non_executable_review_proposal(self):
        docket, record = confirmed_case(codes=("PROPOSAL_MISSING_DOCKET",))
        assessment = SyntheticRemediationProposalBook().draft(
            docket, record.case_id, now=NOW
        )
        proposal = assessment.proposal
        self.assertEqual(
            assessment.decision,
            RemediationProposalDecision.PROPOSED_FOR_ETERNIAN_REVIEW,
        )
        self.assertIsNotNone(proposal)
        self.assertEqual(
            proposal.plan_items[0].action_type,
            RemediationActionType.WORKFLOW_LINKAGE_REVIEW,
        )
        self.assertTrue(proposal.review_required)
        self.assertFalse(proposal.code_change_allowed)
        self.assertFalse(proposal.automatic_application_allowed)
        self.assertFalse(proposal.safety_baseline_relaxation_allowed)
        self.assertFalse(proposal.operator_approval_recorded)
        self.assertFalse(proposal.execution_allowed)
        docket.close()

    def test_all_action_categories_use_allowlisted_scopes_and_checks(self):
        codes = (
            "PAYMENT_EVENT_CHAIN_INVALID",
            "PAYMENT_LEDGER_JOURNAL_MISMATCH",
            "PROPOSAL_MISSING_DOCKET",
            "COMPONENT_CHANGED_DURING_INSPECTION",
        )
        docket, record = confirmed_case(codes=codes)
        proposal = SyntheticRemediationProposalBook().draft(
            docket, record.case_id, now=NOW
        ).proposal
        self.assertEqual(
            {item.action_type for item in proposal.plan_items},
            set(RemediationActionType),
        )
        for item in proposal.plan_items:
            self.assertTrue(all(scope.endswith("_ONLY") for scope in item.allowed_scopes))
            self.assertIn("ETERNIAN_REVIEW_REQUIRED", item.required_checks)
            self.assertFalse(item.code_change_allowed)
            self.assertFalse(item.production_access_allowed)
        docket.close()

    def test_unknown_finding_requires_human_review_without_proposal(self):
        docket, record = confirmed_case(codes=("UNKNOWN_FUTURE_FINDING",))
        assessment = SyntheticRemediationProposalBook().draft(
            docket, record.case_id, now=NOW
        )
        self.assertEqual(assessment.decision, RemediationProposalDecision.HUMAN_REVIEW)
        self.assertIsNone(assessment.proposal)
        self.assertIn("UNKNOWN_FUTURE_FINDING", assessment.reason)
        docket.close()

    def test_unconfirmed_and_held_cases_cannot_source_proposals(self):
        pending = SyntheticReconciliationCaseDocket(":memory:")
        pending_record = pending.submit_report(
            source_report(("PROPOSAL_MISSING_DOCKET",)), submitted_at=NOW
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationProposalBook().draft(
                pending, pending_record.case_id, now=NOW
            )
        pending.close()

        held = SyntheticReconciliationCaseDocket(":memory:")
        held_record = held.submit_report(
            source_report(("PROPOSAL_MISSING_DOCKET",)), submitted_at=NOW
        )
        held.record_eternian_review(
            held_record.case_id,
            review_id="synthetic:reconciliation-review:held-source",
            reviewer_id="synthetic:eternian-reviewer:held-source",
            decision=ReconciliationCaseReviewDecision.HOLD,
            findings_digest=REVIEW_FINDINGS,
            reviewed_at=NOW,
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationProposalBook().draft(held, held_record.case_id, now=NOW)
        held.close()

    def test_case_source_is_idempotent_and_concurrent_drafting_records_once(self):
        docket, record = confirmed_case(codes=("PROPOSAL_MISSING_DOCKET",))
        book = SyntheticRemediationProposalBook()

        def draft(_):
            return book.draft(docket, record.case_id, now=NOW)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(draft, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len(book.assessments), 1)
        self.assertTrue(book.verify_assessment_chain())
        docket.close()

    def test_proposal_cannot_predate_reconciliation_observation(self):
        docket, record = confirmed_case(codes=("PROPOSAL_MISSING_DOCKET",))
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationProposalBook().draft(
                docket, record.case_id, now=NOW - timedelta(seconds=1)
            )
        docket.close()

    def test_proposal_item_tampering_breaks_assessment_chain(self):
        docket, record = confirmed_case(codes=("PAYMENT_EVENT_CHAIN_INVALID",))
        book = SyntheticRemediationProposalBook()
        assessment = book.draft(docket, record.case_id, now=NOW)
        item = assessment.proposal.plan_items[0]
        object.__setattr__(item, "subject_id", "synthetic:tampered")
        self.assertFalse(book.verify_assessment_chain())
        docket.close()

    def test_assessment_tampering_is_detected(self):
        docket, record = confirmed_case(codes=("PROPOSAL_MISSING_DOCKET",))
        book = SyntheticRemediationProposalBook()
        book.draft(docket, record.case_id, now=NOW)
        book._assessments[0] = replace(book._assessments[0], reason="tampered")
        self.assertFalse(book.verify_assessment_chain())
        docket.close()

    def test_tampered_source_case_is_blocked(self):
        docket, record = confirmed_case(codes=("PROPOSAL_MISSING_DOCKET",))
        docket._connection.execute(
            "UPDATE synthetic_reconciliation_cases SET report_json = '{}' WHERE case_id = ?",
            (record.case_id,),
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationProposalBook().draft(docket, record.case_id, now=NOW)
        docket.close()

    def test_evidence_has_no_change_apply_relaxation_or_execution_method(self):
        docket, record = confirmed_case(codes=("PROPOSAL_MISSING_DOCKET",))
        book = SyntheticRemediationProposalBook()
        book.draft(docket, record.case_id, now=NOW)
        evidence = book.evidence()
        self.assertTrue(evidence["assessment_chain_valid"])
        self.assertFalse(evidence["code_change_method_present"])
        self.assertFalse(evidence["application_method_present"])
        self.assertFalse(evidence["safety_baseline_relaxation_method_present"])
        self.assertFalse(evidence["operator_decision_method_present"])
        self.assertFalse(evidence["execution_method_present"])
        self.assertFalse(evidence["source_case_state_changed"])
        self.assertFalse(evidence["money_movement_executed"])
        self.assertFalse(evidence["production_activation_allowed"])
        docket.close()


if __name__ == "__main__":
    unittest.main()
