from __future__ import annotations
import unittest
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_fixture_materialization_dry_run_scenario_review import SCENARIO_REVIEW_MAXIMUM_STATE,ScenarioReviewDecision,SyntheticFixtureMaterializationDryRunScenarioReviewDocket
from nurion_pg.synthetic_fixture_materialization_dry_run_scenarios import SyntheticFixtureMaterializationDryRunScenarioBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_fixture_materialization_dry_run_scenarios import source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
def scenario_source():
    resources,sd,ledger,docket,review=source();book=SyntheticFixtureMaterializationDryRunScenarioBook()
    scenario=book.draft_from_review(docket,review.plan.plan_id,drafted_at=NOW);return resources,sd,ledger,book,scenario
def review(docket,scenario,decision=ScenarioReviewDecision.PASS):
    return docket.record_eternian_review(scenario.scenario_id,review_id="synthetic:fixture-materialization-dry-run-scenario-review:draft",
        reviewer_id="synthetic:eternian-reviewer:fixture-materialization-dry-run-scenario:draft",decision=decision,
        findings_digest=sha256(b"scenario review").hexdigest(),reviewed_at=NOW)
class ScenarioReviewTests(unittest.TestCase):
    def test_pass_and_hold_reject(self):
        resources,sd,ledger,book,scenario=scenario_source();docket=SyntheticFixtureMaterializationDryRunScenarioReviewDocket()
        docket.submit(book,scenario.scenario_id,submitted_at=NOW);final=review(docket,scenario);self.assertIs(docket.ready_source(scenario.scenario_id),final)
        self.assertEqual(final.state.value,SCENARIO_REVIEW_MAXIMUM_STATE);close_sources(resources,sd,ledger)
        for decision in (ScenarioReviewDecision.HOLD,ScenarioReviewDecision.REJECT):
            resources,sd,ledger,book,scenario=scenario_source();docket=SyntheticFixtureMaterializationDryRunScenarioReviewDocket()
            docket.submit(book,scenario.scenario_id,submitted_at=NOW);review(docket,scenario,decision)
            with self.assertRaises(GovernanceRejected):docket.ready_source(scenario.scenario_id)
            close_sources(resources,sd,ledger)
    def test_invalid_time_and_type_fail_closed(self):
        resources,sd,ledger,book,scenario=scenario_source();docket=SyntheticFixtureMaterializationDryRunScenarioReviewDocket()
        with self.assertRaises(GovernanceRejected):docket.submit(object(),scenario.scenario_id,submitted_at=NOW)
        with self.assertRaises(GovernanceRejected):docket.submit(book,scenario.scenario_id,submitted_at=NOW-timedelta(seconds=1))
        close_sources(resources,sd,ledger)
    def test_rehashed_metadata_and_source_tampering_detected(self):
        resources,sd,ledger,book,scenario=scenario_source();docket=SyntheticFixtureMaterializationDryRunScenarioReviewDocket()
        item=docket.submit(book,scenario.scenario_id,submitted_at=NOW);object.__setattr__(item,"submitted_at",NOW-timedelta(seconds=1))
        object.__setattr__(item,"submission_digest",canonical_digest(item.submission_value()));self.assertFalse(docket.verify_chain());close_sources(resources,sd,ledger)
        resources,sd,ledger,book,scenario=scenario_source();object.__setattr__(scenario,"dry_run_executed",True);object.__setattr__(scenario,"scenario_digest",canonical_digest(scenario.digest_value()))
        with self.assertRaises(GovernanceRejected):SyntheticFixtureMaterializationDryRunScenarioReviewDocket().submit(book,scenario.scenario_id,submitted_at=NOW)
        close_sources(resources,sd,ledger)
    def test_immutable_and_evidence_caps_authority(self):
        resources,sd,ledger,book,scenario=scenario_source();docket=SyntheticFixtureMaterializationDryRunScenarioReviewDocket()
        docket.submit(book,scenario.scenario_id,submitted_at=NOW);first=review(docket,scenario);self.assertIs(review(docket,scenario),first)
        with self.assertRaises(GovernanceRejected):review(docket,scenario,ScenarioReviewDecision.HOLD)
        e=docket.evidence();self.assertTrue(e["review_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)
if __name__=="__main__":unittest.main()
