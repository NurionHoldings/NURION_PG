from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.patch_draft_promotion_decision_intake import (
    SyntheticPatchDraftPromotionDecision,
    SyntheticPatchDraftPromotionDecisionIntake,
)
from nurion_pg.patch_draft_promotion_receipt_ledger import (
    SyntheticPatchDraftPromotionDecisionReceiptLedger,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_plans import (
    PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE,
    PATCH_DRAFT_LIMITED_PROMOTION_SCOPE,
    REQUIRED_LIMITED_PROMOTION_CHECKS,
    REQUIRED_ROLLBACK_TRIGGERS,
    SyntheticPatchDraftLimitedPromotionPlanBook,
)
from tests.test_operator_decision_intake import key_registry
from tests.test_patch_draft_promotion_decision_intake import (
    NOW,
    decision_envelope,
    packet_source,
)
from tests.test_synthetic_patch_draft_shadow_review_docket import close_resources


CANDIDATE_DIGEST = sha256(b"synthetic-limited-promotion-candidate").hexdigest()
COHORT_DIGEST = sha256(b"synthetic-fixture-cohort").hexdigest()


def receipted_source(
    decision: SyntheticPatchDraftPromotionDecision = (
        SyntheticPatchDraftPromotionDecision
        .AUTHORIZE_SYNTHETIC_PATCH_DRAFT_LIMITED_PROMOTION
    ),
):
    resources, docket, record, packet_book, packet = packet_source()
    intake = SyntheticPatchDraftPromotionDecisionIntake(key_registry())
    envelope = decision_envelope(packet, decision=decision)
    intake.assess(packet_book, record.shadow_id, envelope, received_at=NOW)
    ledger = SyntheticPatchDraftPromotionDecisionReceiptLedger(":memory:")
    receipt = ledger.record_from_intake(intake, envelope.envelope_id, recorded_at=NOW)
    return resources, docket, ledger, receipt


def draft(book, ledger, receipt, **overrides):
    values = {
        "candidate_digest": CANDIDATE_DIGEST,
        "cohort_digest": COHORT_DIGEST,
        "synthetic_sample_size": 10,
        "observation_window_seconds": 600,
        "rollback_triggers": REQUIRED_ROLLBACK_TRIGGERS,
        "drafted_at": NOW,
    }
    values.update(overrides)
    return book.draft_from_receipt(ledger, receipt.receipt_id, **values)


class SyntheticPatchDraftLimitedPromotionPlanTests(unittest.TestCase):
    def test_authorized_receipt_creates_metadata_only_bounded_plan(self):
        resources, docket, ledger, receipt = receipted_source()
        plan = draft(
            SyntheticPatchDraftLimitedPromotionPlanBook(), ledger, receipt
        )
        self.assertEqual(plan.state, PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE)
        self.assertEqual(plan.promotion_scope, PATCH_DRAFT_LIMITED_PROMOTION_SCOPE)
        self.assertEqual(plan.required_checks, REQUIRED_LIMITED_PROMOTION_CHECKS)
        self.assertTrue(plan.synthetic_only)
        self.assertTrue(plan.rollback_required)
        self.assertTrue(plan.eternian_review_required)
        self.assertTrue(plan.operator_reconfirmation_required)
        for value in (
            plan.candidate_content_present,
            plan.patch_content_present,
            plan.diff_content_present,
            plan.source_code_changed,
            plan.filesystem_written,
            plan.automatic_application_allowed,
            plan.execution_allowed,
            plan.production_activation_allowed,
        ):
            self.assertFalse(value)
        ledger.close()
        close_resources(resources, docket)

    def test_hold_and_reject_cannot_create_plans(self):
        for decision in (
            SyntheticPatchDraftPromotionDecision.HOLD,
            SyntheticPatchDraftPromotionDecision.REJECT,
        ):
            resources, docket, ledger, receipt = receipted_source(decision)
            with self.assertRaises(GovernanceRejected):
                draft(
                    SyntheticPatchDraftLimitedPromotionPlanBook(), ledger, receipt
                )
            ledger.close()
            close_resources(resources, docket)

    def test_requires_typed_intact_receipt_ledger(self):
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionPlanBook().draft_from_receipt(
                object(),
                "synthetic:patch-draft-promotion-decision-receipt:fake",
                candidate_digest=CANDIDATE_DIGEST,
                cohort_digest=COHORT_DIGEST,
                synthetic_sample_size=10,
                observation_window_seconds=600,
                rollback_triggers=REQUIRED_ROLLBACK_TRIGGERS,
                drafted_at=NOW,
            )
        resources, docket, ledger, receipt = receipted_source()
        ledger._connection.execute(
            "UPDATE synthetic_patch_draft_promotion_receipt_audit "
            "SET audit_digest = ?",
            ("f" * 64,),
        )
        with self.assertRaises(GovernanceRejected):
            draft(SyntheticPatchDraftLimitedPromotionPlanBook(), ledger, receipt)
        ledger.close()
        close_resources(resources, docket)

    def test_digests_limits_and_rollback_triggers_are_strict(self):
        resources, docket, ledger, receipt = receipted_source()
        invalid = (
            {"candidate_digest": "not-a-digest"},
            {"cohort_digest": CANDIDATE_DIGEST},
            {"synthetic_sample_size": 0},
            {"synthetic_sample_size": 101},
            {"synthetic_sample_size": True},
            {"observation_window_seconds": 59},
            {"observation_window_seconds": 3610},
            {"observation_window_seconds": 601},
            {"rollback_triggers": REQUIRED_ROLLBACK_TRIGGERS[:-1]},
            {"rollback_triggers": tuple(reversed(REQUIRED_ROLLBACK_TRIGGERS))},
        )
        for override in invalid:
            with self.assertRaises(GovernanceRejected):
                draft(
                    SyntheticPatchDraftLimitedPromotionPlanBook(),
                    ledger,
                    receipt,
                    **override,
                )
        ledger.close()
        close_resources(resources, docket)

    def test_draft_time_cannot_predate_receipt_or_be_naive(self):
        resources, docket, ledger, receipt = receipted_source()
        for value in (NOW - timedelta(seconds=1), NOW.replace(tzinfo=None)):
            with self.assertRaises(GovernanceRejected):
                draft(
                    SyntheticPatchDraftLimitedPromotionPlanBook(),
                    ledger,
                    receipt,
                    drafted_at=value,
                )
        ledger.close()
        close_resources(resources, docket)

    def test_exact_replay_is_idempotent_and_changed_plan_is_blocked(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftLimitedPromotionPlanBook()
        first = draft(book, ledger, receipt)
        second = draft(book, ledger, receipt, drafted_at=NOW + timedelta(seconds=1))
        self.assertEqual(first, second)
        with self.assertRaises(GovernanceRejected):
            draft(book, ledger, receipt, synthetic_sample_size=11)
        ledger.close()
        close_resources(resources, docket)

    def test_concurrent_replay_records_one_plan(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftLimitedPromotionPlanBook()

        def create(_):
            return draft(book, ledger, receipt)

        with ThreadPoolExecutor(max_workers=4) as pool:
            plans = list(pool.map(create, range(8)))
        self.assertTrue(all(item == plans[0] for item in plans))
        self.assertEqual(len(book.plans), 1)
        self.assertTrue(book.verify_plan_chain())
        ledger.close()
        close_resources(resources, docket)

    def test_source_receipt_is_read_only(self):
        resources, docket, ledger, receipt = receipted_source()
        before = ledger.evidence()["report_digest"]
        draft(SyntheticPatchDraftLimitedPromotionPlanBook(), ledger, receipt)
        self.assertEqual(before, ledger.evidence()["report_digest"])
        ledger.close()
        close_resources(resources, docket)

    def test_plan_and_rehashed_source_tampering_fail_closed(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftLimitedPromotionPlanBook()
        plan = draft(book, ledger, receipt)
        object.__setattr__(plan, "source_receipt_digest", "f" * 64)
        object.__setattr__(plan, "plan_digest", canonical_digest(plan.digest_value()))
        self.assertFalse(book.verify_plan_chain())
        with self.assertRaises(GovernanceRejected):
            draft(book, ledger, receipt)
        ledger.close()
        close_resources(resources, docket)

    def test_evidence_exposes_no_activation_authority(self):
        resources, docket, ledger, receipt = receipted_source()
        book = SyntheticPatchDraftLimitedPromotionPlanBook()
        draft(book, ledger, receipt)
        evidence = book.evidence()
        self.assertTrue(evidence["plan_chain_valid"])
        self.assertTrue(evidence["synthetic_only"])
        self.assertTrue(evidence["rollback_required"])
        self.assertEqual(
            evidence["maximum_state"], PATCH_DRAFT_LIMITED_PROMOTION_PLAN_STATE
        )
        for field in (
            "candidate_content_present",
            "patch_content_present",
            "diff_content_present",
            "source_code_changed",
            "filesystem_written",
            "application_method_present",
            "safety_baseline_relaxation_allowed",
            "execution_method_present",
            "network_access_method_present",
            "personal_data_used",
            "credentials_used",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        ledger.close()
        close_resources(resources, docket)


if __name__ == "__main__":
    unittest.main()
