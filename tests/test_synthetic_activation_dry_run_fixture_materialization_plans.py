from __future__ import annotations
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from nurion_pg.arkaon.governance import GovernanceRejected,canonical_digest
from nurion_pg.synthetic_activation_dry_run_fixture_draft_review import FixtureDraftReviewDecision,SyntheticActivationDryRunFixtureDraftReviewDocket
from nurion_pg.synthetic_activation_dry_run_fixture_drafts import SyntheticActivationDryRunFixtureDraftBook
from nurion_pg.synthetic_activation_dry_run_fixture_materialization_plans import FIXTURE_MATERIALIZATION_PLAN_GATES,FIXTURE_MATERIALIZATION_PLAN_SCOPE,FIXTURE_MATERIALIZATION_PLAN_STATE,SyntheticActivationDryRunFixtureMaterializationPlanBook
from tests.test_patch_draft_limited_promotion_reconfirmation_intake import NOW
from tests.test_synthetic_activation_dry_run_fixture_drafts import source
from tests.test_synthetic_patch_draft_limited_promotion_activation_drafts import close_sources

def reviewed_source(decision=FixtureDraftReviewDecision.PASS):
    resources,sd,ledger,proposal_review,proposal=source();drafts=SyntheticActivationDryRunFixtureDraftBook()
    draft=drafts.draft_from_review(proposal_review,proposal.proposal.proposal_id,drafted_at=NOW);docket=SyntheticActivationDryRunFixtureDraftReviewDocket()
    docket.submit(drafts,draft.draft_id,submitted_at=NOW)
    review=docket.record_eternian_review(draft.draft_id,review_id="synthetic:activation-dry-run-fixture-draft-review:plan-source",
        reviewer_id="synthetic:eternian-reviewer:activation-dry-run-fixture-draft:plan-source",decision=decision,
        findings_digest=sha256(b"fixture materialization plan source").hexdigest(),reviewed_at=NOW)
    return resources,sd,ledger,docket,review

class FixtureMaterializationPlanTests(unittest.TestCase):
    def test_plan_contains_only_locked_digests(self):
        resources,sd,ledger,docket,review=reviewed_source();book=SyntheticActivationDryRunFixtureMaterializationPlanBook();before=docket.evidence()["report_digest"]
        item=book.plan_from_review(docket,review.draft.draft_id,planned_at=NOW)
        self.assertEqual(before,docket.evidence()["report_digest"]);self.assertEqual(item.scope,FIXTURE_MATERIALIZATION_PLAN_SCOPE)
        self.assertEqual(item.required_gates,FIXTURE_MATERIALIZATION_PLAN_GATES);self.assertEqual(item.state,FIXTURE_MATERIALIZATION_PLAN_STATE)
        self.assertFalse(item.fixture_content_present);self.assertFalse(item.fixture_bytes_present);self.assertFalse(item.fixture_materialized);close_sources(resources,sd,ledger)
    def test_hold_reject_and_invalid_inputs_fail_closed(self):
        for decision in (FixtureDraftReviewDecision.HOLD,FixtureDraftReviewDecision.REJECT):
            resources,sd,ledger,docket,review=reviewed_source(decision)
            with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationPlanBook().plan_from_review(docket,review.draft.draft_id,planned_at=NOW)
            close_sources(resources,sd,ledger)
    def test_type_and_time_fail_closed(self):
        resources,sd,ledger,docket,review=reviewed_source();book=SyntheticActivationDryRunFixtureMaterializationPlanBook()
        with self.assertRaises(GovernanceRejected):book.plan_from_review(object(),review.draft.draft_id,planned_at=NOW)
        for value in (NOW.replace(tzinfo=None),NOW-timedelta(seconds=1)):
            with self.assertRaises(GovernanceRejected):book.plan_from_review(docket,review.draft.draft_id,planned_at=value)
        close_sources(resources,sd,ledger)
    def test_replay_and_concurrency_converge(self):
        resources,sd,ledger,docket,review=reviewed_source();book=SyntheticActivationDryRunFixtureMaterializationPlanBook()
        with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:book.plan_from_review(docket,review.draft.draft_id,planned_at=NOW),range(8)))
        self.assertTrue(all(i is items[0] for i in items));self.assertEqual(len(book.plans),1);close_sources(resources,sd,ledger)
    def test_rehashed_identity_descriptor_and_forbidden_tampering_detected(self):
        for field,value in (("plan_id","synthetic:activation-dry-run-fixture-materialization-plan:"+"f"*32),("artifact_descriptor_digest","f"*64),
            ("synthetic_only",False),("separate_review_required",False),("fixture_bytes_present",True),("filesystem_written",True)):
            resources,sd,ledger,docket,review=reviewed_source();book=SyntheticActivationDryRunFixtureMaterializationPlanBook();item=book.plan_from_review(docket,review.draft.draft_id,planned_at=NOW)
            object.__setattr__(item,field,value);object.__setattr__(item,"plan_digest",canonical_digest(item.digest_value()));self.assertFalse(book.verify_plan_chain());close_sources(resources,sd,ledger)
    def test_rehashed_source_review_tampering_is_rejected(self):
        resources,sd,ledger,docket,review=reviewed_source();object.__setattr__(review,"findings_digest","f"*64)
        with self.assertRaises(GovernanceRejected):SyntheticActivationDryRunFixtureMaterializationPlanBook().plan_from_review(docket,review.draft.draft_id,planned_at=NOW)
        close_sources(resources,sd,ledger)
    def test_source_change_discards_plan(self):
        resources,sd,ledger,docket,review=reviewed_source();book=SyntheticActivationDryRunFixtureMaterializationPlanBook();original=docket.evidence;calls=0
        def changing():
            nonlocal calls;calls+=1;v=original();return v if calls==1 else {**v,"report_digest":"f"*64}
        docket.evidence=changing
        with self.assertRaises(GovernanceRejected):book.plan_from_review(docket,review.draft.draft_id,planned_at=NOW)
        self.assertEqual(book.plans,());close_sources(resources,sd,ledger)
    def test_evidence_caps_authority(self):
        resources,sd,ledger,docket,review=reviewed_source();book=SyntheticActivationDryRunFixtureMaterializationPlanBook();book.plan_from_review(docket,review.draft.draft_id,planned_at=NOW);e=book.evidence()
        self.assertEqual(e["maximum_state"],FIXTURE_MATERIALIZATION_PLAN_STATE);self.assertTrue(e["plan_chain_valid"])
        for key in e:
            if key.endswith("_present") or key.endswith("_allowed") or key.endswith("_executed") or key.endswith("_used"):self.assertFalse(e[key])
        close_sources(resources,sd,ledger)

if __name__=="__main__":unittest.main()
