from __future__ import annotations
import unittest
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_dry_run_plan_review import MaterializationDryRunPlanReviewDecision,SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_dry_run_plans import SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook
from nurion_pg.synthetic_fixture_materialization_dry_run_scenarios import SCENARIO_STATE,SyntheticFixtureMaterializationDryRunScenarioBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_materialization_dry_run_plans import reviewed_specification_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources
def source(decision=MaterializationDryRunPlanReviewDecision.PASS):
    resources,sd,ledger,docket,review=reviewed_specification_source();plans=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
    plan=plans.plan_from_review(docket,review.specification.specification_id,planned_at=NOW);reviews=SyntheticActivationDryRunFixtureMaterializationDryRunPlanReviewDocket()
    reviews.submit(plans,plan.plan_id,submitted_at=NOW);final=reviews.record_eternian_review(plan.plan_id,
        review_id="synthetic:activation-dry-run-fixture-materialization-dry-run-plan-review:scenario",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-dry-run-plan:scenario",
        decision=decision,findings_digest=sha256(b"scenario source").hexdigest(),reviewed_at=NOW);return resources,sd,ledger,reviews,final
class ScenarioTests(unittest.TestCase):
    def test_content_free_scenario(self):
        resources,sd,ledger,docket,review=source();book=SyntheticFixtureMaterializationDryRunScenarioBook();item=book.draft_from_review(docket,review.plan.plan_id,drafted_at=NOW)
        self.assertEqual(item.state,SCENARIO_STATE);self.assertFalse(item.observations_present);self.assertFalse(item.dry_run_executed);self.assertTrue(book.verify_chain());close_sources(resources,sd,ledger)
    def test_hold_reject_fail_closed(self):
        for decision in (MaterializationDryRunPlanReviewDecision.HOLD,MaterializationDryRunPlanReviewDecision.REJECT):
            resources,sd,ledger,docket,review=source(decision)
            with self.assertRaises(GovernanceRejected):SyntheticFixtureMaterializationDryRunScenarioBook().draft_from_review(docket,review.plan.plan_id,drafted_at=NOW)
            close_sources(resources,sd,ledger)
    def test_tamper_and_authority_fail_closed(self):
        resources,sd,ledger,docket,review=source();book=SyntheticFixtureMaterializationDryRunScenarioBook();item=book.draft_from_review(docket,review.plan.plan_id,drafted_at=NOW)
        object.__setattr__(item,"dry_run_executed",True);object.__setattr__(item,"scenario_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_chain());close_sources(resources,sd,ledger)
        e=SyntheticFixtureMaterializationDryRunScenarioBook().evidence()
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
if __name__=="__main__":unittest.main()
