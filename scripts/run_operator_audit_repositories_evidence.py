from datetime import UTC,datetime
from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.operator_audit_repositories import MemoryOperatorAuditRepository,SQLiteMemoryOperatorAuditRepository,repository_evidence
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 m=MemoryOperatorAuditRepository();s=SQLiteMemoryOperatorAuditRepository();now=datetime(2026,9,18,tzinfo=UTC)
 for n in (1,2):
  args=(f"synthetic:audit-checkpoint:{n}",h(f"checkpoint:{n}".encode()),h(f"report:{n}".encode()),f"synthetic:key:{n}",now);m.append(*args);s.append(*args)
 e=repository_evidence(m,s);o=ROOT/"build/synthetic-operator-audit-repositories-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(e,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");s.close();print("synthetic operator audit repositories: PASS",d)
if __name__=="__main__":main()
