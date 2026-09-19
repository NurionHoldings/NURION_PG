"""Synthetic operator-audit repositories #486-#500; no external I/O."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Protocol
import sqlite3
from .arkaon.governance import GovernanceRejected,canonical_digest

def _digest(v):
 return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def _key(v):
 return isinstance(v,str) and v.startswith("synthetic:key:")

@dataclass(frozen=True)
class AuditCheckpointRecord:
 checkpoint_id:str
 checkpoint_digest:str
 sequence:int
 previous_digest:str|None
 report_digest:str
 idempotency_key:str
 created_at:str
 record_digest:str

class OperatorAuditRepository(Protocol):
 def append(self,checkpoint_id:str,checkpoint_digest:str,report_digest:str,idempotency_key:str,created_at:datetime)->AuditCheckpointRecord: ...
 def get(self,checkpoint_id:str)->AuditCheckpointRecord|None: ...
 def verify(self)->bool: ...
 def close(self)->None: ...

def _record(checkpoint_id,checkpoint_digest,sequence,previous_digest,report_digest,idempotency_key,created_at):
 if not checkpoint_id.startswith("synthetic:audit-checkpoint:") or not _digest(checkpoint_digest) or not _digest(report_digest) or not _key(idempotency_key) or created_at.tzinfo is None:raise GovernanceRejected("valid synthetic checkpoint required")
 payload={"checkpoint_id":checkpoint_id,"checkpoint_digest":checkpoint_digest,"sequence":sequence,"previous_digest":previous_digest,"report_digest":report_digest,"idempotency_key":idempotency_key,"created_at":created_at.isoformat()}
 return AuditCheckpointRecord(**payload,record_digest=canonical_digest(payload))

class MemoryOperatorAuditRepository:
 def __init__(self):self._rows=[];self._by_id={};self._by_key={};self._lock=RLock()
 def append(self,checkpoint_id,checkpoint_digest,report_digest,idempotency_key,created_at):
  with self._lock:
   candidate=(checkpoint_id,checkpoint_digest,report_digest,created_at.isoformat())
   if idempotency_key in self._by_key:
    old=self._by_key[idempotency_key]
    if candidate!=(old.checkpoint_id,old.checkpoint_digest,old.report_digest,old.created_at):raise GovernanceRejected("idempotency conflict")
    return old
   if checkpoint_id in self._by_id:raise GovernanceRejected("checkpoint collision")
   previous=self._rows[-1].record_digest if self._rows else None
   item=_record(checkpoint_id,checkpoint_digest,len(self._rows)+1,previous,report_digest,idempotency_key,created_at)
   self._rows.append(item);self._by_id[checkpoint_id]=item;self._by_key[idempotency_key]=item;return item
 def get(self,checkpoint_id):return self._by_id.get(checkpoint_id)
 def verify(self):
  previous=None
  for number,item in enumerate(self._rows,1):
   rebuilt=_record(item.checkpoint_id,item.checkpoint_digest,number,previous,item.report_digest,item.idempotency_key,datetime.fromisoformat(item.created_at))
   if rebuilt!=item:return False
   previous=item.record_digest
  return True
 def close(self):pass
 @property
 def count(self):return len(self._rows)

class SQLiteMemoryOperatorAuditRepository:
 def __init__(self):
  self._lock=RLock();self._db=sqlite3.connect(":memory:",check_same_thread=False,isolation_level=None)
  self._db.execute("CREATE TABLE audit_checkpoints(checkpoint_id TEXT PRIMARY KEY,checkpoint_digest TEXT NOT NULL,sequence INTEGER NOT NULL UNIQUE,previous_digest TEXT,report_digest TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL,record_digest TEXT NOT NULL)")
 def _row(self,row):return None if row is None else AuditCheckpointRecord(*row)
 def append(self,checkpoint_id,checkpoint_digest,report_digest,idempotency_key,created_at):
  with self._lock:
   self._db.execute("BEGIN IMMEDIATE")
   try:
    old=self._row(self._db.execute("SELECT checkpoint_id,checkpoint_digest,sequence,previous_digest,report_digest,idempotency_key,created_at,record_digest FROM audit_checkpoints WHERE idempotency_key=?",(idempotency_key,)).fetchone())
    if old:
     if (checkpoint_id,checkpoint_digest,report_digest,created_at.isoformat())!=(old.checkpoint_id,old.checkpoint_digest,old.report_digest,old.created_at):raise GovernanceRejected("idempotency conflict")
     self._db.execute("COMMIT");return old
    last=self._db.execute("SELECT sequence,record_digest FROM audit_checkpoints ORDER BY sequence DESC LIMIT 1").fetchone()
    sequence=1 if last is None else last[0]+1;previous=None if last is None else last[1]
    item=_record(checkpoint_id,checkpoint_digest,sequence,previous,report_digest,idempotency_key,created_at)
    self._db.execute("INSERT INTO audit_checkpoints VALUES(?,?,?,?,?,?,?,?)",(item.checkpoint_id,item.checkpoint_digest,item.sequence,item.previous_digest,item.report_digest,item.idempotency_key,item.created_at,item.record_digest));self._db.execute("COMMIT");return item
   except Exception:
    self._db.execute("ROLLBACK");raise
 def get(self,checkpoint_id):
  with self._lock:return self._row(self._db.execute("SELECT checkpoint_id,checkpoint_digest,sequence,previous_digest,report_digest,idempotency_key,created_at,record_digest FROM audit_checkpoints WHERE checkpoint_id=?",(checkpoint_id,)).fetchone())
 def verify(self):
  with self._lock:rows=[self._row(x) for x in self._db.execute("SELECT checkpoint_id,checkpoint_digest,sequence,previous_digest,report_digest,idempotency_key,created_at,record_digest FROM audit_checkpoints ORDER BY sequence")]
  previous=None
  for number,item in enumerate(rows,1):
   if _record(item.checkpoint_id,item.checkpoint_digest,number,previous,item.report_digest,item.idempotency_key,datetime.fromisoformat(item.created_at))!=item:return False
   previous=item.record_digest
  return True
 def close(self):self._db.close()
 @property
 def count(self):return self._db.execute("SELECT COUNT(*) FROM audit_checkpoints").fetchone()[0]

def repository_evidence(memory,sqlite_repo):
 out={"schema":"nurion.pg.synthetic-operator-audit-repositories.v1","features":list(range(486,501)),"maximum_state":"SYNTHETIC_OPERATOR_AUDIT_REPOSITORIES_VERIFIED","memory_count":memory.count,"sqlite_memory_count":sqlite_repo.count,"memory_chain_valid":memory.verify(),"sqlite_chain_valid":sqlite_repo.verify(),"records_equal":memory.count==sqlite_repo.count,"synthetic_only":True,"in_memory_only":True,"persistent_file_used":False,"external_io_used":False,"production_credentials_accessed":False,"payment_allowed":False,"refund_allowed":False,"settlement_allowed":False,"transfer_allowed":False,"ledger_posting_allowed":False,"deployment_allowed":False}
 return {**out,"report_digest":canonical_digest(out)}
