from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_feasibility_decision_portfolio import DecisionPortfolio
from nurion_pg.synthetic_decision_portfolio_briefing import (
    BriefingPacket, MAXIMUM_STATE, SyntheticDecisionPortfolioBriefing,
)


def digest(value): return sha256(value.encode()).hexdigest()


def source(name="one", status="SYNTHETIC_DECISION_PORTFOLIO_RECORDED", identity=None):
    identity = identity or name
    values = dict(portfolio_id=f"synthetic:decision-portfolio:{name}",
        curator=f"synthetic:portfolio-curator:curator-{identity}", requested_limit=2,
        docket_ids=(f"synthetic:feasibility-portfolio:{name}-a", f"synthetic:feasibility-portfolio:{name}-b"),
        decision_counts=(("HOLD", 0), ("OBSERVE", 1), ("REASSESS", 1)),
        recorded_count=2, held_count=0, status=status, version=3,
        previous_digest=digest(f"previous:{name}"))
    return DecisionPortfolio(**values, digest=SyntheticDecisionPortfolioBriefing._source_digest(
        DecisionPortfolio(**values, digest="placeholder")))


class DecisionPortfolioBriefingTests(unittest.TestCase):
    def populated(self, count=3):
        service = SyntheticDecisionPortfolioBriefing()
        for i in range(count): service.intake(source(f"{i:02}"))
        return service

    def drafted(self, count=3, author="author"):
        service = self.populated(count)
        row = service.author("synthetic:portfolio-briefing:one",
                             f"synthetic:briefing-author:{author}", count)
        return service, row

    def reviewed(self, accepted=True):
        service, row = self.drafted()
        row = service.review("synthetic:briefing-review:one", row.briefing_id, row.version,
            "synthetic:briefing-reviewer:reviewer", accepted, digest("finding"))
        return service, row

    def recorded(self):
        service, row = self.reviewed()
        review = service.review_artifact("synthetic:briefing-review:one")
        row = service.record("synthetic:briefing-receipt:one", row.briefing_id, row.version,
            review.digest, "synthetic:briefing-verifier:verifier")
        return service, row

    def test_exact_control_matrix(self):
        e = SyntheticDecisionPortfolioBriefing().evidence()
        self.assertEqual((e["control_count"], e["workstream_count"]), (200, 8))
        self.assertTrue(e["control_matrix_valid"])

    def test_typed_integral_source_required(self):
        service = SyntheticDecisionPortfolioBriefing()
        with self.assertRaises(GovernanceRejected): service.intake(object())
        with self.assertRaises(GovernanceRejected): service.intake(replace(source(), digest=digest("fake")))

    def test_self_rehashed_semantic_forgery_rejected(self):
        row = source(); values = row.__dict__ | {"recorded_count": 99}
        fake = DecisionPortfolio(**(values | {"digest": "placeholder"}))
        values["digest"] = SyntheticDecisionPortfolioBriefing._source_digest(fake)
        with self.assertRaises(GovernanceRejected): SyntheticDecisionPortfolioBriefing().intake(DecisionPortfolio(**values))

    def test_self_rehashed_invalid_counts_and_limit_are_rejected(self):
        for changes in (
            {"requested_limit": 0},
            {"decision_counts": (("HOLD", -1), ("OBSERVE", 2), ("REASSESS", 1))},
            {"recorded_count": True, "held_count": 1},
        ):
            values = source().__dict__ | changes
            fake = DecisionPortfolio(**(values | {"digest": "placeholder"}))
            values["digest"] = SyntheticDecisionPortfolioBriefing._source_digest(fake)
            with self.assertRaises(GovernanceRejected):
                SyntheticDecisionPortfolioBriefing().intake(DecisionPortfolio(**values))

    def test_source_idempotency_and_conflict(self):
        service = SyntheticDecisionPortfolioBriefing(); row = source()
        self.assertIs(service.intake(row), service.intake(row))
        with self.assertRaises(GovernanceRejected): service.intake(replace(row, status="HELD"))

    def test_bounded_batch_and_unique_membership(self):
        service = self.populated(25)
        a = service.author("synthetic:portfolio-briefing:a", "synthetic:briefing-author:a", 20)
        b = service.author("synthetic:portfolio-briefing:b", "synthetic:briefing-author:b", 20)
        self.assertEqual((len(a.source_ids), len(b.source_ids)), (20, 5))
        self.assertFalse(set(a.source_ids) & set(b.source_ids))

    def test_over_limit_and_empty_fail_closed(self):
        service = SyntheticDecisionPortfolioBriefing()
        with self.assertRaises(GovernanceRejected): service.author("synthetic:portfolio-briefing:x", "synthetic:briefing-author:x", 1)
        service.intake(source())
        with self.assertRaises(GovernanceRejected): service.author("synthetic:portfolio-briefing:x", "synthetic:briefing-author:x", 21)

    def test_fixed_plain_language_and_internal_links(self):
        _, row = self.drafted()
        self.assertTrue(all(text.endswith("건") for text in row.plain_status + row.plain_decisions))
        self.assertTrue(all(link.startswith("evidence:") and "http" not in link for link in row.evidence_link_ids))

    def test_explicit_operator_boundary(self):
        _, row = self.recorded()
        self.assertTrue(row.operator_action_required)
        self.assertFalse(row.approval_recorded)
        self.assertEqual(row.status, MAXIMUM_STATE)

    def test_author_role_independence(self):
        service = SyntheticDecisionPortfolioBriefing(); service.intake(source(identity="same"))
        with self.assertRaises(GovernanceRejected): service.author(
            "synthetic:portfolio-briefing:x", "synthetic:briefing-author:curator-same", 1)

    def test_reviewer_and_verifier_role_independence(self):
        service, row = self.drafted(author="same")
        with self.assertRaises(GovernanceRejected): service.review(
            "synthetic:briefing-review:x", row.briefing_id, row.version,
            "synthetic:briefing-reviewer:same", True, digest("f"))
        service, row = self.reviewed(); review = service.review_artifact("synthetic:briefing-review:one")
        with self.assertRaises(GovernanceRejected): service.record(
            "synthetic:briefing-receipt:x", row.briefing_id, row.version,
            review.digest, "synthetic:briefing-verifier:reviewer")

    def test_review_idempotency_conflict_and_hold(self):
        service, row = self.drafted(); args = ("synthetic:briefing-review:x", row.briefing_id,
            row.version, "synthetic:briefing-reviewer:r", False, digest("finding"))
        result = service.review(*args); self.assertIs(result, service.review(*args))
        self.assertEqual(result.status, "HELD")
        with self.assertRaises(GovernanceRejected): service.review(*args[:-1], digest("other"))

    def test_receipt_idempotency_conflict_replay(self):
        service, row = self.reviewed(); review = service.review_artifact("synthetic:briefing-review:one")
        args = ("synthetic:briefing-receipt:x", row.briefing_id, row.version, review.digest,
                "synthetic:briefing-verifier:v")
        result = service.record(*args); self.assertIs(result, service.record(*args))
        with self.assertRaises(GovernanceRejected): service.record(*args[:-1], "synthetic:briefing-verifier:z")

    def test_concurrent_exact_record_converges(self):
        service, row = self.reviewed(); review = service.review_artifact("synthetic:briefing-review:one")
        args = ("synthetic:briefing-receipt:x", row.briefing_id, row.version, review.digest,
                "synthetic:briefing-verifier:v")
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: service.record(*args), range(24)))
        self.assertEqual(len({row.digest for row in rows}), 1)

    def test_independent_auditor_can_hold(self):
        service, row = self.recorded()
        row = service.audit_hold(row.briefing_id, row.version,
            "synthetic:briefing-auditor:auditor", digest("finding"))
        self.assertEqual(row.status, "HELD")
        self.assertTrue(service.evidence()["integrity_valid"])

    def test_auditor_role_collision_rejected(self):
        service, row = self.recorded()
        with self.assertRaises(GovernanceRejected): service.audit_hold(row.briefing_id, row.version,
            "synthetic:briefing-auditor:verifier", digest("finding"))

    def test_distribution_tamper_detected(self):
        service, row = self.drafted(); service._packets[row.briefing_id] = replace(row, status_counts=(("HELD", 99),))
        self.assertFalse(service.evidence()["briefing_integrity_valid"])

    def test_plain_text_tamper_detected_by_digest(self):
        service, row = self.drafted(); service._packets[row.briefing_id] = replace(row, plain_status=("승인 완료",))
        self.assertFalse(service.evidence()["briefing_integrity_valid"])

    def test_self_rehashed_plain_text_semantic_forgery_detected(self):
        service, row = self.drafted()
        values = row.__dict__ | {"plain_status": ("승인 완료",)}
        values["digest"] = service._packet_digest(**{k: v for k, v in values.items() if k != "digest"})
        service._packets[row.briefing_id] = BriefingPacket(**values)
        self.assertFalse(service.evidence()["briefing_integrity_valid"])

    def test_source_trace_tamper_detected(self):
        service, _ = self.drafted(); key = next(iter(service._sources))
        service._sources[key] = replace(service._sources[key], related_trace_digest=digest("fake"))
        self.assertFalse(service.evidence()["source_integrity_valid"])

    def test_event_and_artifact_tamper_detected(self):
        service, _ = self.reviewed(); service._events[-1]["action"] = "APPROVED"
        self.assertFalse(service.evidence()["append_only_chain_valid"])
        service, _ = self.reviewed(); key = next(iter(service._reviews))
        service._reviews[key] = replace(service._reviews[key], accepted=False)
        self.assertFalse(service.evidence()["artifact_integrity_valid"])

    def test_rehashed_event_attachment_tamper_detected(self):
        from nurion_pg.arkaon.governance import canonical_digest
        service, _ = self.reviewed(); event = service._events[-1]
        event["attachment_digest"] = digest("substituted")
        payload = {key: event[key] for key in ("sequence", "action", "briefing_digest",
            "attachment_digest", "previous_digest")}
        event["digest"] = canonical_digest(payload)
        self.assertFalse(service.evidence()["append_only_chain_valid"])

    def test_rehashed_hold_provenance_tamper_detected(self):
        from nurion_pg.arkaon.governance import canonical_digest
        service, _ = self.reviewed(False); hold = service._holds[0]
        hold["actor"] = "synthetic:briefing-reviewer:impostor"
        payload = {key: hold[key] for key in ("sequence", "briefing_id", "actor", "reason",
            "briefing_digest", "attachment_digest", "previous_digest")}
        hold["digest"] = canonical_digest(payload)
        self.assertFalse(service.evidence()["append_only_chain_valid"])

    def test_control_gap_is_capability_failure(self):
        import nurion_pg.synthetic_decision_portfolio_briefing as module
        with patch.object(module, "WORKSTREAMS", module.WORKSTREAMS[:-1]):
            evidence = SyntheticDecisionPortfolioBriefing().evidence()
        self.assertFalse(evidence["capability_ready"])
        self.assertIn("control_matrix", evidence["capability_gap_evidence"]["gaps"])

    def test_inert_evidence_contract(self):
        e = SyntheticDecisionPortfolioBriefing().evidence()
        self.assertTrue(e["fixed_template"] and not e["free_prompt_generation"])
        self.assertEqual((e["external_calls"], e["external_url_calls"], e["ledger_writes"]), (0,0,0))


if __name__ == "__main__": unittest.main()
