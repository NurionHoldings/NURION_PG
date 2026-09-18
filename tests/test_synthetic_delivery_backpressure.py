from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC,datetime,timedelta
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.synthetic_delivery_backpressure import SyntheticDeliveryQueue
NOW=datetime(2026,9,18,tzinfo=UTC);h=lambda x:sha256(x).hexdigest()
class Tests(unittest.TestCase):
 def test_backpressure_capacity_fails_closed(self):
  q=SyntheticDeliveryQueue(1);q.enqueue("synthetic:packet:1",h(b"1"),NOW,NOW+timedelta(hours=1))
  with self.assertRaises(GovernanceRejected):q.enqueue("synthetic:packet:2",h(b"2"),NOW,NOW+timedelta(hours=1))
 def test_duplicate_intent_returns_existing_packet(self):
  q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:1",h(b"x"),NOW,NOW+timedelta(hours=1));b=q.enqueue("synthetic:packet:2",h(b"x"),NOW,NOW+timedelta(hours=1));self.assertIs(a,b);self.assertEqual(q.evidence()["packet_count"],1)
 def test_concurrent_duplicate_has_single_packet(self):
  q=SyntheticDeliveryQueue()
  with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:q.enqueue("synthetic:packet:1",h(b"x"),NOW,NOW+timedelta(hours=1)),range(8)))
  self.assertTrue(all(x is rows[0] for x in rows));self.assertEqual(q.evidence()["packet_count"],1)
 def test_refresh_warning_hold_clear_and_verified_resume(self):
  q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:1",h(b"x"),NOW,NOW+timedelta(hours=1));a=q.refresh(a.packet_id,a.version,NOW+timedelta(hours=2),NOW);a=q.warn(a.packet_id,a.version,"STALE_PACKET",NOW)
  with self.assertRaises(GovernanceRejected):q.warn(a.packet_id,a.version,"CAPACITY_PRESSURE",NOW)
  a=q.hold(a.packet_id,a.version,NOW)
  with self.assertRaises(GovernanceRejected):q.transition(a.packet_id,a.version,"READY",NOW)
  a=q.clear_warning(a.packet_id,a.version,NOW);a=q.verify_resume(a.packet_id,a.version,"synthetic:verifier:1",h(b"resume"),NOW);a=q.transition(a.packet_id,a.version,"READY",NOW);self.assertEqual(a.status,"READY")
 def test_superseded_and_expired_cleanup(self):
  q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:1",h(b"1"),NOW,NOW+timedelta(hours=1));self.assertEqual(q.transition(a.packet_id,a.version,"SUPERSEDED",NOW).status,"SUPERSEDED")
  b=q.enqueue("synthetic:packet:2",h(b"2"),NOW,NOW+timedelta(hours=1))
  with self.assertRaises(GovernanceRejected):q.transition(b.packet_id,b.version,"EXPIRED",NOW)
  self.assertEqual(q.transition(b.packet_id,b.version,"EXPIRED",NOW+timedelta(hours=2)).status,"EXPIRED")
 def test_stale_version_and_external_effects_absent(self):
  q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:1",h(b"x"),NOW,NOW+timedelta(hours=1))
  with self.assertRaises(GovernanceRejected):q.refresh(a.packet_id,99,NOW+timedelta(hours=2),NOW)
  e=q.evidence();self.assertEqual(e["features"],list(range(701,901)))
  for k,v in e.items():
   if k.endswith("_allowed") or k.endswith("_used") or k.endswith("_accessed"):self.assertFalse(v)
 def test_full_capacity_duplicate_remains_idempotent(self):
  q=SyntheticDeliveryQueue(1);a=q.enqueue("synthetic:packet:1",h(b"x"),NOW,NOW+timedelta(hours=1));self.assertIs(a,q.enqueue("synthetic:packet:2",h(b"x"),NOW,NOW+timedelta(hours=1)))
 def test_terminal_and_expired_mutations_fail_closed(self):
  for terminal in ("SUPERSEDED","EXPIRED","CLOSED"):
   q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:1",h(terminal.encode()),NOW,NOW+timedelta(hours=1))
   if terminal=="EXPIRED":a=q.transition(a.packet_id,a.version,terminal,NOW+timedelta(hours=2))
   else:a=q.transition(a.packet_id,a.version,terminal,NOW)
   with self.assertRaises(GovernanceRejected):q.warn(a.packet_id,a.version,"STALE_PACKET",NOW)
  q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:e",h(b"expired"),NOW,NOW+timedelta(hours=1))
  for action in ("warn","hold","refresh"):
   with self.assertRaises(GovernanceRejected):
    {"warn":lambda:q.warn(a.packet_id,a.version,"STALE_PACKET",NOW+timedelta(hours=2)),"hold":lambda:q.hold(a.packet_id,a.version,NOW+timedelta(hours=2)),"refresh":lambda:q.refresh(a.packet_id,a.version,NOW+timedelta(hours=3),NOW+timedelta(hours=2))}[action]()
 def test_resume_receipt_idempotency_conflict_and_tamper(self):
  q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:r",h(b"r"),NOW,NOW+timedelta(hours=1));a=q.warn(a.packet_id,a.version,"STALE_PACKET",NOW);a=q.hold(a.packet_id,a.version,NOW);a=q.clear_warning(a.packet_id,a.version,NOW);source=a.version;a=q.verify_resume(a.packet_id,source,"synthetic:verifier:1",h(b"receipt"),NOW);self.assertIs(a,q.verify_resume(a.packet_id,source,"synthetic:verifier:1",h(b"receipt"),NOW))
  with self.assertRaises(GovernanceRejected):q.verify_resume(a.packet_id,source,"synthetic:verifier:1",h(b"other"),NOW)
  receipt=q._resume_receipts[a.packet_id];q._resume_receipts[a.packet_id]=replace(receipt,verifier="tampered")
  self.assertFalse(q.evidence()["receipt_integrity_valid"])
  with self.assertRaises(GovernanceRejected):q.transition(a.packet_id,a.version,"READY",NOW)
 def test_evidence_chains_and_invalid_digest(self):
  q=SyntheticDeliveryQueue();a=q.enqueue("synthetic:packet:1",h(b"x"),NOW,NOW+timedelta(hours=1));a=q.warn(a.packet_id,a.version,"STALE_PACKET",NOW);a=q.hold(a.packet_id,a.version,NOW);a=q.clear_warning(a.packet_id,a.version,NOW);a=q.verify_resume(a.packet_id,a.version,"synthetic:verifier:1",h(b"receipt"),NOW);q.transition(a.packet_id,a.version,"READY",NOW)
  e=q.evidence();self.assertEqual(e["event_count"],6);self.assertEqual(e["history_count"],6);self.assertTrue(e["event_chain_valid"]);self.assertTrue(e["history_chain_valid"]);self.assertTrue(e["receipt_integrity_valid"]);self.assertEqual(e["resume_receipt_count"],1)
  q._events[0]["action"]="tampered";self.assertFalse(q.evidence()["event_chain_valid"])
  q2=SyntheticDeliveryQueue();x=q2.enqueue("synthetic:packet:history",h(b"history"),NOW,NOW+timedelta(hours=1));q2._history[0]=replace(x,warning="tampered");self.assertFalse(q2.evidence()["history_chain_valid"])
  q3=SyntheticDeliveryQueue();x=q3.enqueue("synthetic:packet:tip",h(b"tip"),NOW,NOW+timedelta(hours=1));q3._rows[x.packet_id]=replace(x,warning="tampered");self.assertFalse(q3.evidence()["history_chain_valid"])
  with self.assertRaises(GovernanceRejected):SyntheticDeliveryQueue().enqueue("synthetic:packet:bad","z"*64,NOW,NOW+timedelta(hours=1))
if __name__=="__main__":unittest.main()
