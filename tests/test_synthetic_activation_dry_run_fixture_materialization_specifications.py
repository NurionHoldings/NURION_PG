from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_plan_review import FixtureMaterializationPlanReviewDecision,SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_plans import SyntheticActivationDryRunFixtureMaterializationPlanBook
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_specifications import FIXTURE_MATERIALIZATION_SPECIFICATION_GATES,FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE,FIXTURE_MATERIALIZATION_SPECIFICATION_STATE,SyntheticActivationDryRunFixtureMaterializationSpecificationBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_materialization_plans import reviewed_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def reviewed_plan_source(decision=FixtureMaterializationPlanReviewDecision.PASS):
    resources,sd,ledger,source_docket,source_review=reviewed_source();plans=SyntheticActivationDryRunFixtureMaterializationPlanBook()
    plan=plans.plan_from_review(source_docket,source_review.draft.draft_id,planned_at=NOW);docket=SyntheticActivationDryRunFixtureMaterializationPlanReviewDocket()
    docket.submit(plans,plan.plan_id,submitted_at=NOW)
    review=docket.record_eternian_review(plan.plan_id,review_id="synthetic:activation-dry-run-fixture-materialization-plan-review:spec-source",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-plan:spec-source",decision=decision,
        findings_digest=sha256(b"fixture materialization specification source").hexdigest(),reviewed_at=NOW)
    return resources,sd,ledger,docket,review

class FixtureMaterializationSpecificationTests(unittest.TestCase):
    def test_specification_contains_only_locked_digests(self):
        resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook();before=docket.evidence()["report_digest"]
        item=book.specify_from_review(docket,review.plan.plan_id,specified_at=NOW)
        self.assertEqual(before,docket.evidence()["report_digest"]);self.assertEqual(item.scope,FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE)
        self.assertEqual(item.required_gates,FIXTURE_MATERIALIZATION_SPECIFICATION_GATES);self.assertEqual(item.state,FIXTURE_MATERIALIZATION_SPECIFICATION_STATE)
        self.assertFalse(item.fixture_content_present);self.assertFalse(item.fixture_bytes_present);self.assertFalse(item.filesystem_path_present);close_sources(resources,sd,ledger)
    def test_hold_reject_and_invalid_inputs_fail_closed(self):
        for decision in (FixtureMaterializationPlanReviewDecision.HOLD,FixtureMaterializationPlanReviewDecision.REJECT):
            resources,sd,ledger,docket,review=reviewed_plan_source(decision)
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationSpecificationBook().specify_from_review(docket,review.plan.plan_id,specified_at=NOW)
            close_sources(resources,sd,ledger)
    def test_type_and_time_fail_closed(self):
        resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook()
        with self.assertRaises(GovernanceRejected):book.specify_from_review(object(),review.plan.plan_id,specified_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):book.specify_from_review(docket,review.plan.plan_id,specified_at=value)
        close_sources(resources,sd,ledger)
    def test_replay_and_concurrency_converge(self):
        resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:book.specify_from_review(docket,review.plan.plan_id,specified_at=NOW),range(8)))
        self.assertTrue(all(i is items[0] for i in items));self.assertEqual(len(book.specifications),1);close_sources(resources,sd,ledger)
    def test_rehashed_identity_descriptor_and_forbidden_tampering_detected(self):
        for field,value in (("specification_id","synthetic:activation-dry-run-fixture-materialization-specification:"+"f"*32),
            ("specification_descriptor_digest","f"*64),("synthetic_only",False),("separate_review_required",False),
            ("fixture_content_present",True),("fixture_bytes_present",True),("filesystem_path_present",True),("filesystem_written",True)):
            resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook()
            item=book.specify_from_review(docket,review.plan.plan_id,specified_at=NOW);object.__setattr__(item,field,value)
            object.__setattr__(item,"specification_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_specification_chain());close_sources(resources,sd,ledger)
    def test_fully_rehashed_lineage_tampering_is_detected(self):
        resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook()
        item=book.specify_from_review(docket,review.plan.plan_id,specified_at=NOW);object.__setattr__(item,"source_plan_digest","f"*64)
        object.__setattr__(item,"specification_id","synthetic:activation-dry-run-fixture-materialization-specification:"+canonical_digest(
            {"plan_id":item.source_plan_id,"plan_digest":item.source_plan_digest,"review_digest":item.source_review_digest,"scope":FIXTURE_MATERIALIZATION_SPECIFICATION_SCOPE})[:32])
        object.__setattr__(item,"specification_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_specification_chain());close_sources(resources,sd,ledger)
    def test_nested_source_review_tampering_is_rejected(self):
        resources,sd,ledger,docket,review=reviewed_plan_source();object.__setattr__(review,"findings_digest","f"*64)
        with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationSpecificationBook().specify_from_review(docket,review.plan.plan_id,specified_at=NOW)
        close_sources(resources,sd,ledger)
    def test_source_change_discards_specification(self):
        resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook();original=docket.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;v=original();return v if calls==1 else {**v,"report_digest":"f"*64}
        docket.evidence=changing
        with self.assertRaises(GovernanceRejected):book.specify_from_review(docket,review.plan.plan_id,specified_at=NOW)
        self.assertEqual(book.specifications,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,docket,review=reviewed_plan_source();book=SyntheticActivationDryRunFixtureMaterializationSpecificationBook()
        book.specify_from_review(docket,review.plan.plan_id,specified_at=NOW);e=book.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_MATERIALIZATION_SPECIFICATION_STATE);self.assertTrue(e["specification_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__":unittest.main()
