from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch

from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_feasibility_decision_docket import (
    DocketRecord, MAXIMUM_STATE as SOURCE_RECORDED,
    SyntheticFeasibilityDecisionDocket,
)
from nurion_pg.synthetic_feasibility_decision_portfolio import (
    DECISIONS, MAX_PORTFOLIO_BATCH, MAXIMUM_STATE,
    SyntheticFeasibilityDecisionPortfolio,
)


def digest(value): return sha256(value.encode()).hexdigest()


def source(name="one", status=SOURCE_RECORDED, decision="OBSERVE", identity=None):
    identity = identity or name
    values = dict(portfolio_id=f"synthetic:feasibility-portfolio:{name}",
        portfolio_digest=digest(f"upstream:{name}"), source_version=1, member_count=2,
        observer=f"synthetic:portfolio-observer:observer-{identity}", status=status,
        version=5, analyst=f"synthetic:docket-analyst:analyst-{identity}",
        decision=decision, hold_reason="REVIEW_REJECTED" if status == "HELD" else None,
        previous_digest=digest(f"previous:{name}"))
    return DocketRecord(**values, digest=SyntheticFeasibilityDecisionDocket._record_digest(
        values["portfolio_id"], values["portfolio_digest"], values["source_version"],
        values["member_count"], values["observer"], values["status"], values["version"],
        values["analyst"], values["decision"], values["hold_reason"],
        values["previous_digest"]))


