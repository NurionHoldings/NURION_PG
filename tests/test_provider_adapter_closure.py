import unittest
from scripts.validate_provider_adapter_closure import validate
class ClosureTests(unittest.TestCase):
    def test_closed_without_live_authority(self):
        value=validate();self.assertEqual(value["completion_percent"],100);self.assertFalse(value["live_payment_executed"])
if __name__=="__main__":unittest.main()
