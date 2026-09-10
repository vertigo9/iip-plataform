from __future__ import annotations
import csv,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPORTS=ROOT/"reports";INPUT=REPORTS/"PCIP11_0695_7_FINAL_EXECUTION_READINESS_R2.csv"
print("="*100);print("D-OBSIDIAN-06.30 — 0695.7 CONTROLLED PERSISTENCE R2");print("="*100)
if not INPUT.exists():print("[BLOCKED] readiness input missing");sys.exit(2)
with INPUT.open("r",encoding="utf-8-sig",newline="") as f:rs=list(csv.DictReader(f))
grant=all(str(r.get("Explicit_Grant","")).strip()=="GRANTED" for r in rs)
ready=len(rs)==31 and all(str(r.get("Readiness_Status","")).strip()=="READY_FOR_CONTROLLED_PERSISTENCE" for r in rs)
if not (grant and ready):
 print("[BLOCKED] EXECUTION_NOT_AUTHORIZED")
 print("Persistence executed: NO")
 print("Vault changed: NO")
 sys.exit(3)
print("[STOP] Authorization grant detected, but this R2 package is a pre-release guard only.")
print("Persistence executed: NO")
print("Vault changed: NO")
sys.exit(0)
