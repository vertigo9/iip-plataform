from __future__ import annotations
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPORTS=ROOT/"reports";INPUT=REPORTS/"PCIP11_0695_7_PRE_EXECUTION_INTEGRITY_R2.csv";OUTPUT=REPORTS/"PCIP11_0695_7_IDEMPOTENCY_SIMULATION_R2"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def rows(p):
 with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def v(r,k):return str(r.get(k,"") or "").strip()
rs=rows(INPUT) if INPUT.exists() else [];ok=INPUT.exists() and len(rs)==31 and all(v(r,"Integrity_Status")=="INTEGRITY_VERIFIED" for r in rs)
status="PASS" if ok else "BLOCKED";decision="SIMULATION_READY" if ok else "SIMULATION_BLOCKED"
out=[{**r,"Simulation_Status":"SIMULATION_READY" if ok else "SIMULATION_BLOCKED","Stage_Status":status} for r in rs];fields=list(dict.fromkeys(k for r in out for k in r))
if out:
 with OUTPUT.with_suffix(".csv").open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
OUTPUT.with_suffix(".json").write_text(json.dumps({"stage":"06.27","status":status,"decision":decision,"input_sha256":sha(INPUT) if INPUT.exists() else "","rows":len(rs),"vault_modified":False},indent=2)+"\n",encoding="utf-8")
print(f"D-OBSIDIAN-06.27: {status}");sys.exit(0 if ok else 3)
