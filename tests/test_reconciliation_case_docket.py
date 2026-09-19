from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.reconciliation_case_docket import (
    ReconciliationCaseReviewDecision,
    ReconciliationCaseState,
    SyntheticReconciliationCaseDocket,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)
FINDINGS = sha256(b"synthetic reconciliation case review").hexdigest()


def case_report(*, severity: str = "BLOCKED") -> dict[str, object]:
    status = "BLOCKED" if severity == "BLOCKED" else "HUMAN_REVIEW"
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": status,
        "component_snapshot_digests": {
            "payment": sha256(b"payment").hexdigest(),
            "inbox": sha256(b"inbox").hexdigest(),
            "proposals": sha256(b"proposals").hexdigest(),
            "docket": sha256(b"docket").hexdigest(),
        },
        "findings": [
            {
                "code": "SYNTHETIC_TEST_FINDING",
                "severity": severity,
                "subject_id": "synthetic:reconciliation:test",
                "detail": "synthetic mismatch for review",
                "suggested_action": "Eternian should inspect synthetic evidence",
                "automatic_repair_allowed": False,
            }
        ],
        "finding_counts": {
            "WARNING": 1 if severity == "WARNING" else 0,
            "BLOCKED": 1 if severity == "BLOCKED" else 0,
        },
        "read_only_verified": True,
        "synthetic_only": True,
        "automatic_repair_allowed": False,
        "operator_decision_recorded": False,
        "payment_state_changed": False,
        "money_movement_executed": False,
        "production_activation_allowed": False,
    }
    return {**value, "report_digest": canonical_digest(value)}


