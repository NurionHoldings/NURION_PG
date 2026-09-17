from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_dry_run_plans import MATERIALIZATION_DRY_RUN_PLAN_GATES,MATERIALIZATION_DRY_RUN_PLAN_SCOPE,MATERIALIZATION_DRY_RUN_PLAN_STATE,SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_specification_review import FixtureMaterializationSpecificationReviewDecision,SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_specifications import SyntheticActivationDryRunFixtureMaterializationSpecificationBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_materialization_specifications import reviewed_plan_source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def reviewed_specification_source(decision=FixtureMaterializationSpecificationReviewDecision.PASS):
    resources,sd,ledger,source_docket,source_review=reviewed_plan_source();specs=SyntheticActivationDryRunFixtureMaterializationSpecificationBook()
    spec=specs.specify_from_review(source_docket,source_review.plan.plan_id,specified_at=NOW)
    docket=SyntheticActivationDryRunFixtureMaterializationSpecificationReviewDocket();docket.submit(specs,spec.specification_id,submitted_at=NOW)
    review=docket.record_eternian_review(spec.specification_id,
        review_id="synthetic:activation-dry-run-fixture-materialization-specification-review:plan-source",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-materialization-specification:plan-source",
        decision=decision,findings_digest=sha256(b"materialization dry-run plan source").hexdigest(),reviewed_at=NOW)
    return resources,sd,ledger,docket,review

class MaterializationDryRunPlanTests(unittest.TestCase):
    def test_plan_is_contract_digest_only(self):
        resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
        before=docket.evidence()["report_digest"];item=book.plan_from_review(docket,review.specification.specification_id,planned_at=NOW)
        self.assertEqual(before,docket.evidence()["report_digest"]);self.assertEqual(item.scope,MATERIALIZATION_DRY_RUN_PLAN_SCOPE)
        self.assertEqual(item.required_gates,MATERIALIZATION_DRY_RUN_PLAN_GATES);self.assertEqual(item.state,MATERIALIZATION_DRY_RUN_PLAN_STATE)
        self.assertFalse(item.fixture_content_present);self.assertFalse(item.fixture_file_present);self.assertFalse(item.dry_run_executed);close_sources(resources,sd,ledger)
    def test_hold_reject_and_invalid_inputs_fail_closed(self):
        for decision in (FixtureMaterializationSpecificationReviewDecision.HOLD,FixtureMaterializationSpecificationReviewDecision.REJECT):
            resources,sd,ledger,docket,review=reviewed_specification_source(decision)
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook().plan_from_review(docket,review.specification.specification_id,planned_at=NOW)
            close_sources(resources,sd,ledger)
    def test_type_and_time_fail_closed(self):
        resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
        with self.assertRaises(GovernanceRejected):book.plan_from_review(object(),review.specification.specification_id,planned_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):book.plan_from_review(docket,review.specification.specification_id,planned_at=value)
        close_sources(resources,sd,ledger)
    def test_replay_and_concurrency_converge(self):
        resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:book.plan_from_review(docket,review.specification.specification_id,planned_at=NOW),range(8)))
        self.assertTrue(all(i is items[0] for i in items));self.assertEqual(len(book.plans),1);close_sources(resources,sd,ledger)
    def test_rehashed_identity_contract_and_forbidden_tampering_detected(self):
        for field,value in (("plan_id","synthetic:activation-dry-run-fixture-materialization-dry-run-plan:"+"f"*32),
            ("dry_run_contract_digest","f"*64),("synthetic_only",False),("separate_review_required",False),
            ("fixture_content_present",True),("fixture_bytes_present",True),("filesystem_path_present",True),
            ("fixture_file_present",True),("filesystem_written",True),("dry_run_executed",True)):
            resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
            item=book.plan_from_review(docket,review.specification.specification_id,planned_at=NOW);object.__setattr__(item,field,value)
            object.__setattr__(item,"plan_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_plan_chain());close_sources(resources,sd,ledger)
    def test_fully_rehashed_lineage_and_nested_review_tampering_detected(self):
        resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
        item=book.plan_from_review(docket,review.specification.specification_id,planned_at=NOW);object.__setattr__(item,"source_specification_digest","f"*64)
        object.__setattr__(item,"plan_id","synthetic:activation-dry-run-fixture-materialization-dry-run-plan:"+canonical_digest(
            {"specification_id":item.source_specification_id,"specification_digest":item.source_specification_digest,
             "review_digest":item.source_review_digest,"scope":MATERIALIZATION_DRY_RUN_PLAN_SCOPE})[:32])
        object.__setattr__(item,"plan_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_plan_chain());close_sources(resources,sd,ledger)
        resources,sd,ledger,docket,review=reviewed_specification_source();object.__setattr__(review,"findings_digest","f"*64)
        with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook().plan_from_review(
            docket,review.specification.specification_id,planned_at=NOW)
        close_sources(resources,sd,ledger)
    def test_source_change_discards_plan(self):
        resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook();original=docket.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;v=original();return v if calls==1 else {**v,"report_digest":"f"*64}
        docket.evidence=changing
        with self.assertRaises(GovernanceRejected):book.plan_from_review(docket,review.specification.specification_id,planned_at=NOW)
        self.assertEqual(book.plans,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,docket,review=reviewed_specification_source();book=SyntheticActivationDryRunFixtureMaterializationDryRunPlanBook()
        book.plan_from_review(docket,review.specification.specification_id,planned_at=NOW);e=book.evidence()
        self.assertEqual(e["maximum_state"],MATERIALIZATION_DRY_RUN_PLAN_STATE);self.assertTrue(e["plan_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__":unittest.main()
