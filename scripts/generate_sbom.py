import importlib.metadata,json
from hashlib import sha256
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
components=sorted(({"type":"library","name":d.metadata["Name"],"version":d.version} for d in importlib.metadata.distributions() if d.metadata.get("Name")),key=lambda x:(x["name"].lower(),x["version"]))
value={"bomFormat":"CycloneDX","specVersion":"1.5","version":1,"metadata":{"component":{"type":"application","name":"nurion-pg"}},"components":components};out=ROOT/"build/nurion-pg-sbom.cdx.json";out.parent.mkdir(exist_ok=True);payload=json.dumps(value,sort_keys=True,indent=2)+"\n";out.write_text(payload);out.with_suffix(".json.sha256").write_text(sha256(payload.encode()).hexdigest()+"\n");print("SBOM:",len(components),"components")
