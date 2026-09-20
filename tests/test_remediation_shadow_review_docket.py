from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    SyntheticReconciliationCaseDocket,
)
from nurion_pg.reconciliation_remediation_proposals import (
    SyntheticRemediationProposalBook,
)
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


NOW = datetime(2026, 9, 17, tzinfo=UTC)
FINDINGS = sha256(b"synthetic shadow docket review").hexdigest()


def source_report() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": "BLOCKED",
        "component_snapshot_digests": {
            name: sha256(name.encode("ascii")).hexdigest()
            for name in ("payment", "inbox", "proposals", "docket")
        },
        "findings": [
            {
                "code": "PROPOSAL_MISSING_DOCKET",
                "severity": "BLOCKED",
                "subject_id": "synthetic:shadow-review-subject",
                "detail": "synthetic discrepancy",
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


def shadow_source(*, regression_test_passed: bool = True):
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:shadow-docket-source",
        reviewer_id="synthetic:eternian-reviewer:shadow-docket-case",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    proposal_book = SyntheticRemediationProposalBook()
    proposal_assessment = proposal_book.draft(case_docket, case.case_id, now=NOW)
    proposal = proposal_assessment.proposal
    remediation_docket = SyntheticRemediationReviewDocket(":memory:")
    remediation = remediation_docket.submit_from_book(
        proposal_book, case.case_id, submitted_at=NOW
    )
    remediation_docket.record_eternian_review(
        remediation.proposal_id,
        review_id="synthetic:remediation-review:shadow-docket-source",
        reviewer_id="synthetic:eternian-reviewer:shadow-docket-proposal",
        decision=RemediationReviewDecision.PASS,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    plan_item = proposal.plan_items[0]
    fixture_value = {
        "fixture_id": "synthetic:remediation-shadow-fixture:docket-source",
        "plan_item_digest": plan_item.item_digest,
        "action_type": plan_item.action_type.value,
        "fixture_seed_digest": sha256(b"shadow docket fixture").hexdigest(),
        "trigger_observed": True,
        "fail_closed_baseline_preserved": True,
        "regression_test_passed": regression_test_passed,
        "sha256_evidence_reproduced": True,
        "eternian_review_retained": True,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_access_used": False,
    }
    fixture = SyntheticRemediationShadowFixture(
        fixture_value["fixture_id"],
        fixture_value["plan_item_digest"],
        plan_item.action_type,
        fixture_value["fixture_seed_digest"],
        True,
        True,
        regression_test_passed,
        True,
        True,
        False,
        False,
        False,
        canonical_digest(fixture_value),
    )
    shadow_book = SyntheticRemediationShadowBook()
    assessment = shadow_book.evaluate(
        remediation_docket,
        proposal.proposal_id,
        (fixture,),
        evaluated_at=NOW,
    )
    return case_docket, remediation_docket, shadow_book, assessment


class RemediationShadowReviewDocketTests(unittest.TestCase):
    def test_requires_synthetic_sqlite_target(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationShadowReviewDocket("production.sqlite")
        with self.assertRaises(GovernanceRejected):
            SyntheticRemediationShadowReviewDocket("postgresql://prod/shadow")

    def test_passed_shadow_is_persisted_pending_review(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        self.assertEqual(record.state, ShadowReviewState.PENDING_ETERNIAN_REVIEW)
        self.assertEqual(record.shadow_assessment_digest, assessment.assessment_digest)
        self.assertFalse(record.automatic_review_allowed)
        self.assertTrue(docket.verify_audit_chain())
        self.assertTrue(docket.verify_record_bindings())
        docket.close()
        remediation.close()
        case.close()

    def test_nonpassing_shadow_cannot_enter_docket(self):
        case, remediation, book, assessment = shadow_source(regression_test_passed=False)
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        docket.close()
        remediation.close()
        case.close()

    def test_tampered_assessment_chain_is_blocked(self):
        case, remediation, book, assessment = shadow_source()
        object.__setattr__(book._assessments[0], "reason", "tampered")
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        docket.close()
        remediation.close()
        case.close()

    def test_pass_stops_at_ready_for_operator_decision(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        reviewed = docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:shadow-review:pass",
            reviewer_id="synthetic:eternian-reviewer:shadow-independent",
            decision=ShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(reviewed.state, ShadowReviewState.READY_FOR_OPERATOR_DECISION)
        self.assertFalse(reviewed.operator_decision_recorded)
        evidence = docket.evidence()
        self.assertEqual(evidence["maximum_state"], "READY_FOR_OPERATOR_DECISION")
        self.assertFalse(evidence["operator_decision_method_present"])
        self.assertFalse(evidence["execution_method_present"])
        docket.close()
        remediation.close()
        case.close()

    def test_hold_and_reject_are_terminal(self):
        for decision, state in (
            (ShadowReviewDecision.HOLD, ShadowReviewState.HELD),
            (ShadowReviewDecision.REJECT, ShadowReviewState.REJECTED),
        ):
            case, remediation, book, assessment = shadow_source()
            docket = SyntheticRemediationShadowReviewDocket(":memory:")
            record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
            result = docket.record_eternian_review(
                record.shadow_id,
                review_id=f"synthetic:shadow-review:{decision.value.lower()}",
                reviewer_id="synthetic:eternian-reviewer:shadow-independent",
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(result.state, state)
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(
                    record.shadow_id,
                    review_id="synthetic:shadow-review:second",
                    reviewer_id="synthetic:eternian-reviewer:shadow-independent",
                    decision=ShadowReviewDecision.PASS,
                    findings_digest=FINDINGS,
                    reviewed_at=NOW,
                )
            docket.close()
            remediation.close()
            case.close()

    def test_review_metadata_time_and_idempotency_are_enforced(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                review_id="bad",
                reviewer_id="synthetic:eternian-reviewer:shadow-independent",
                decision=ShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:shadow-review:early",
                reviewer_id="synthetic:eternian-reviewer:shadow-independent",
                decision=ShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW - timedelta(seconds=1),
            )
        arguments = {
            "review_id": "synthetic:shadow-review:idempotent",
            "reviewer_id": "synthetic:eternian-reviewer:shadow-independent",
            "decision": ShadowReviewDecision.PASS,
            "findings_digest": FINDINGS,
            "reviewed_at": NOW,
        }
        first = docket.record_eternian_review(record.shadow_id, **arguments)
        second = docket.record_eternian_review(record.shadow_id, **arguments)
        self.assertEqual(first, second)
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                **{**arguments, "findings_digest": sha256(b"different").hexdigest()},
            )
        docket.close()
        remediation.close()
        case.close()

    def test_restart_preserves_review_state(self):
        case, remediation, book, assessment = shadow_source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-shadow-review.sqlite3"
            docket = SyntheticRemediationShadowReviewDocket(path)
            record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
            docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:shadow-review:restart",
                reviewer_id="synthetic:eternian-reviewer:shadow-restart",
                decision=ShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            docket.close()
            reopened = SyntheticRemediationShadowReviewDocket(path)
            self.assertEqual(
                reopened.get(record.shadow_id).state,
                ShadowReviewState.READY_FOR_OPERATOR_DECISION,
            )
            self.assertTrue(reopened.verify_audit_chain())
            self.assertTrue(reopened.verify_record_bindings())
            reopened.close()
        remediation.close()
        case.close()

    def test_concurrent_review_records_one_transition(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)

        def review(_):
            return docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:shadow-review:concurrent",
                reviewer_id="synthetic:eternian-reviewer:shadow-concurrent",
                decision=ShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(review, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_shadow_reviews"
        ).fetchone()[0]
        self.assertEqual(count, 1)
        docket.close()
        remediation.close()
        case.close()

    def test_audit_failure_rolls_back_submission(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")

        def fail(**_):
            raise sqlite3.IntegrityError("synthetic audit failure")

        docket._append_audit = fail
        with self.assertRaises(GovernanceRejected):
            docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_shadow_review_dockets"
        ).fetchone()[0]
        self.assertEqual(count, 0)
        docket.close()
        remediation.close()
        case.close()

    def test_tampering_is_detected_and_blocks_pending_review(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_shadow_review_audit SET actor_id = 'synthetic:tampered'"
        )
        self.assertFalse(docket.verify_audit_chain())
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.shadow_id,
                review_id="synthetic:shadow-review:blocked-tamper",
                reviewer_id="synthetic:eternian-reviewer:shadow-independent",
                decision=ShadowReviewDecision.PASS,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
        review_count = docket._connection.execute(
            "SELECT COUNT(*) FROM synthetic_shadow_reviews"
        ).fetchone()[0]
        self.assertEqual(review_count, 0)
        docket._connection.execute(
            "UPDATE synthetic_shadow_review_dockets SET assessment_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(record.shadow_id)
        docket.close()
        remediation.close()
        case.close()

    def test_ready_source_requires_pass_and_is_read_only(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):
            docket.ready_source(record.shadow_id)
        docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:shadow-review:ready-source",
            reviewer_id="synthetic:eternian-reviewer:shadow-ready-source",
            decision=ShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        before = docket.evidence()["report_digest"]
        source = docket.ready_source(record.shadow_id)
        after = docket.evidence()["report_digest"]
        self.assertEqual(source.shadow_assessment_digest, assessment.assessment_digest)
        self.assertEqual(before, after)
        docket.close()
        remediation.close()
        case.close()

    def test_idempotent_review_replay_fails_closed_after_tampering(self):
        case, remediation, book, assessment = shadow_source()
        docket = SyntheticRemediationShadowReviewDocket(":memory:")
        record = docket.submit_from_book(book, assessment.proposal_id, submitted_at=NOW)
        arguments = {
            "review_id": "synthetic:shadow-review:tampered-replay",
            "reviewer_id": "synthetic:eternian-reviewer:shadow-independent",
            "decision": ShadowReviewDecision.PASS,
            "findings_digest": FINDINGS,
            "reviewed_at": NOW,
        }
        docket.record_eternian_review(record.shadow_id, **arguments)
        docket._connection.execute(
            "UPDATE synthetic_shadow_review_audit SET actor_id = 'synthetic:tampered' "
            "WHERE audit_sequence = 2"
        )
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(record.shadow_id, **arguments)
        docket.close()
        remediation.close()
        case.close()


if __name__ == "__main__":
    unittest.main()
