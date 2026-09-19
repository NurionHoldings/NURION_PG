from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC,datetime
from hashlib import sha256
import unittest
from nurion_pg.arkaon.governance import GovernanceRejected
from nurion_pg.operator_audit_repositories import MemoryOperatorAuditRepository,SQLiteMemoryOperatorAuditRepository,repository_evidence
h=lambda x:sha256(x).hexdigest();NOW=datetime(2026,9,18,tzinfo=UTC)
def args(n=1):return (f"synthetic:audit-checkpoint:{n}",h(f"checkpoint:{n}".encode()),h(f"report:{n}".encode()),f"synthetic:key:{n}",NOW)
class Tests(unittest.TestCase):
 def setUp(self):self.memory=MemoryOperatorAuditRepository();self.sqlite=SQLiteMemoryOperatorAuditRepository()
 def tearDown(self):self.sqlite.close()
 def test_backends_have_equal_contract_and_chain(self):
  for n in (1,2):
   self.assertEqual(self.memory.append(*args(n)),self.sqlite.append(*args(n)))
  e=repository_evidence(self.memory,self.sqlite);self.assertEqual(e["features"],list(range(486,501)));self.assertTrue(e["records_equal"]);self.assertTrue(e["memory_chain_valid"]);self.assertTrue(e["sqlite_chain_valid"])
 def test_idempotent_replay_and_conflict(self):
  for repo in (self.memory,self.sqlite):
   first=repo.append(*args());self.assertIsNotNone(first);self.assertEqual(first,repo.append(*args()))
   bad=list(args());bad[2]=h(b"other")
   with self.assertRaises(GovernanceRejected):repo.append(*bad)
 def test_checkpoint_collision_is_blocked(self):
  for repo in (self.memory,self.sqlite):
   repo.append(*args());bad=list(args(2));bad[0]="synthetic:audit-checkpoint:1"
   with self.assertRaises((GovernanceRejected,Exception)):repo.append(*bad)
 def test_concurrent_replay_has_one_record(self):
  for repo in (self.memory,self.sqlite):
   with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:repo.append(*args()),range(8)))
   self.assertTrue(all(row==rows[0] for row in rows));self.assertEqual(repo.count,1);self.assertTrue(repo.verify())
 def test_tampering_is_detected(self):
  self.memory.append(*args());self.memory._rows[0]=replace(self.memory._rows[0],report_digest=h(b"tampered"));self.assertFalse(self.memory.verify())
  self.sqlite.append(*args());self.sqlite._db.execute("UPDATE audit_checkpoints SET report_digest=? WHERE sequence=1",(h(b"tampered"),));self.assertFalse(self.sqlite.verify())
 def test_invalid_synthetic_boundary_is_rejected(self):
  for repo in (self.memory,self.sqlite):
   bad=list(args());bad[0]="real-checkpoint"
   with self.assertRaises(GovernanceRejected):repo.append(*bad)
if __name__=="__main__":unittest.main()