class ReconciliationCaseDocketTests(unittest.TestCase):
    def test_only_synthetic_sqlite_targets_are_allowed(self):
        SyntheticReconciliationCaseDocket(":memory:").close()
        for target in ("cases.sqlite3", "file:synthetic-cases.sqlite3", "postgres://db"):
            with self.assertRaises(GovernanceRejected):
                SyntheticReconciliationCaseDocket(target)

    def test_blocked_and_warning_reports_become_pending_cases(self):
        for severity in ("BLOCKED", "WARNING"):
            docket = SyntheticReconciliationCaseDocket(":memory:")
            record = docket.submit_report(case_report(severity=severity), submitted_at=NOW)
            self.assertEqual(record.state, ReconciliationCaseState.PENDING_ETERNIAN_REVIEW)
            self.assertEqual(
                record.report_status,
                "BLOCKED" if severity == "BLOCKED" else "HUMAN_REVIEW",
            )
            self.assertFalse(record.automatic_repair_allowed)
            self.assertFalse(record.operator_approval_recorded)
            self.assertFalse(record.execution_allowed)
            self.assertTrue(docket.verify_audit_chain())
            docket.close()

    def test_exact_report_replay_is_idempotent(self):
        docket = SyntheticReconciliationCaseDocket(":memory:")
        report = case_report()
        first = docket.submit_report(report, submitted_at=NOW)
        replay = docket.submit_report(report, submitted_at=NOW)
        self.assertEqual(first, replay)
        self.assertEqual(docket.evidence()["state_counts"]["PENDING_ETERNIAN_REVIEW"], 1)
        docket.close()

    def test_pass_empty_tampered_and_executable_reports_are_rejected(self):
        invalid = []
        passed = case_report()
        passed["status"] = "PASS"
        passed["findings"] = []
        passed["finding_counts"] = {"WARNING": 0, "BLOCKED": 0}
        passed["report_digest"] = canonical_digest(
            {key: value for key, value in passed.items() if key != "report_digest"}
        )
        invalid.append(passed)
        tampered = case_report()
        tampered["finding_counts"] = {"WARNING": 1, "BLOCKED": 0}
        invalid.append(tampered)
        executable = case_report()
        executable["automatic_repair_allowed"] = True
        executable["report_digest"] = canonical_digest(
            {key: value for key, value in executable.items() if key != "report_digest"}
        )
        invalid.append(executable)
        for report in invalid:
            docket = SyntheticReconciliationCaseDocket(":memory:")
            with self.assertRaises(GovernanceRejected):
                docket.submit_report(report, submitted_at=NOW)
            docket.close()

    def test_confirm_stops_at_ready_for_remediation_proposal(self):
        docket = SyntheticReconciliationCaseDocket(":memory:")
        record = docket.submit_report(case_report(), submitted_at=NOW)
        reviewed = docket.record_eternian_review(
            record.case_id,
            review_id="synthetic:reconciliation-review:confirm:1",
            reviewer_id="synthetic:eternian-reviewer:case:1",
            decision=ReconciliationCaseReviewDecision.CONFIRM,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(
            reviewed.state, ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL
        )
        evidence = docket.evidence()
        self.assertFalse(evidence["remediation_proposal_method_present"])
        self.assertFalse(evidence["automatic_repair_method_present"])
        docket.close()

    def test_hold_and_reject_are_terminal_review_results(self):
        for number, decision, expected in (
            (1, ReconciliationCaseReviewDecision.HOLD, ReconciliationCaseState.HELD),
            (2, ReconciliationCaseReviewDecision.REJECT, ReconciliationCaseState.REJECTED),
        ):
            docket = SyntheticReconciliationCaseDocket(":memory:")
            record = docket.submit_report(case_report(), submitted_at=NOW)
            reviewed = docket.record_eternian_review(
                record.case_id,
                review_id=f"synthetic:reconciliation-review:terminal:{number}",
                reviewer_id=f"synthetic:eternian-reviewer:terminal:{number}",
                decision=decision,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            self.assertEqual(reviewed.state, expected)
            with self.assertRaises(GovernanceRejected):
                docket.record_eternian_review(
                    record.case_id,
                    review_id=f"synthetic:reconciliation-review:second:{number}",
                    reviewer_id="synthetic:eternian-reviewer:second",
                    decision=ReconciliationCaseReviewDecision.CONFIRM,
                    findings_digest=FINDINGS,
                    reviewed_at=NOW,
                )
            docket.close()

    def test_review_metadata_time_and_idempotency_are_enforced(self):
        docket = SyntheticReconciliationCaseDocket(":memory:")
        record = docket.submit_report(case_report(), submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.case_id,
                review_id="real-review",
                reviewer_id="synthetic:eternian-reviewer:case",
                decision=ReconciliationCaseReviewDecision.CONFIRM,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
        with self.assertRaises(GovernanceRejected):
            docket.record_eternian_review(
                record.case_id,
                review_id="synthetic:reconciliation-review:backdated",
                reviewer_id="synthetic:eternian-reviewer:case",
                decision=ReconciliationCaseReviewDecision.CONFIRM,
                findings_digest=FINDINGS,
                reviewed_at=NOW - timedelta(seconds=1),
            )
        first = docket.record_eternian_review(
            record.case_id,
            review_id="synthetic:reconciliation-review:idempotent",
            reviewer_id="synthetic:eternian-reviewer:case",
            decision=ReconciliationCaseReviewDecision.CONFIRM,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        replay = docket.record_eternian_review(
            record.case_id,
            review_id="synthetic:reconciliation-review:idempotent",
            reviewer_id="synthetic:eternian-reviewer:case",
            decision=ReconciliationCaseReviewDecision.CONFIRM,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        self.assertEqual(first, replay)
        docket.close()

    def test_restart_preserves_case_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-reconciliation-cases.sqlite3"
            docket = SyntheticReconciliationCaseDocket(path)
            record = docket.submit_report(case_report(), submitted_at=NOW)
            docket.close()
            restarted = SyntheticReconciliationCaseDocket(path)
            self.assertEqual(
                restarted.get(record.case_id).state,
                ReconciliationCaseState.PENDING_ETERNIAN_REVIEW,
            )
            restarted.record_eternian_review(
                record.case_id,
                review_id="synthetic:reconciliation-review:restart",
                reviewer_id="synthetic:eternian-reviewer:restart",
                decision=ReconciliationCaseReviewDecision.CONFIRM,
                findings_digest=FINDINGS,
                reviewed_at=NOW,
            )
            restarted.close()
            final = SyntheticReconciliationCaseDocket(path)
            self.assertEqual(
                final.get(record.case_id).state,
                ReconciliationCaseState.READY_FOR_REMEDIATION_PROPOSAL,
            )
            self.assertTrue(final.verify_record_bindings())
            final.close()

    def test_concurrent_reviews_allow_exactly_one_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-reconciliation-review-race.sqlite3"
            setup = SyntheticReconciliationCaseDocket(path)
            record = setup.submit_report(case_report(), submitted_at=NOW)
            setup.close()
            first = SyntheticReconciliationCaseDocket(path)
            second = SyntheticReconciliationCaseDocket(path)

            def review(item):
                number, docket = item
                try:
                    docket.record_eternian_review(
                        record.case_id,
                        review_id=f"synthetic:reconciliation-review:race:{number}",
                        reviewer_id=f"synthetic:eternian-reviewer:race:{number}",
                        decision=ReconciliationCaseReviewDecision.CONFIRM,
                        findings_digest=FINDINGS,
                        reviewed_at=NOW,
                    )
                    return "accepted"
                except GovernanceRejected:
                    return "rejected"

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(review, ((1, first), (2, second))))
            self.assertEqual(results.count("accepted"), 1)
            self.assertEqual(results.count("rejected"), 1)
            self.assertTrue(first.verify_audit_chain())
            first.close()
            second.close()

    def test_audit_failure_rolls_back_and_tampering_is_detected(self):
        docket = SyntheticReconciliationCaseDocket(":memory:")
        docket._connection.executescript(
            """
            CREATE TRIGGER synthetic_test_fail_case_audit
            BEFORE INSERT ON synthetic_reconciliation_case_audit
            BEGIN SELECT RAISE(ABORT, 'synthetic audit failure'); END;
            """
        )
        report = case_report()
        with self.assertRaises(GovernanceRejected):
            docket.submit_report(report, submitted_at=NOW)
        docket._connection.execute("DROP TRIGGER synthetic_test_fail_case_audit")
        record = docket.submit_report(report, submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_reconciliation_case_audit SET action = 'tampered'"
        )
        self.assertFalse(docket.verify_audit_chain())
        self.assertEqual(
            docket.get(record.case_id).state,
            ReconciliationCaseState.PENDING_ETERNIAN_REVIEW,
        )
        docket.close()

    def test_stored_report_and_review_tampering_break_bindings(self):
        docket = SyntheticReconciliationCaseDocket(":memory:")
        record = docket.submit_report(case_report(), submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_reconciliation_cases SET report_json = '{}' WHERE case_id = ?",
            (record.case_id,),
        )
        with self.assertRaises(GovernanceRejected):
            docket.get(record.case_id)
        self.assertFalse(docket.verify_record_bindings())
        docket.close()

        docket = SyntheticReconciliationCaseDocket(":memory:")
        record = docket.submit_report(case_report(), submitted_at=NOW)
        docket._connection.execute(
            "UPDATE synthetic_reconciliation_cases SET case_id = ? WHERE case_id = ?",
            ("synthetic:reconciliation-case:tampered", record.case_id),
        )
        self.assertFalse(docket.verify_record_bindings())
        docket.close()

        docket = SyntheticReconciliationCaseDocket(":memory:")
        record = docket.submit_report(case_report(), submitted_at=NOW)
        docket.record_eternian_review(
            record.case_id,
            review_id="synthetic:reconciliation-review:binding",
            reviewer_id="synthetic:eternian-reviewer:binding",
            decision=ReconciliationCaseReviewDecision.CONFIRM,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
        docket._connection.execute(
            "UPDATE synthetic_reconciliation_case_reviews SET reviewer_id = ?",
            ("synthetic:eternian-reviewer:tampered",),
        )
        self.assertTrue(docket.verify_audit_chain())
        self.assertFalse(docket.verify_record_bindings())
        docket.close()

    def test_input_report_is_not_mutated(self):
        docket = SyntheticReconciliationCaseDocket(":memory:")
        report = case_report()
        before = deepcopy(report)
        docket.submit_report(report, submitted_at=NOW)
        self.assertEqual(report, before)
        docket.close()


if __name__ == "__main__":
    unittest.main()
