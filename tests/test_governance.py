from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from nurion_pg.arkaon.governance import (
    Action,
    ArkaonGovernor,
    AuthorityDecision,
    CAPABILITY_DOMAINS,
    Candidate,
    CapabilityProfile,
    EvidenceChain,
    EvidenceEvent,
    EvidenceSource,
    GovernanceRejected,
    PromotionStage,
)


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def profile() -> CapabilityProfile:
    return CapabilityProfile("NURION_PG_ARKAON_SYNTHETIC", "0.1.0", CAPABILITY_DOMAINS)


def source(**changes) -> EvidenceSource:
    now = datetime(2026, 9, 17, tzinfo=UTC)
    value = EvidenceSource(
        "E-001",
        "https://official.example.invalid/document",
        "Synthetic official evidence",
        now - timedelta(days=1),
        now,
        now + timedelta(days=30),
        digest("official-document"),
        True,
    )
    return replace(value, **changes)


def candidate() -> Candidate:
    return Candidate(
        "C-001", digest("baseline"), digest("proposal"), digest("rollback"), ("E-001",)
    )


class GovernanceTests(unittest.TestCase):
    def test_profile_is_complete_and_synthetic_only(self):
        value = profile()
        self.assertEqual(value.domains, CAPABILITY_DOMAINS)
        self.assertEqual(value.production_status, "BLOCKED")

    def test_profile_cannot_self_activate_or_self_modify(self):
        with self.assertRaises(GovernanceRejected):
            replace(profile(), production_status="ACTIVE")
        with self.assertRaises(GovernanceRejected):
            replace(profile(), self_modification_allowed=True)

    def test_money_identity_contract_and_delivery_actions_are_blocked(self):
        governor = ArkaonGovernor(profile())
        for action in ArkaonGovernor._BLOCKED_ACTIONS:
            self.assertEqual(governor.decide(action), AuthorityDecision.BLOCKED)

    def test_synthetic_actions_are_allowed_without_operational_authority(self):
        governor = ArkaonGovernor(profile())
        for action in ArkaonGovernor._SYNTHETIC_ACTIONS:
            self.assertEqual(governor.decide(action), AuthorityDecision.ALLOW_SYNTHETIC)
        self.assertEqual(
            governor.decide(Action.REQUEST_ETHERNIAN_REVIEW),
            AuthorityDecision.REQUIRE_ETHERNIAN_REVIEW,
        )

    def test_internet_evidence_cannot_become_instruction_authority(self):
        with self.assertRaises(GovernanceRejected):
            source(instruction_authority=True)

    def test_non_https_stale_and_malformed_evidence_are_rejected(self):
        with self.assertRaises(GovernanceRejected):
            source(url="http://official.example.invalid")
        with self.assertRaises(GovernanceRejected):
            source(content_digest="bad")
        with self.assertRaises(GovernanceRejected):
            source(valid_until=datetime(2026, 9, 17, tzinfo=UTC))

    def test_duplicate_evidence_identity_is_rejected(self):
        governor = ArkaonGovernor(profile())
        governor.register_source(source())
        with self.assertRaises(GovernanceRejected):
            governor.register_source(source())

    def test_proposal_requires_current_verified_nonconflicting_evidence(self):
        now = datetime(2026, 9, 18, tzinfo=UTC)
        for unsafe in (
            source(official_verified=False),
            source(conflicting_evidence=("E-OTHER",)),
            source(valid_until=datetime(2026, 9, 17, 1, tzinfo=UTC)),
        ):
            governor = ArkaonGovernor(profile())
            governor.register_source(unsafe)
            with self.assertRaises(GovernanceRejected):
                governor.propose(candidate(), now=now)

    def test_stage_order_is_fail_closed(self):
        governor = ArkaonGovernor(profile())
        value = candidate()
        with self.assertRaises(GovernanceRejected):
            governor.record_synthetic_shadow(value, {"passed": True})
        governor.register_source(source())
        governor.propose(value, now=datetime(2026, 9, 18, tzinfo=UTC))
        with self.assertRaises(GovernanceRejected):
            governor.record_ethernian_review(value, digest("review"))

    def test_synthetic_shadow_cannot_activate_production(self):
        governor = ArkaonGovernor(profile())
        value = candidate()
        governor.register_source(source())
        governor.propose(value, now=datetime(2026, 9, 18, tzinfo=UTC))
        with self.assertRaises(GovernanceRejected):
            governor.record_synthetic_shadow(
                value,
                {"passed": True, "synthetic_only": True, "production_activation_allowed": True},
            )

    def test_reviewer_and_operator_approval_are_separate(self):
        governor = ArkaonGovernor(profile())
        value = candidate()
        governor.register_source(source())
        governor.propose(value, now=datetime(2026, 9, 18, tzinfo=UTC))
        governor.record_synthetic_shadow(
            value,
            {"passed": True, "synthetic_only": True, "production_activation_allowed": False},
        )
        review = digest("ethernian-review")
        governor.record_ethernian_review(value, review)
        with self.assertRaises(GovernanceRejected):
            governor.record_operator_approval(value, review)
        governor.record_operator_approval(value, digest("operator-approval"))
        self.assertEqual(value.stage, PromotionStage.OPERATOR_APPROVED)

    def test_limited_promotion_is_synthetic_only_and_rollback_is_recorded(self):
        governor = ArkaonGovernor(profile())
        value = candidate()
        governor.register_source(source())
        governor.propose(value, now=datetime(2026, 9, 18, tzinfo=UTC))
        governor.record_synthetic_shadow(
            value,
            {"passed": True, "synthetic_only": True, "production_activation_allowed": False},
        )
        governor.record_ethernian_review(value, digest("ethernian-review"))
        governor.record_operator_approval(value, digest("operator-approval"))
        with self.assertRaises(GovernanceRejected):
            governor.limited_promote(value, ("production:payments",))
        governor.limited_promote(value, ("synthetic:payment-state-machine",))
        governor.rollback(value)
        self.assertEqual(value.stage, PromotionStage.ROLLED_BACK)
        self.assertTrue(governor.chain.verify())

    def test_evidence_chain_detects_tampering(self):
        chain = EvidenceChain()
        first = chain.append("A", {"value": 1})
        chain.append("B", {"value": 2})
        self.assertTrue(chain.verify())
        chain.events[0] = EvidenceEvent(
            first.sequence, "TAMPERED", first.payload_digest, first.previous_digest, first.event_digest
        )
        self.assertFalse(chain.verify())


if __name__ == "__main__":
    unittest.main()

