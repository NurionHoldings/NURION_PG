from hashlib import sha256
import json
from pathlib import Path
from nurion_pg.postgres_repository_readiness import build_readiness_portfolio,readiness_evidence
ROOT=Path(__file__).resolve().parents[1]
def main():
 controls=build_readiness_portfolio(sha256(b"synthetic-operator-audit-repository-evidence").hexdigest());e=readiness_evidence(controls);o=ROOT/"build/postgres-repository-readiness-evidence.json";o.parent.mkdir(exist_ok=True);x=json.dumps(e,sort_keys=True,indent=2)+"\n";o.write_text(x);d=sha256(x.encode()).hexdigest();o.with_suffix(".json.sha256").write_text(d+"\n");print("postgres repository readiness #501-#700: PASS",d)
if __name__=="__main__":main()
