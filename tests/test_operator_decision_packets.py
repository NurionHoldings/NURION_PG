from __future__ import annotations

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.operator_decision_packets import (
    ALLOWED_OPERATOR_DECISIONS,
    PACKET_SCOPE,
    REQUIRED_ACKNOWLEDGEMENTS,
    OperatorGovernanceSnapshot,
    SyntheticOperatorDecisionPacketBook,
)
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
    SyntheticRemediationShadowReviewDocket,
)
from nurion_pg.remediation_synthetic_shadow import (
    SyntheticRemediationShadowBook,
    SyntheticRemediationShadowFixture,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 17, tzinfo=UTC)
FINDINGS = sha256(b"synthetic operator packet findings").hexdigest()


def load_document(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def governance_snapshot() -> OperatorGovernanceSnapshot:
    return OperatorGovernanceSnapshot.from_documents(
        load_document("config/external-blockers.json"),
        load_document("governance/authority-policy.json"),
        load_document("governance/promotion-policy.json"),
    )


def source_report() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "nurion.pg.synthetic-reconciliation-report.v1",
        "observed_at": NOW.isoformat(),
        "status": "BLOCKED",
        "component_snapshot_digests": {
            name: sha256(f"packet:{name}".encode("ascii")).hexdigest()
            for name in ("payment", "inbox", "proposals", "docket")
        },
        "findings": [
            {
                "code": "PROPOSAL_MISSING_DOCKET",
                "severity": "BLOCKED",
                "subject_id": "synthetic:operator-packet-subject",
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


def reviewed_shadow(*, pass_review: bool = True):
    case_docket = SyntheticReconciliationCaseDocket(":memory:")
    case = case_docket.submit_report(source_report(), submitted_at=NOW)
    case_docket.record_eternian_review(
        case.case_id,
        review_id="synthetic:reconciliation-review:operator-packet",
        reviewer_id="synthetic:eternian-reviewer:operator-packet-case",
        decision=ReconciliationCaseReviewDecision.CONFIRM,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    proposal_book = SyntheticRemediationProposalBook()
    proposal = proposal_book.draft(case_docket, case.case_id, now=NOW).proposal
    remediation_docket = SyntheticRemediationReviewDocket(":memory:")
    remediation = remediation_docket.submit_from_book(
        proposal_book, case.case_id, submitted_at=NOW
    )
    remediation_docket.record_eternian_review(
        remediation.proposal_id,
        review_id="synthetic:remediation-review:operator-packet",
        reviewer_id="synthetic:eternian-reviewer:operator-packet-proposal",
        decision=RemediationReviewDecision.PASS,
        findings_digest=FINDINGS,
        reviewed_at=NOW,
    )
    item = proposal.plan_items[0]
    fixture_value = {
        "fixture_id": "synthetic:remediation-shadow-fixture:operator-packet",
        "plan_item_digest": item.item_digest,
        "action_type": item.action_type.value,
        "fixture_seed_digest": sha256(b"operator packet fixture").hexdigest(),
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
        remediation_docket, proposal.proposal_id, (fixture,), evaluated_at=NOW
    )
    shadow_docket = SyntheticRemediationShadowReviewDocket(":memory:")
    record = shadow_docket.submit_from_book(
        shadow_book, proposal.proposal_id, submitted_at=NOW
    )
    if pass_review:
        shadow_docket.record_eternian_review(
            record.shadow_id,
            review_id="synthetic:shadow-review:operator-packet",
            reviewer_id="synthetic:eternian-reviewer:operator-packet-shadow",
            decision=ShadowReviewDecision.PASS,
            findings_digest=FINDINGS,
            reviewed_at=NOW,
        )
    return case_docket, remediation_docket, shadow_docket, record, shadow


class OperatorDecisionPacketTests(unittest.TestCase):
    def test_governance_snapshot_pins_pending_blockers_and_separation(self):
        snapshot = governance_snapshot()
        self.assertEqual(snapshot.release_status, "BLOCKED")
        self.assertEqual(len(snapshot.blocker_ids), 7)
        self.assertTrue(snapshot.governance_digest)

        blockers = load_document("config/external-blockers.json")
        blockers["blockers"][0]["status"] = "CLOSED"
        with self.assertRaises(GovernanceRejected):
            OperatorGovernanceSnapshot.from_documents(
                blockers,
                load_document("governance/authority-policy.json"),
                load_document("governance/promotion-policy.json"),
            )

        authority = load_document("governance/authority-policy.json")
        authority["forbidden_actions"].remove("merge_main")
        with self.assertRaises(GovernanceRejected):
            OperatorGovernanceSnapshot.from_documents(
                load_document("config/external-blockers.json"),
                authority,
                load_document("governance/promotion-policy.json"),
            )

        authority = load_document("governance/authority-policy.json")
        authority["allowed_synthetic_actions"].append("run_live_payment")
        with self.assertRaises(GovernanceRejected):
            OperatorGovernanceSnapshot.from_documents(
                load_document("config/external-blockers.json"),
                authority,
                load_document("governance/promotion-policy.json"),
            )

        promotion = load_document("governance/promotion-policy.json")
        promotion["stages"].remove("ETHERNIAN_REVIEW")
        with self.assertRaises(GovernanceRejected):
            OperatorGovernanceSnapshot.from_documents(
                load_document("config/external-blockers.json"),
                load_document("governance/authority-policy.json"),
                promotion,
            )

    def test_packet_is_non_authorizing_and_source_bound(self):
        case, remediation, docket, record, shadow = reviewed_shadow()
        before = docket.evidence()["report_digest"]
        book = SyntheticOperatorDecisionPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        after = docket.evidence()["report_digest"]
        self.assertEqual(before, after)
        self.assertEqual(packet.shadow_assessment_digest, shadow.assessment_digest)
        self.assertEqual(packet.requested_scope, PACKET_SCOPE)
        self.assertEqual(packet.allowed_decisions, ALLOWED_OPERATOR_DECISIONS)
        self.assertEqual(packet.required_acknowledgements, REQUIRED_ACKNOWLEDGEMENTS)
        self.assertEqual(packet.release_status, "BLOCKED")
        self.assertFalse(packet.operator_decision_recorded)
        self.assertFalse(packet.code_change_allowed)
        self.assertFalse(packet.automatic_application_allowed)
        self.assertFalse(packet.execution_allowed)
        self.assertTrue(book.verify_packet_chain())
        docket.close()
        remediation.close()
        case.close()

    def test_pending_shadow_review_cannot_create_packet(self):
        case, remediation, docket, record, _ = reviewed_shadow(pass_review=False)
        with self.assertRaises(GovernanceRejected):
            SyntheticOperatorDecisionPacketBook().prepare(
                docket, record.shadow_id, governance_snapshot(), generated_at=NOW
            )
        docket.close()
        remediation.close()
        case.close()

    def test_packet_time_cannot_predate_review_or_be_naive(self):
        case, remediation, docket, record, _ = reviewed_shadow()
        book = SyntheticOperatorDecisionPacketBook()
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket,
                record.shadow_id,
                governance_snapshot(),
                generated_at=NOW - timedelta(seconds=1),
            )
        with self.assertRaises(GovernanceRejected):
            book.prepare(
                docket,
                record.shadow_id,
                governance_snapshot(),
                generated_at=datetime(2026, 9, 17),
            )
        docket.close()
        remediation.close()
        case.close()

    def test_packet_expires_without_automatic_freshness_extension(self):
        case, remediation, docket, record, _ = reviewed_shadow()
        book = SyntheticOperatorDecisionPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        self.assertEqual(
            book.current_packet(record.shadow_id, now=packet.valid_until), packet
        )
        with self.assertRaises(GovernanceRejected):
            book.current_packet(
                record.shadow_id, now=packet.valid_until + timedelta(microseconds=1)
            )
        replay = book.prepare(
            docket,
            record.shadow_id,
            governance_snapshot(),
            generated_at=packet.valid_until + timedelta(days=1),
        )
        self.assertEqual(replay, packet)
        with self.assertRaises(GovernanceRejected):
            book.current_packet(record.shadow_id, now=replay.valid_until + timedelta(days=1))
        docket.close()
        remediation.close()
        case.close()

    def test_concurrent_preparation_is_idempotent(self):
        case, remediation, docket, record, _ = reviewed_shadow()
        book = SyntheticOperatorDecisionPacketBook()
        snapshot = governance_snapshot()

        def prepare(_):
            return book.prepare(docket, record.shadow_id, snapshot, generated_at=NOW)

        with ThreadPoolExecutor(max_workers=4) as pool:
            packets = list(pool.map(prepare, range(8)))
        self.assertTrue(all(packet == packets[0] for packet in packets))
        self.assertEqual(len(book.packets), 1)
        docket.close()
        remediation.close()
        case.close()

    def test_changed_governance_snapshot_is_an_idempotency_collision(self):
        case, remediation, docket, record, _ = reviewed_shadow()
        book = SyntheticOperatorDecisionPacketBook()
        snapshot = governance_snapshot()
        book.prepare(docket, record.shadow_id, snapshot, generated_at=NOW)
        object.__setattr__(snapshot, "blocker_ids", snapshot.blocker_ids[:-1])
        with self.assertRaises(GovernanceRejected):
            book.prepare(docket, record.shadow_id, snapshot, generated_at=NOW)
        docket.close()
        remediation.close()
        case.close()

    def test_source_and_packet_tampering_fail_closed(self):
        case, remediation, docket, record, _ = reviewed_shadow()
        book = SyntheticOperatorDecisionPacketBook()
        packet = book.prepare(
            docket, record.shadow_id, governance_snapshot(), generated_at=NOW
        )
        object.__setattr__(packet, "requested_scope", "PRODUCTION")
        self.assertFalse(book.verify_packet_chain())
        with self.assertRaises(GovernanceRejected):
            book.current_packet(record.shadow_id, now=NOW)

        clean = SyntheticOperatorDecisionPacketBook()
        docket._connection.execute(
            "UPDATE synthetic_shadow_review_audit SET actor_id = 'synthetic:tampered'"
        )
        with self.assertRaises(GovernanceRejected):
            clean.prepare(docket, record.shadow_id, governance_snapshot(), generated_at=NOW)
        docket.close()
        remediation.close()
        case.close()

    def test_evidence_exposes_no_decision_change_apply_or_execution(self):
        case, remediation, docket, record, _ = reviewed_shadow()
        book = SyntheticOperatorDecisionPacketBook()
        book.prepare(docket, record.shadow_id, governance_snapshot(), generated_at=NOW)
        evidence = book.evidence()
        self.assertTrue(evidence["packet_chain_valid"])
        self.assertEqual(evidence["maximum_state"], "AWAITING_OPERATOR_DECISION")
        for field in (
            "operator_decision_method_present",
            "code_change_method_present",
            "application_method_present",
            "execution_method_present",
            "external_blocker_close_method_present",
            "money_movement_executed",
            "production_activation_allowed",
        ):
            self.assertFalse(evidence[field])
        docket.close()
        remediation.close()
        case.close()


if __name__ == "__main__":
    unittest.main()
