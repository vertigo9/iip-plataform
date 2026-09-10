from __future__ import annotations
import csv, re, hashlib
from pathlib import Path
from collections import Counter, defaultdict

REPO=Path(__file__).resolve().parent
REPORTS=REPO/"reports"
AUTH=REPORTS/"PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv"
GENERIC=REPORTS/"0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv"
OUT=REPORTS/"PCIP11_0695_7_IDENTITY_RECONCILIATION_GATE_R2.csv"
MD=REPORTS/"PCIP11_0695_7_IDENTITY_RECONCILIATION_GATE_R2.md"

def clean(v): return str(v or "").strip()
def load(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))
def key(r): return (clean(r.get("Row")),clean(r.get("SHA256")),clean(r.get("Metric")))
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1048576),b""): h.update(c)
    return h.hexdigest()

def main():
    print("="*96)
    print("D-OBSIDIAN-06.31.1 R2 — 0695.7 IDENTITY RECONCILIATION GATE")
    print("="*96)
    print("Mode: READ-ONLY / FAIL-CLOSED")
    errors=[]
    for p in (AUTH,GENERIC):
        if not p.exists(): errors.append(f"MISSING:{p.name}")
    if errors:
        for e in errors: print("[FAIL]",e)
        return 2

    auth=load(AUTH); generic=load(GENERIC)
    print(f"Authorization rows : {len(auth)}")
    print(f"Generic evidence rows: {len(generic)}")
    if len(auth)!=31: errors.append(f"AUTH_ROWS:{len(auth)}")
    if len(generic)!=31: errors.append(f"GENERIC_ROWS:{len(generic)}")

    gmap=defaultdict(list)
    for r in generic: gmap[key(r)].append(r)

    results=[]
    for a in auth:
        matches=gmap.get(key(a),[])
        if len(matches)!=1:
            status="BLOCKED"
            reason="NO_UNIQUE_CANONICAL_MATCH" if not matches else "AMBIGUOUS_CANONICAL_MATCH"
            results.append({**a,"Reconciliation_Status":status,"Reconciliation_Reason":reason})
            continue
        g=matches[0]
        # Copy only fields that are explicitly present in the canonical evidence source.
        r=dict(a)
        for dst,src in {
            "Metric_ID":"Metric_Evidence_ID",
            "Knowledge_Evidence_ID":"Knowledge_Evidence_ID",
            "Ticker":"Canonical_Ticker",
            "Original_Ticker":"Original_Ticker",
            "Resolved_Period":"Resolved_Period",
            "Document_ID":"Document_ID",
            "Document_Hash":"SHA256",
            "Source_Locator":"FileName",
            "Lineage":"Lineage",
        }.items():
            if clean(g.get(src)): r[dst]=g[src]
        required=("Metric_ID","Knowledge_Evidence_ID","Ticker","Resolved_Period","Document_Hash")
        missing=[x for x in required if not clean(r.get(x))]
        # Do not promote rows that canonical evidence itself marked BLOCKED.
        if clean(g.get("Validation_Status")).upper()!="READY" or missing:
            status="BLOCKED"
            reason="CANONICAL_SOURCE_BLOCKED" if clean(g.get("Validation_Status")).upper()!="READY" else "MISSING_IDENTITY"
        else:
            status="RECONCILED"
            reason=""
        r["Reconciliation_Status"]=status
        r["Reconciliation_Reason"]=reason
        results.append(r)

    counts=Counter(r["Reconciliation_Status"] for r in results)
    print(f"RECONCILED : {counts.get('RECONCILED',0)}")
    print(f"BLOCKED    : {counts.get('BLOCKED',0)}")

    # Identity uniqueness is checked only among reconciled records.
    mids=[r["Metric_ID"] for r in results if r["Reconciliation_Status"]=="RECONCILED"]
    kids=[r["Knowledge_Evidence_ID"] for r in results if r["Reconciliation_Status"]=="RECONCILED"]
    print(f"Unique reconciled Metric_IDs: {len(set(mids))}/{len(mids)}")
    print(f"Unique reconciled Knowledge IDs: {len(set(kids))}/{len(kids)}")

    # This gate NEVER converts partial reconciliation into authorization.
    if len(results)!=31 or counts.get("BLOCKED",0) or len(set(mids))!=len(mids) or len(set(kids))!=len(kids):
        print("[STOP] identity reconciliation is incomplete; no authorization artifact created")
        print("VAULT CHANGED: NO")
        return 3

    fields=[]
    for r in results:
        for k in r:
            if k not in fields: fields.append(k)
    with OUT.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(results)
    MD.write_text(
        "# 06.31.1 R2 — Identity Reconciliation Gate\n\n"
        "- Mode: READ-ONLY / FAIL-CLOSED\n"
        f"- Authorization scope: {len(auth)} rows\n"
        f"- Canonical evidence scope: {len(generic)} rows\n"
        f"- Reconciled: {counts.get('RECONCILED',0)}\n"
        f"- Blocked: {counts.get('BLOCKED',0)}\n"
        "- No authorization is granted by this gate.\n"
        "- Vault unchanged.\n",encoding="utf-8")
    print(f"[PASS] reconciliation artifact: {OUT}")
    print("VAULT CHANGED: NO")
    return 0

if __name__=="__main__": raise SystemExit(main())
