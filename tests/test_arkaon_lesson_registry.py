from copy import deepcopy
from hashlib import sha256
import json
import unittest
from pathlib import Path

from scripts.validate_arkaon_lesson_registry import (MANIFEST, REGISTRY, declared_remediations,
                                                     discovered_negative_tests, validate,
                                                     HISTORICAL_LESSON_SNAPSHOTS, LESSONS_12301, STAGE_LESSON_SNAPSHOTS,
                                                     validated_stage_chain, validated_stage_chain_through,
                                                     validated_stage_snapshot)

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.declared=declared_remediations(json.loads(MANIFEST.read_text(encoding="utf-8")))
        cls.tests=discovered_negative_tests()
    def test_registry_covers_detected_fixes(self):
        ids=validate(self.data,self.declared,self.tests); self.assertEqual(len(ids),38)
    def test_unregistered_fix_fails_closed(self):
        bad=dict(self.declared)|{"ETH-UNREGISTERED": {"ARL-MISSING"}}
        with self.assertRaises(ValueError): validate(self.data,bad,self.tests)
    def test_missing_ack_fails_closed(self):
        data=deepcopy(self.data); data["lessons"][0]["arkaon_acknowledgement"]["acknowledged"]=False
        with self.assertRaises(ValueError): validate(data,self.declared,self.tests)
    def test_missing_negative_tests_fails_closed(self):
        data=deepcopy(self.data); data["lessons"][0]["required_negative_tests"]=[]
        with self.assertRaises(ValueError): validate(data,self.declared,self.tests)
    def test_missing_revalidation_fails_closed(self):
        data=deepcopy(self.data); data["lessons"][0]["revalidation_evidence"]["result"]="UNKNOWN"
        with self.assertRaises(ValueError): validate(data,self.declared,self.tests)
    def test_named_negative_test_must_exist(self):
        data=deepcopy(self.data); data["lessons"][0]["required_negative_tests"]=["test_missing_from_repository"]
        with self.assertRaises(ValueError): validate(data,self.declared,self.tests)
    def test_validator_has_no_git_history_dependency(self):
        source=Path("scripts/validate_arkaon_lesson_registry.py").read_text(encoding="utf-8")
        self.assertNotIn("git log",source); self.assertNotIn("subprocess",source)
    def test_future_registry_superset_preserves_prior_stage_snapshot(self):
        current=validate(self.data,self.declared,self.tests);future=current+("ARL-FUTURE-001",)
        before=validated_stage_snapshot(current,LESSONS_12301,"ARKAON-LESSONS-12301",(9901,12700));after=validated_stage_snapshot(future,LESSONS_12301,"ARKAON-LESSONS-12301",(9901,12700))
        self.assertEqual(before,after)
    def test_prior_stage_evidence_payload_digest_future_invariant(self):
        current=validate(self.data,self.declared,self.tests);future=current+("ARL-FUTURE-001",)
        before=validated_stage_snapshot(current,LESSONS_12301,"ARKAON-LESSONS-12301",(9901,12700));after=validated_stage_snapshot(future,LESSONS_12301,"ARKAON-LESSONS-12301",(9901,12700))
        payload=lambda snapshot:json.dumps({"range":[9901,12700],"applied_lesson_ids":snapshot[0],"lesson_registry_digest":snapshot[1]},sort_keys=True,separators=(",",":"))
        self.assertEqual((payload(before),sha256(payload(before).encode()).hexdigest()),(payload(after),sha256(payload(after).encode()).hexdigest()))
    def test_future_lesson_cannot_be_claimed_without_explicit_snapshot(self):
        current=validate(self.data,self.declared,self.tests);future=current+("ARL-FUTURE-001",)
        required=STAGE_LESSON_SNAPSHOTS["ARKAON-LESSONS-12701"][1]
        self.assertEqual(validated_stage_snapshot(current,required,"ARKAON-LESSONS-12701",(12701,13100)),validated_stage_snapshot(future,required,"ARKAON-LESSONS-12701",(12701,13100)))
        with self.assertRaises(ValueError):validated_stage_snapshot(future,tuple(sorted(required+("ARL-FUTURE-001",))),"ARKAON-LESSONS-12701",(12701,13100))
    def test_stage_snapshot_chain_is_contiguous(self):
        self.assertEqual(len(validated_stage_chain()),16)
    def test_prior_runner_boundary_ignores_future_snapshot(self):
        future=dict(STAGE_LESSON_SNAPSHOTS);latest=STAGE_LESSON_SNAPSHOTS["ARKAON-LESSONS-14301"][1];future["ARKAON-LESSONS-14701"]=((14701,15100),latest+("ARL-FUTURE-TEST",))
        bounded=validated_stage_chain_through(14300,future)
        self.assertEqual((len(bounded),bounded[-1][0],bounded[-1][1]),(5,"ARKAON-LESSONS-13901",(13901,14300)))
    def test_answer_intake_snapshot_payload_is_future_invariant(self):
        current=validate(self.data,self.declared,self.tests);required=HISTORICAL_LESSON_SNAPSHOTS["ARKAON-LESSONS-7501"][1];future=current+("ARL-FUTURE-002",)
        self.assertEqual(validated_stage_snapshot(current,required,"ARKAON-LESSONS-7501",(7501,7900)),validated_stage_snapshot(future,required,"ARKAON-LESSONS-7501",(7501,7900)))
    def test_stage_snapshot_overlap_rejected(self):
        bad=dict(STAGE_LESSON_SNAPSHOTS);bad["OVERLAP"]=((13000,13200),STAGE_LESSON_SNAPSHOTS["ARKAON-LESSONS-12701"][1])
        with self.assertRaises(ValueError):validated_stage_chain(bad)
    def test_stage_snapshot_gap_rejected(self):
        bad=dict(STAGE_LESSON_SNAPSHOTS);bad["ARKAON-LESSONS-13101"]=((13102,13500),bad["ARKAON-LESSONS-13101"][1])
        with self.assertRaises(ValueError):validated_stage_chain(bad)
    def test_stage_snapshot_lesson_regression_rejected(self):
        bad=dict(STAGE_LESSON_SNAPSHOTS);bad["ARKAON-LESSONS-13101"]=((13101,13500),LESSONS_12301)
        with self.assertRaises(ValueError):validated_stage_chain(bad)

if __name__=="__main__": unittest.main()
