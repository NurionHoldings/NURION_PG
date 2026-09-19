from copy import deepcopy
import json
import unittest

from scripts.validate_arkaon_lesson_registry import REGISTRY, discovered_fix_commits, validate

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=json.loads(REGISTRY.read_text(encoding="utf-8"))
    def test_registry_covers_detected_fixes(self):
        ids=validate(self.data,discovered_fix_commits(self.data["scan_base_commit"])); self.assertEqual(len(ids),3)
    def test_unregistered_fix_fails_closed(self):
        with self.assertRaises(ValueError): validate(self.data,{"fffffff"})
    def test_missing_ack_fails_closed(self):
        data=deepcopy(self.data); data["lessons"][0]["arkaon_acknowledgement"]["acknowledged"]=False
        with self.assertRaises(ValueError): validate(data,set())
    def test_missing_negative_tests_fails_closed(self):
        data=deepcopy(self.data); data["lessons"][0]["required_negative_tests"]=[]
        with self.assertRaises(ValueError): validate(data,set())
    def test_missing_revalidation_fails_closed(self):
        data=deepcopy(self.data); data["lessons"][0]["revalidation_evidence"]["result"]="UNKNOWN"
        with self.assertRaises(ValueError): validate(data,set())

if __name__=="__main__": unittest.main()
