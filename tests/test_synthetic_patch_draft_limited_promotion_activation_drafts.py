from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_drafts import (
    ACTIVATION_DRAFT_REQUIRED_CHECKS,
    ACTIVATION_DRAFT_SCOPE,
    ACTIVATION_DRAFT_STATE,
    SyntheticPatchDraftLimitedPromotionActivationDraftBook,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_intake import (
    SyntheticPatchDraftLimitedPromotionActivationDecision,
    SyntheticPatchDraftLimitedPromotionActivationIntake,
)
from nurion_pg.synthetic_patch_draft_limited_promotion_activation_receipt_ledger import (
    SyntheticPatchDraftLimitedPromotionActivationReceiptLedger,
)
from tests.test_operator_decision_intake import key_registry
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_patch_draft_limited_promotion_activation_intake import (
    activation_envelope,
    packet_source,
)
from tests.test_synthetic_patch_draft_limited_promotion_activation_review_docket import (
    close_all,
)


def activation_sources(
    decision=(
        SyntheticPatchDraftLimitedPromotionActivationDecision
        .AUTHORIZE_SYNTHETIC_LIMITED_PROMOTION_ACTIVATION
    ),
):
    resources, docket, manifest, packet_book, packet = packet_source()
    envelope = activation_envelope(packet, decision=decision)
    intake = SyntheticPatchDraftLimitedPromotionActivationIntake(key_registry())
    intake.assess(packet_book, manifest.manifest_id, envelope, received_at=NOW)
    ledger = SyntheticPatchDraftLimitedPromotionActivationReceiptLedger(":memory:")
    receipt = ledger.record_from_intake(
        intake, envelope.envelope_id, recorded_at=NOW
    )
    return resources, docket, ledger, packet_book, receipt


def close_sources(resources, docket, ledger):
    ledger.close()
    close_all(resources, docket)


class ActivationDraftTests(unittest.TestCase):
    def test_draft_binds_exact_scope_without_activation(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
        before_ledger = ledger.evidence()["report_digest"]
        before_packet = packet_book.evidence()["report_digest"]
        draft = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        packet = packet_book.packets[0]
        self.assertEqual(before_ledger, ledger.evidence()["report_digest"])
        self.assertEqual(before_packet, packet_book.evidence()["report_digest"])
        self.assertEqual(draft.source_receipt_digest, receipt.receipt_digest())
        self.assertEqual(draft.manifest_digest, packet.manifest_digest)
        self.assertEqual(draft.candidate_digest, packet.candidate_digest)
        self.assertEqual(draft.cohort_digest, packet.cohort_digest)
        self.assertEqual(draft.activation_scope, ACTIVATION_DRAFT_SCOPE)
        self.assertEqual(draft.required_checks, ACTIVATION_DRAFT_REQUIRED_CHECKS)
        self.assertFalse(draft.activation_allowed)
        close_sources(resources, docket, ledger)

    def test_hold_and_reject_receipts_are_blocked(self):
        for decision in (
            SyntheticPatchDraftLimitedPromotionActivationDecision.HOLD,
            SyntheticPatchDraftLimitedPromotionActivationDecision.REJECT,
        ):
            resources, docket, ledger, packet_book, receipt = activation_sources(
                decision
            )
            with self.assertRaises(GovernanceRejected):
                SyntheticPatchDraftLimitedPromotionActivationDraftBook().draft_from_receipt(
                    ledger, receipt.receipt_id, packet_book, drafted_at=NOW
                )
            close_sources(resources, docket, ledger)

    def test_typed_inputs_and_time_fail_closed(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                object(), receipt.receipt_id, packet_book, drafted_at=NOW
            )
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger, receipt.receipt_id, object(), drafted_at=NOW
            )
        for value in (NOW - timedelta(seconds=1), datetime(2026, 9, 17)):
            with self.assertRaises(GovernanceRejected):
                book.draft_from_receipt(
                    ledger, receipt.receipt_id, packet_book, drafted_at=value
                )
        close_sources(resources, docket, ledger)

    def test_exact_replay_is_idempotent(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
        first = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        second = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        self.assertEqual(first, second)
        self.assertEqual(len(book.drafts), 1)
        close_sources(resources, docket, ledger)

    def test_concurrent_drafting_creates_one_draft(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()

        def draft(_):
            return book.draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            drafts = list(pool.map(draft, range(8)))
        self.assertTrue(all(item == drafts[0] for item in drafts))
        self.assertEqual(len(book.drafts), 1)
        close_sources(resources, docket, ledger)

    def test_receipt_tampering_blocks_drafting(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        ledger._connection.execute(
            "UPDATE synthetic_activation_receipts SET assessment_json = '{}'"
        )
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationDraftBook().draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )
        close_sources(resources, docket, ledger)

    def test_packet_tampering_blocks_drafting(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        object.__setattr__(packet_book.packets[0], "manifest_digest", "f" * 64)
        with self.assertRaises(GovernanceRejected):
            SyntheticPatchDraftLimitedPromotionActivationDraftBook().draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )
        close_sources(resources, docket, ledger)

    def test_draft_tampering_breaks_chain(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
        draft = book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        object.__setattr__(draft, "activation_scope", "PRODUCTION")
        self.assertFalse(book.verify_draft_chain())
        close_sources(resources, docket, ledger)

    def test_source_change_during_draft_discards_result(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
        original = ledger.evidence
        calls = 0

        def changing_evidence():
            nonlocal calls
            calls += 1
            result = original()
            if calls > 1:
                result = {**result, "report_digest": "f" * 64}
            return result

        ledger.evidence = changing_evidence
        with self.assertRaises(GovernanceRejected):
            book.draft_from_receipt(
                ledger, receipt.receipt_id, packet_book, drafted_at=NOW
            )
        self.assertEqual(book.drafts, ())
        close_sources(resources, docket, ledger)

    def test_evidence_proves_metadata_only_boundary(self):
        resources, docket, ledger, packet_book, receipt = activation_sources()
        book = SyntheticPatchDraftLimitedPromotionActivationDraftBook()
        book.draft_from_receipt(
            ledger, receipt.receipt_id, packet_book, drafted_at=NOW
        )
        evidence = book.evidence()
        self.assertTrue(evidence["draft_chain_valid"])
        self.assertTrue(evidence["eternian_review_required"])
        self.assertEqual(evidence["maximum_state"], ACTIVATION_DRAFT_STATE)
        for field in (
            "actual_operator_decision_recorded",
            "activation_recording_method_present",
            "candidate_content_present",
            "patch_content_present",
            "diff_content_present",
            "source_code_change_method_present",
            "filesystem_write_method_present",
            "activation_method_present",
            "rollback_execution_method_present",
            "execution_method_present",
            "network_access_method_present",
            "external_blocker_close_method_present",
            "automatic_merge_method_present",
            "automatic_deploy_method_present",
            "personal_data_used",
            "credentials_used",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        close_sources(resources, docket, ledger)


if __name__ == "__main__":
    unittest.main()
