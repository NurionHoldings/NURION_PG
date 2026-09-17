from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from nurion_pg.arkaon.governance import GovernanceRejected, canonical_digest
from nurion_pg.arkaon.regulatory_evidence import (
    EvidenceDisposition,
    RegulatoryClaim,
    RegulatoryEvidence,
    RegulatoryRegistry,
    SourceAuthority,
)


NOW = datetime(2026, 9, 17, tzinfo=UTC)


def evidence(**changes) -> RegulatoryEvidence:
    claims = (
        RegulatoryClaim("registration", "Synthetic registration review is required.", "CURRENT"),
    )
    value = RegulatoryEvidence(
        "REG-001",
        "https://www.fsc.go.kr/example",
        "Synthetic regulator announcement",
        SourceAuthority.REGULATOR_ANNOUNCEMENT,
        "금융위원회",
        "2026-09-01",
        NOW,
        NOW + timedelta(days=30),
        "2026-09-01",
        claims,
        canonical_digest([claim.canonical() for claim in claims]),
        True,
        True,
    )
    return replace(value, **changes)


class RegulatoryEvidenceTests(unittest.TestCase):
    def test_verified_current_official_snapshot_is_drafting_only(self):
        registry = RegulatoryRegistry()
        registry.register(evidence())
        self.assertEqual(
            registry.disposition("REG-001", now=NOW + timedelta(days=1)),
            EvidenceDisposition.DRAFTING_ONLY,
        )
        view = registry.requirement_view("registration", now=NOW + timedelta(days=1))
        self.assertTrue(view["drafting_allowed"])
        self.assertFalse(view["operational_use_allowed"])

    def test_metadata_only_official_source_requires_human_review(self):
        registry = RegulatoryRegistry()
        registry.register(
            evidence(claims=(), claim_snapshot_digest=None, content_capture_complete=False)
        )
        self.assertEqual(
            registry.disposition("REG-001", now=NOW + timedelta(days=1)),
            EvidenceDisposition.HUMAN_REVIEW,
        )

    def test_stale_and_conflicting_evidence_fail_closed(self):
        stale = RegulatoryRegistry()
        stale.register(evidence(revalidate_after=NOW + timedelta(hours=1)))
        self.assertEqual(stale.disposition("REG-001", now=NOW + timedelta(days=1)), EvidenceDisposition.STALE)
        conflict = RegulatoryRegistry()
        conflict.register(evidence(conflicts_with=("REG-002",)))
        self.assertEqual(conflict.disposition("REG-001", now=NOW), EvidenceDisposition.CONFLICT)

    def test_unknown_requirement_and_source_are_blocked(self):
        registry = RegulatoryRegistry()
        self.assertEqual(registry.disposition("missing", now=NOW), EvidenceDisposition.BLOCKED)
        self.assertFalse(registry.requirement_view("missing", now=NOW)["drafting_allowed"])

    def test_nonofficial_host_cannot_be_marked_official(self):
        with self.assertRaises(GovernanceRejected):
            evidence(url="https://example.com/document")

    def test_digest_mismatch_instruction_authority_and_operational_use_are_rejected(self):
        with self.assertRaises(GovernanceRejected):
            evidence(claim_snapshot_digest="0" * 64)
        with self.assertRaises(GovernanceRejected):
            evidence(instruction_authority=True)
        with self.assertRaises(GovernanceRejected):
            evidence(operational_use_allowed=True)

    def test_report_is_deterministic_and_cannot_activate_production(self):
        registry = RegulatoryRegistry()
        registry.register(evidence())
        first = registry.report(now=NOW)
        second = registry.report(now=NOW)
        self.assertEqual(first, second)
        self.assertFalse(first["production_activation_allowed"])
        self.assertFalse(first["automatic_registry_update_allowed"])


if __name__ == "__main__":
    unittest.main()

