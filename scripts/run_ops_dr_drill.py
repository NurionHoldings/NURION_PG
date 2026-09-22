from __future__ import annotations
import json,os,subprocess,tempfile,time
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import psycopg
from nurion_pg.ledger import capture_journal
from nurion_pg.storage.ledger_repository import PostgresLedgerRepository
from nurion_pg.storage.postgres import MIGRATION_VERSION,PostgresFoundation
from nurion_pg.payments import PaymentService
from nurion_pg.storage.payment_repository import PostgresPaymentRepository

ROOT=Path(__file__).resolve().parents[1];SCHEMA="nurion_pg_dr_drill"
def run(cmd):subprocess.run(cmd,check=True,capture_output=True,text=True)
def main():
 if os.getenv("NURION_PG_EPHEMERAL_TEST")!="1":raise SystemExit("ephemeral PostgreSQL gate required")
 conn=psycopg.connect(connect_timeout=5,autocommit=True);foundation=PostgresFoundation(conn,SCHEMA);foundation.rollback();foundation.migrate_up()
 try:
  foundation.provision_principal("merchant-dr","principal-dr","key-dr",sha256(b"dr-fixture").hexdigest(),["auditor"])
  PaymentService(PostgresPaymentRepository(conn,SCHEMA)).create("merchant-dr",10000,"KRW","dr-payment","dr-order",{})
  ledger=PostgresLedgerRepository(conn,SCHEMA);journal=capture_journal(str(uuid4()),"merchant-dr","KRW","dr-capture",10000,500,300);ledger.post(journal)
  before={"migrations":conn.execute(f"SELECT count(*) FROM {SCHEMA}.schema_migrations").fetchone()[0],"payments":conn.execute(f"SELECT count(*) FROM {SCHEMA}.payment_intents").fetchone()[0],"journals":conn.execute(f"SELECT count(*) FROM {SCHEMA}.ledger_journals").fetchone()[0],"outbox":conn.execute(f"SELECT count(*) FROM {SCHEMA}.outbox_events").fetchone()[0],"merchant_payable":ledger.balance("merchant-dr","KRW","merchant_payable")}
  last_write=conn.execute(f"SELECT max(created_at) FROM {SCHEMA}.outbox_events").fetchone()[0];started=time.monotonic()
  with tempfile.TemporaryDirectory(prefix="nurion-pg-dr-") as tmp:
   dump=str(Path(tmp)/"backup.dump");run(["pg_dump","--format=custom","--no-owner","--no-acl","--schema",SCHEMA,"--file",dump])
   if not Path(dump).is_file() or Path(dump).stat().st_size==0:raise RuntimeError("backup artifact is empty")
   backup_sha=sha256(Path(dump).read_bytes()).hexdigest();foundation.rollback();run(["pg_restore","--exit-on-error","--no-owner","--no-acl","--dbname",conn.info.dbname,dump])
  rto=time.monotonic()-started;restored=PostgresFoundation(conn,SCHEMA);assert restored.migrate_up() is False
  after={"migrations":conn.execute(f"SELECT count(*) FROM {SCHEMA}.schema_migrations").fetchone()[0],"payments":conn.execute(f"SELECT count(*) FROM {SCHEMA}.payment_intents").fetchone()[0],"journals":conn.execute(f"SELECT count(*) FROM {SCHEMA}.ledger_journals").fetchone()[0],"outbox":conn.execute(f"SELECT count(*) FROM {SCHEMA}.outbox_events").fetchone()[0],"merchant_payable":PostgresLedgerRepository(conn,SCHEMA).balance("merchant-dr","KRW","merchant_payable")}
  imbalanced=conn.execute(f"SELECT count(*) FROM (SELECT e.journal_id,sum(CASE WHEN side='debit' THEN amount ELSE -amount END) delta FROM {SCHEMA}.ledger_entries e GROUP BY e.journal_id HAVING sum(CASE WHEN side='debit' THEN amount ELSE -amount END)<>0) q").fetchone()[0]
  invalid_payments=conn.execute(f"SELECT count(*) FROM {SCHEMA}.payment_intents WHERE status NOT IN ('requires_authorization','authorization_pending','authorized','capture_pending','partially_captured','captured','cancel_pending','canceled','refund_pending','partially_refunded','refunded','failed') OR authorized_amount>amount OR captured_amount>authorized_amount OR refunded_amount>captured_amount").fetchone()[0]
  checksum_count=conn.execute(f"SELECT count(*) FROM {SCHEMA}.schema_migrations WHERE length(trim(checksum))=64").fetchone()[0];rpo=max(0,(datetime.now(timezone.utc)-last_write).total_seconds())
  assert before==after and imbalanced==0 and invalid_payments==0 and checksum_count==MIGRATION_VERSION and rto<1800 and rpo<300
  evidence={"result":"PASS","schema":SCHEMA,"migration_version":MIGRATION_VERSION,"backup_sha256":backup_sha,"schema_data_match":True,"migration_checksums_valid":True,"ledger_balanced":True,"payment_state_valid":True,"outbox_preserved":True,"rpo_seconds":round(rpo,3),"rto_seconds":round(rto,3),"rpo_target_seconds":300,"rto_target_seconds":1800,"encrypted_offsite_claimed":False,"ephemeral_only":True}
  out=ROOT/"build/ops-e09-dr-drill-evidence.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(evidence,sort_keys=True,indent=2)+"\n";out.write_text(payload);out.with_suffix(".json.sha256").write_text(sha256(payload.encode()).hexdigest()+"\n");print("OPS-E09 DR drill: PASS")
 finally:foundation.rollback();conn.close()
if __name__=="__main__":main()
