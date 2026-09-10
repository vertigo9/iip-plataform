from __future__ import annotations
import csv,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent;REPORTS=ROOT/"reports"
INPUT=REPORTS/"PCIP11_0695_7_AUTHORIZATION_MANIFEST_R2.csv";OUTPUT=REPORTS/"PCIP11_0695_7_PRE_EXECUTION_INTEGRITY_R2"
def sha(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest().upper()
def rows(p):
 with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def v(r,k):return str(r.get(k,"") or "").strip()
rs=rows(INPUT) if INPUT.exists() else []
ok=INPUT.exists() and len(rs)==31 and len({(v(r,"Row"),v(r,"SHA256").upper(),v(r,"Metric")) for r in rs})==31 and all(v(r,"Target_Binding") and v(r,"Scope_Status")=="EXACT_31" for r in rs)
status="PASS" if ok else "BLOCKED";decision="INTEGRITY_VERIFIED" if ok else "INTEGRITY_BLOCKED"
out=[{**r,"Integrity_Status":"INTEGRITY_VERIFIED" if ok else "INTEGRITY_BLOCKED","Stage_Status":status} for r in rs]
fields=list(dict.fromkeys(k for r in out for k in r))
if out:
 with OUTPUT.with_suffix(".csv").open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
OUTPUT.with_suffix(".json").write_text(json.dumps({"stage":"06.26","revision":"R2","status":status,"decision":decision,"input_sha256":sha(INPUT) if INPUT.exists() else "","rows":len(rs),"vault_modified":False},indent=2)+"\n",encoding="utf-8")
print("="*100);print("D-OBSIDIAN-06.26 — 0695.7 PRE-EXECUTION INTEGRITY R2");print("="*100);print(f"[{'PASS' if ok else 'BLOCKED'}] {decision}");print(f"D-OBSIDIAN-06.26: {status}");sys.exit(0 if ok else 3)
