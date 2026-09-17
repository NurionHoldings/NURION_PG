"""Synthetic memory/SQLite contract parity for role benchmark receipts."""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from .arkaon.governance import GovernanceRejected,canonical_digest
from .arkaon_role_separated_release_benchmark import ArkaonRoleSeparatedReleaseBenchmark
FOUNDRY_COMMIT="24ae4a601ee449649e40804119fa37667f731076"
FOUNDRY_PATTERN_ID="apf.public.repository-contract-parity"
FOUNDRY_PACKAGE_HASH="e1757d7a82ed9844f04c4a49fedc9c95111dca17b7efcf247c3cd6ba5eb88fbc"
FOUNDRY_PATTERN_STATUS="ETHERNIAN_REVIEW_REQUIRED"
PARITY_STATE="SYNTHETIC_PG_BENCHMARK_RECEIPT_REPOSITORY_CONTRACT_PARITY_VERIFIED"
SYNTHETIC_NAMESPACE="synthetic:pg:release-benchmark"
def _valid_digest(v:object)->bool:return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
@dataclass(frozen=True)
class BenchmarkReceipt:
    namespace:str;idempotency_key:str;benchmark_digest:str;outcome:str;receipt_digest:str
    def __post_init__(self)->None:
        if (self.namespace!=SYNTHETIC_NAMESPACE or not isinstance(self.idempotency_key,str) or not self.idempotency_key.startswith("synthetic:")
            or not _valid_digest(self.benchmark_digest) or self.outcome not in {"PASS","HOLD"}
            or self.receipt_digest!=canonical_digest(self.digest_value())):raise GovernanceRejected("valid synthetic benchmark receipt required")
    def digest_value(self)->dict[str,str]:return {"namespace":self.namespace,"idempotency_key":self.idempotency_key,"benchmark_digest":self.benchmark_digest,"outcome":self.outcome}
def _receipt(namespace:str,key:str,digest:str,outcome:str)->BenchmarkReceipt:
    values={"namespace":namespace,"idempotency_key":key,"benchmark_digest":digest,"outcome":outcome}
    return BenchmarkReceipt(namespace,key,digest,outcome,canonical_digest(values))
class MemoryBenchmarkReceiptRepository:
    def __init__(self)->None:self._items:dict[tuple[str,str],BenchmarkReceipt]={}
    def save(self,receipt:BenchmarkReceipt)->BenchmarkReceipt:
        if not isinstance(receipt,BenchmarkReceipt):raise GovernanceRejected("typed benchmark receipt required")
        receipt.__post_init__();key=(receipt.namespace,receipt.idempotency_key);old=self._items.get(key)
        if old is not None:
            if old!=receipt:raise GovernanceRejected("idempotency key payload conflict")
            return old
        self._items[key]=receipt;return receipt
class SQLiteBenchmarkReceiptRepository:
    def __init__(self)->None:
        self._db=sqlite3.connect(":memory:")
        self._db.execute("CREATE TABLE receipts(namespace TEXT NOT NULL,idempotency_key TEXT NOT NULL,benchmark_digest TEXT NOT NULL,outcome TEXT NOT NULL,receipt_digest TEXT NOT NULL,PRIMARY KEY(namespace,idempotency_key))")
    def save(self,receipt:BenchmarkReceipt)->BenchmarkReceipt:
        if not isinstance(receipt,BenchmarkReceipt):raise GovernanceRejected("typed benchmark receipt required")
        receipt.__post_init__();row=self._db.execute("SELECT benchmark_digest,outcome,receipt_digest FROM receipts WHERE namespace=? AND idempotency_key=?",(receipt.namespace,receipt.idempotency_key)).fetchone()
        if row is not None:
            old=BenchmarkReceipt(receipt.namespace,receipt.idempotency_key,row[0],row[1],row[2])
            if old!=receipt:raise GovernanceRejected("idempotency key payload conflict")
            return old
        with self._db:self._db.execute("INSERT INTO receipts VALUES(?,?,?,?,?)",(receipt.namespace,receipt.idempotency_key,receipt.benchmark_digest,receipt.outcome,receipt.receipt_digest))
        return receipt
    def close(self)->None:self._db.close()
def verify_repository_contract(benchmark:ArkaonRoleSeparatedReleaseBenchmark,*,idempotency_key:str)->dict[str,object]:
    if not isinstance(benchmark,ArkaonRoleSeparatedReleaseBenchmark):raise GovernanceRejected("typed role benchmark required")
    benchmark.__post_init__();receipt=_receipt(SYNTHETIC_NAMESPACE,idempotency_key,benchmark.benchmark_digest,benchmark.outcome.value)
    memory=MemoryBenchmarkReceiptRepository();sqlite=SQLiteBenchmarkReceiptRepository()
    try:
        memory_first=memory.save(receipt);memory_retry=memory.save(receipt);sqlite_first=sqlite.save(receipt);sqlite_retry=sqlite.save(receipt)
        parity=memory_first==memory_retry==sqlite_first==sqlite_retry
    finally:sqlite.close()
    if not parity:raise GovernanceRejected("repository contract parity required")
    values={"schema":"nurion.pg.arkaon-benchmark-receipt-repository-parity-evidence.v1","mode":"UNREGISTERED_SYNTHETIC_ONLY",
        "receipt_digest":receipt.receipt_digest,"memory_receipt_digest":memory_first.receipt_digest,"sqlite_receipt_digest":sqlite_first.receipt_digest,
        "idempotent_retry_equal":True,"adapter_outcomes_equal":True,"maximum_state":PARITY_STATE,"foundry_commit":FOUNDRY_COMMIT,
        "foundry_pattern_id":FOUNDRY_PATTERN_ID,"foundry_package_hash":FOUNDRY_PACKAGE_HASH,"foundry_pattern_status":FOUNDRY_PATTERN_STATUS,
        "postgresql_adapter_present":False,"production_database_method_present":False,"network_access_method_present":False,
        "release_approval_present":False,"automatic_merge_method_present":False,"credentials_used":False,"money_movement_executed":False,
        "deployment_allowed":False}
    return {**values,"report_digest":canonical_digest(values)}