class FeasibilityDecisionPortfolioTests(unittest.TestCase):
    def populated(self, count=3):
        service = SyntheticFeasibilityDecisionPortfolio()
        decisions = sorted(DECISIONS)
        for index in range(count):
            service.intake(source(f"{index:02}", "HELD" if index == 1 else SOURCE_RECORDED,
                                  decisions[index % len(decisions)]))
        return service

    def curated(self, count=3, curator="curator"):
        service = self.populated(count)
        row = service.curate("synthetic:decision-portfolio:one",
                             f"synthetic:portfolio-curator:{curator}", count)
        return service, row

    def reviewed(self, accepted=True, curator="curator", reviewer="reviewer"):
        service, row = self.curated(curator=curator)
        row = service.review("synthetic:portfolio-review:one", row.portfolio_id,
            row.version, f"synthetic:portfolio-reviewer:{reviewer}", accepted,
            digest("finding"))
        return service, row

    def recorded(self, verifier="verifier"):
        service, row = self.reviewed()
        review = service.review_artifact("synthetic:portfolio-review:one")
        row = service.record("synthetic:portfolio-receipt:one", row.portfolio_id,
            row.version, review.digest, f"synthetic:portfolio-verifier:{verifier}")
        return service, row

    def test_control_matrix_exactly_200(self):
        evidence = SyntheticFeasibilityDecisionPortfolio().evidence()
        self.assertEqual((evidence["control_count"], evidence["workstream_count"]), (200, 8))
        self.assertTrue(evidence["exactly_25_controls_per_workstream"])

    def test_typed_terminal_source_is_required(self):
        service = SyntheticFeasibilityDecisionPortfolio()
        with self.assertRaises(GovernanceRejected): service.intake(object())
        with self.assertRaises(GovernanceRejected): service.intake(replace(source(), status="DOCKET_REVIEWED"))

    def test_source_digest_semantics_and_namespace_are_verified(self):
        service = SyntheticFeasibilityDecisionPortfolio()
        with self.assertRaises(GovernanceRejected): service.intake(replace(source(), digest=digest("fake")))
        row = source(); values = row.__dict__ | {"portfolio_id": "real:portfolio:x"}
        values["digest"] = SyntheticFeasibilityDecisionDocket._record_digest(
            values["portfolio_id"], values["portfolio_digest"], values["source_version"],
            values["member_count"], values["observer"], values["status"], values["version"],
            values["analyst"], values["decision"], values["hold_reason"], values["previous_digest"])
        with self.assertRaises(GovernanceRejected): service.intake(DocketRecord(**values))

    def test_self_rehashed_source_semantic_forgery_is_rejected(self):
        for changes in (
            {"source_version": 2}, {"member_count": 21},
            {"hold_reason": "UNKNOWN", "status": "HELD"},
            {"analyst": "synthetic:docket-analyst:observer-one"},
        ):
            values = source().__dict__ | changes
            values["digest"] = SyntheticFeasibilityDecisionDocket._record_digest(
                values["portfolio_id"], values["portfolio_digest"], values["source_version"],
                values["member_count"], values["observer"], values["status"], values["version"],
                values["analyst"], values["decision"], values["hold_reason"],
                values["previous_digest"])
            with self.assertRaises(GovernanceRejected):
                SyntheticFeasibilityDecisionPortfolio().intake(DocketRecord(**values))

    def test_held_and_recorded_semantics_are_distinct(self):
        service = SyntheticFeasibilityDecisionPortfolio()
        with self.assertRaises(GovernanceRejected): service.intake(replace(source(status="HELD"), hold_reason=None))
        with self.assertRaises(GovernanceRejected): service.intake(replace(source(), hold_reason="REVIEW_REJECTED"))

    def test_source_intake_idempotency_and_conflict(self):
        service = SyntheticFeasibilityDecisionPortfolio(); row = source()
        first = service.intake(row); self.assertIs(first, service.intake(row))
        changed = source(decision="HOLD")
        with self.assertRaises(GovernanceRejected): service.intake(changed)

    def test_portfolio_cap_distribution_and_state_counts(self):
        service = self.populated(22)
        row = service.curate("synthetic:decision-portfolio:cap",
            "synthetic:portfolio-curator:c", MAX_PORTFOLIO_BATCH)
        self.assertEqual(len(row.docket_ids), 20)
        self.assertEqual(sum(dict(row.decision_counts).values()), 20)
        self.assertEqual(row.recorded_count + row.held_count, 20)

    def test_empty_and_over_limit_portfolios_fail_closed(self):
        service = SyntheticFeasibilityDecisionPortfolio()
        with self.assertRaises(GovernanceRejected): service.curate(
            "synthetic:decision-portfolio:x", "synthetic:portfolio-curator:c", 1)
        service.intake(source())
        with self.assertRaises(GovernanceRejected): service.curate(
            "synthetic:decision-portfolio:x", "synthetic:portfolio-curator:c", 21)

    def test_cross_portfolio_membership_is_unique(self):
        service = self.populated(5)
        a = service.curate("synthetic:decision-portfolio:a", "synthetic:portfolio-curator:a", 3)
        b = service.curate("synthetic:decision-portfolio:b", "synthetic:portfolio-curator:b", 3)
        self.assertFalse(set(a.docket_ids) & set(b.docket_ids))

    def test_portfolio_idempotency_and_conflict(self):
        service, row = self.curated()
        self.assertIs(row, service.curate(row.portfolio_id, row.curator, 3))
        with self.assertRaises(GovernanceRejected): service.curate(row.portfolio_id, row.curator, 2)

    def test_concurrent_portfolios_do_not_overlap(self):
        service = self.populated(40)
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda name: service.curate(
                f"synthetic:decision-portfolio:{name}",
                f"synthetic:portfolio-curator:{name}", 20), ("a", "b")))
        self.assertEqual(len(set(rows[0].docket_ids + rows[1].docket_ids)), 40)

    def test_curator_is_independent_from_upstream_roles(self):
        for identity in ("observer-same", "analyst-same"):
            service = SyntheticFeasibilityDecisionPortfolio(); service.intake(source(identity="same"))
            with self.assertRaises(GovernanceRejected): service.curate(
                "synthetic:decision-portfolio:x", f"synthetic:portfolio-curator:{identity.split('-')[0]}-same", 1)

    def test_reviewer_is_independent(self):
        service, row = self.curated(curator="same")
        with self.assertRaises(GovernanceRejected): service.review(
            "synthetic:portfolio-review:x", row.portfolio_id, row.version,
            "synthetic:portfolio-reviewer:same", True, digest("finding"))

    def test_downstream_roles_are_independent_from_upstream_roles(self):
        for role in ("reviewer", "verifier", "auditor"):
            service, row = self.curated()
            upstream_identity = "observer-00"
            if role == "reviewer":
                with self.assertRaises(GovernanceRejected): service.review(
                    "synthetic:portfolio-review:x", row.portfolio_id, row.version,
                    f"synthetic:portfolio-reviewer:{upstream_identity}", True, digest("finding"))
                continue
            row = service.review("synthetic:portfolio-review:x", row.portfolio_id, row.version,
                "synthetic:portfolio-reviewer:r", True, digest("finding"))
            review = service.review_artifact("synthetic:portfolio-review:x")
            if role == "verifier":
                with self.assertRaises(GovernanceRejected): service.record(
                    "synthetic:portfolio-receipt:x", row.portfolio_id, row.version,
                    review.digest, f"synthetic:portfolio-verifier:{upstream_identity}")
            else:
                with self.assertRaises(GovernanceRejected): service.audit_hold(
                    row.portfolio_id, row.version,
                    f"synthetic:portfolio-auditor:{upstream_identity}", digest("audit"))

    def test_review_idempotency_conflict_and_stale_version(self):
        service, row = self.curated()
        args = ("synthetic:portfolio-review:x", row.portfolio_id, row.version,
                "synthetic:portfolio-reviewer:r", True, digest("finding"))
        result = service.review(*args); self.assertIs(result, service.review(*args))
        with self.assertRaises(GovernanceRejected): service.review(*args[:-1], digest("other"))

    def test_rejected_review_creates_append_only_hold(self):
        service, row = self.reviewed(False)
        self.assertEqual(row.status, "HELD")
        self.assertTrue(service.evidence()["hold_chain_valid"])

    def test_receipt_is_inert_and_maximum_state_bounded(self):
        service, row = self.recorded()
        self.assertEqual(row.status, MAXIMUM_STATE)
        evidence = service.evidence()
        self.assertTrue(evidence["non_authorizing"] and evidence["non_executable"])
        self.assertEqual((evidence["external_calls"], evidence["ledger_writes"]), (0, 0))

    def test_verifier_is_independent(self):
        for identity in ("curator", "reviewer"):
            service, row = self.reviewed(curator="curator", reviewer="reviewer")
            review = service.review_artifact("synthetic:portfolio-review:one")
            with self.assertRaises(GovernanceRejected): service.record(
                "synthetic:portfolio-receipt:x", row.portfolio_id, row.version,
                review.digest, f"synthetic:portfolio-verifier:{identity}")

    def test_receipt_idempotency_conflict_and_replay(self):
        service, row = self.reviewed(); review = service.review_artifact("synthetic:portfolio-review:one")
        args = ("synthetic:portfolio-receipt:x", row.portfolio_id, row.version,
                review.digest, "synthetic:portfolio-verifier:v")
        result = service.record(*args); self.assertIs(result, service.record(*args))
        with self.assertRaises(GovernanceRejected): service.record(*args[:-1], "synthetic:portfolio-verifier:z")

    def test_concurrent_exact_receipt_converges(self):
        service, row = self.reviewed(); review = service.review_artifact("synthetic:portfolio-review:one")
        args = ("synthetic:portfolio-receipt:x", row.portfolio_id, row.version,
                review.digest, "synthetic:portfolio-verifier:v")
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(lambda _: service.record(*args), range(32)))
        self.assertEqual(len({item.digest for item in rows}), 1)

    def test_auditor_is_independent_of_all_portfolio_roles(self):
        for identity in ("curator", "reviewer", "verifier"):
            service, row = self.recorded(verifier="verifier")
            with self.assertRaises(GovernanceRejected): service.audit_hold(
                row.portfolio_id, row.version, f"synthetic:portfolio-auditor:{identity}", digest("finding"))

    def test_independent_auditor_can_hold_recorded_portfolio(self):
        service, row = self.recorded()
        row = service.audit_hold(row.portfolio_id, row.version,
            "synthetic:portfolio-auditor:auditor", digest("finding"))
        self.assertEqual(row.status, "HELD")
        self.assertTrue(service.evidence()["integrity_valid"])

    def test_decision_aggregate_tamper_is_detected(self):
        service, row = self.curated()
        service._portfolios[row.portfolio_id] = replace(row,
            decision_counts=(("HOLD", 99), ("OBSERVE", 0), ("REASSESS", 0)))
        self.assertFalse(service.evidence()["portfolio_integrity_valid"])

    def test_source_semantic_tamper_is_detected(self):
        service, _ = self.curated(); key = next(iter(service._sources))
        service._sources[key] = replace(service._sources[key], decision="APPROVE")
        self.assertFalse(service.evidence()["source_integrity_valid"])

    def test_membership_replay_tamper_is_detected(self):
        service, row = self.curated(); service._members[row.docket_ids[0]] = "synthetic:decision-portfolio:other"
        self.assertFalse(service.evidence()["portfolio_integrity_valid"])

    def test_event_and_review_tamper_are_detected(self):
        service, _ = self.reviewed(); service._events[-1]["action"] = "APPROVED"
        self.assertFalse(service.evidence()["event_chain_valid"])
        service, _ = self.reviewed(); key = next(iter(service._reviews))
        service._reviews[key] = replace(service._reviews[key], accepted=False)
        self.assertFalse(service.evidence()["artifact_integrity_valid"])

    def test_rehashed_hold_semantic_tamper_is_detected(self):
        from nurion_pg.arkaon.governance import canonical_digest
        service, _ = self.reviewed(False)
        hold = service._holds[0]
        hold["reason"] = "INVENTED"
        payload = {key: hold[key] for key in ("sequence", "portfolio_id", "actor", "reason",
            "portfolio_digest", "attachment_digest", "previous_digest")}
        hold["digest"] = canonical_digest(payload)
        self.assertFalse(service.evidence()["hold_chain_valid"])

    def test_control_matrix_gap_is_capability_failure(self):
        import nurion_pg.synthetic_feasibility_decision_portfolio as module
        broken = module.WORKSTREAMS[:-1] + ((2877, 2900, "BROKEN"),)
        with patch.object(module, "WORKSTREAMS", broken):
            evidence = SyntheticFeasibilityDecisionPortfolio().evidence()
        self.assertFalse(evidence["control_matrix_valid"])
        self.assertIn("control_matrix", evidence["capability_gap_evidence"]["gaps"])

    def test_capability_gap_evidence_fails_closed(self):
        service, row = self.curated(); service._members.pop(row.docket_ids[0])
        evidence = service.evidence()
        self.assertTrue(evidence["capability_gap_evidence"]["fail_closed"])
        self.assertFalse(evidence["capability_ready"])


if __name__ == "__main__": unittest.main()
