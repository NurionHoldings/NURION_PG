from copy import deepcopy
import json
import unittest
from pathlib import Path

from scripts.validate_arkaon_lesson_registry import (MANIFEST, REGISTRY, declared_remediations,
                                                     discovered_negative_tests, validate)

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.declared=declared_remediations(json.loads(MANIFEST.read_text(encoding="utf-8")))
        cls.tests=discovered_negative_tests()
    def test_registry_covers_detected_fixes(self):
        ids=validate(self.data,self.declared,self.tests); self.assertEqual(len(ids),5)
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

if __name__=="__main__": unittest.main()
