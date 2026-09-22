from __future__ import annotations
import json,os,re,subprocess
from pathlib import Path

DIGEST=re.compile(r"^sha256:[0-9a-f]{64}$")
BASE_IMAGE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9./:_-]*@sha256:[0-9a-f]{64}$")
def validate(env:dict[str,str]|None=None)->dict:
 env=env or os.environ;root=Path(__file__).resolve().parents[1];digest=env.get("NURION_PG_IMAGE_DIGEST","")
 if not DIGEST.fullmatch(digest):raise ValueError("immutable sha256 image digest required")
 if env.get("NURION_PG_ENV") not in {"staging","production"}:raise ValueError("deploy environment required")
 base_image=env.get("NURION_PG_BASE_IMAGE","")
 if not BASE_IMAGE.fullmatch(base_image):raise ValueError("immutable base image reference required")
 manifest=(root/"deploy/k8s/deployment.yaml").read_text();forbidden=("password:","secret_key:","test_sk_","live_sk_")
 if any(x in manifest.lower() for x in forbidden):raise ValueError("manifest contains a secret")
 required=("readOnlyRootFilesystem: true","runAsNonRoot: true","/health/startup","/health/ready","/health/live","@${NURION_PG_IMAGE_DIGEST}")
 if not all(x in manifest for x in required):raise ValueError("deployment hardening drift")
 dockerfile=(root/"Dockerfile").read_text()
 if "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}" not in dockerfile:raise ValueError("base image must be supplied by immutable release evidence")
 if "pg_advisory_xact_lock" not in (root/"src/nurion_pg/storage/postgres.py").read_text():raise ValueError("migration lock contract missing")
 policy=json.loads((root/"deploy/environments.json").read_text());return {"result":"PASS","environment":env["NURION_PG_ENV"],"image_digest":digest,"base_image":base_image,"migration_steps":len(policy["migration_order"]),"external_deployment_performed":False}
if __name__=="__main__":print(json.dumps(validate(),sort_keys=True))
