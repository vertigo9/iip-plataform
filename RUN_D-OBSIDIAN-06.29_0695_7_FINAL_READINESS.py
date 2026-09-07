from __future__ import annotations
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPORTS=ROOT/"reports";INPUT=REPORTS/"PCIP11_0695_7_ATOMIC_DRY_RUN_R2.csv";OUTPUT=REPORTS/"PCIP11_0695_7_FINAL_EXECUTION_READINESS_R2"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def rows(p):
 with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def v(r,k):return str(r.get(k,"") or "").strip()
rs=rows(INPUT) if INPUT.exists() else [];ok=INPUT.exists() and len(rs)==31 and all(v(r,"Dry_Run_Status")=="ATOMIC_DRY_RUN_READY" for r in rs)
status="PASS" if ok else "BLOCKED";decision="READY_FOR_CONTROLLED_PERSISTENCE" if ok else "NOT_READY"
out=[{**r,"Readiness_Status":"READY_FOR_CONTROLLED_PERSISTENCE" if ok else "NOT_READY","Stage_Status":status,"Explicit_Grant":"NOT_GRANTED"} for r in rs];fields=list(dict.fromkeys(k for r in out for k in r))
if out:
 with OUTPUT.with_suffix(".csv").open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
OUTPUT.with_suffix(".json").write_text(json.dumps({"stage":"06.29","status":status,"decision":decision,"input_sha256":sha(INPUT) if INPUT.exists() else "","rows":len(rs),"authorization":"NOT_GRANTED","vault_modified":False},indent=2)+"\n",encoding="utf-8")
print(f"D-OBSIDIAN-06.29: {status}");sys.exit(0 if ok else 3)
