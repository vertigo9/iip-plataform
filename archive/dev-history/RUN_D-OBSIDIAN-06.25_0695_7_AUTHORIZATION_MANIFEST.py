from __future__ import annotations
import csv,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent; REPORTS=ROOT/"reports"
INPUT=REPORTS/"PCIP11_0695_7_TARGET_BINDING_R2.csv"; OUTPUT=REPORTS/"PCIP11_0695_7_AUTHORIZATION_MANIFEST_R2"
def sha(p):
 h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest().upper()
def rows(p):
 with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def v(r,k):return str(r.get(k,"") or "").strip()
print("="*100);print("D-OBSIDIAN-06.25 — 0695.7 AUTHORIZATION MANIFEST R2");print("="*100)
if not INPUT.exists():print("[BLOCKED] input missing:",INPUT);sys.exit(2)
rs=rows(INPUT); ok=len(rs)==31 and all(v(r,"Target_Status")=="TARGET_EXPLICITLY_BOUND" and v(r,"Target_Binding") for r in rs)
status="PASS" if ok else "BLOCKED";decision="AUTHORIZATION_MANIFEST_READY" if ok else "AUTHORIZATION_MANIFEST_BLOCKED"
out=[]
for r in rs:
 x=dict(r);x["Scope_Status"]="EXACT_31" if len(rs)==31 else "SCOPE_ERROR";x["Authorization_Status"]="NOT_GRANTED";x["Explicit_Grant"]="NOT_GRANTED";x["Stage_Status"]=status;out.append(x)
fields=list(dict.fromkeys(k for r in out for k in r))
with OUTPUT.with_suffix(".csv").open("w",encoding="utf-8-sig",newline="") as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
OUTPUT.with_suffix(".json").write_text(json.dumps({"stage":"06.25","revision":"R2","status":status,"decision":decision,"input_sha256":sha(INPUT),"rows":len(rs),"authorization":"NOT_GRANTED","vault_modified":False},indent=2)+"\n",encoding="utf-8")
print(f"[{'PASS' if ok else 'BLOCKED'}] {decision}");print("Authorization: NOT GRANTED");print(f"D-OBSIDIAN-06.25: {status}");sys.exit(0 if ok else 3)
