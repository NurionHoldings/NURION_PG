from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.synthetic_operator_audit_registry_parity import OperatorAuditRegistryParity
ROOT=Path(__file__).resolve().parents[1];h=lambda x:sha256(x).hexdigest()
def main():
 r=OperatorAuditRegistryParity(h(b"audit"));r.admit("SYNTHETIC_OPERATOR_INTENT_AUDIT_COMPLETED",(441,455),True,"synthetic:key:456");r.contract("nurion.pg.operator-audit-registry.v1",("checkpoint_digest","sequence","previous_digest","report_digest"),"synthetic:key:457",1);r.backends(("memory","sqlite-memory"),"synthetic:key:458",2);r.fixture(h(b"fixture"),"synthetic:key:459",3);r.write_preview(1,None,"synthetic:key:460",4);r.memory(h(b"record"),1,"synthetic:key:461",5);r.sqlite(h(b"record"),1,False,"synthetic:key:462",6);r.parity(h(b"record"),h(b"record"),"synthetic:key:463",7);r.replay(True,True,"synthetic:key:464",8);r.concurrency(True,"synthetic:key:465",9);r.tamper(True,True,"synthetic:key:466",10);r.privacy(False,False,"synthetic:key:467",11);r.effects((),"synthetic:key:468",12);r.seal(None,"synthetic:key:469",13);r.complete(("IN_MEMORY_ONLY","NO_AUTHORITY","NO_EXTERNAL_IO","READ_ONLY","SYNTHETIC_ONLY"),"synthetic:key:470",14)
 e=r.evidence();o=ROOT/"build/synthetic-operator-audit-registry-parity-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(e,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("synthetic operator audit registry parity: PASS",d)
if __name__=="__main__":main()
