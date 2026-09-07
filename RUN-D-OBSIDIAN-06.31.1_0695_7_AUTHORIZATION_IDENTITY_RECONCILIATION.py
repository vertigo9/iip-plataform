from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent
REPORTS = REPO / "reports"

AUTH_IN = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R2_1.csv"
IDENTITY_IN = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"

AUTH_OUT = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R3.csv"
MD_OUT = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R3.md"
CHECK_OUT = REPORTS / "PCIP11_0695_7_EXPLICIT_PERSISTENCE_AUTHORIZATION_R3_CHECKS.csv"

KEY = ("Row", "SHA256", "Metric")
IDENTITY_FIELDS = {
    "Metric_ID": "Metric_ID",
    "Knowledge_Evidence_ID": "Knowledge_Evidence_ID",
    "Ticker": "Ticker",
    "Original_Ticker": "Original_Ticker",
    "Period": "Period",
    "Document_Hash": "Document_Hash",
    "Document_ID": "Document_ID",
    "Source_Locator": "Source_Locator",
    "Semantic_Dimension": "Semantic_Dimension",
}

def clean(v):
    return str(v or "").strip()

def sha256_file(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def key(row):
    return tuple(clean(row.get(k)) for k in KEY)

def main():
    print("="*96)
    print("D-OBSIDIAN-06.31.1 — 0695.7 AUTHORIZATION IDENTITY RECONCILIATION")
    print("="*96)
    print("Mode: READ-ONLY RECONCILIATION / NEW AUTHORIZATION ARTIFACT")

    errors=[]
    if not AUTH_IN.exists():
        errors.append(f"missing authorization input: {AUTH_IN}")
    if not IDENTITY_IN.exists():
        errors.append(f"missing identity contract: {IDENTITY_IN}")
    if errors:
        for e in errors: print("[FAIL]",e)
        return 2

    auth=load(AUTH_IN)
    identity=load(IDENTITY_IN)

    print(f"Authorization input rows: {len(auth)}")
    print(f"Identity contract rows:   {len(identity)}")

    if len(auth)!=31: errors.append(f"AUTH_ROWS={len(auth)} expected=31")
    if len(identity)!=31: errors.append(f"IDENTITY_ROWS={len(identity)} expected=31")

    amap={key(r):r for r in auth}
    imap={key(r):r for r in identity}

    if len(amap)!=len(auth): errors.append("AUTH_DUPLICATE_SCOPE_KEYS")
    if len(imap)!=len(identity): errors.append("IDENTITY_DUPLICATE_SCOPE_KEYS")
    if set(amap)!=set(imap): errors.append("AUTH_IDENTITY_SCOPE_MISMATCH")

    checks=[]
    checks.append(("AUTH_31_ROWS", len(auth)==31, len(auth), 31))
    checks.append(("IDENTITY_31_ROWS", len(identity)==31, len(identity), 31))
    checks.append(("EXACT_SCOPE_MATCH", set(amap)==set(imap), len(set(amap)&set(imap)), 31))

    out=[]
    for k in sorted(amap, key=lambda x:int(x[0]) if x[0].isdigit() else x[0]):
        a=dict(amap[k])
        i=imap[k]

        # Identity is sourced only from the proven persistence contract.
        # No identity is inferred, parsed, or manually assigned here.
        for dst, src in IDENTITY_FIELDS.items():
            v=clean(i.get(src))
            if v:
                a[dst]=v

        required=("Metric_ID","Knowledge_Evidence_ID","Ticker","Period","Document_Hash")
        missing=[x for x in required if not clean(a.get(x))]
        if missing:
            errors.append(f"row_{k[0]}:missing_identity:{','.join(missing)}")

        # Preserve the already authorized target/policy fields exactly.
        out.append(a)

    checks.append(("IDENTITY_COMPLETE_31",
                   all(all(clean(r.get(x)) for x in ("Metric_ID","Knowledge_Evidence_ID","Ticker","Period","Document_Hash")) for r in out),
                   sum(all(clean(r.get(x)) for x in ("Metric_ID","Knowledge_Evidence_ID","Ticker","Period","Document_Hash")) for r in out),31))

    mids=[clean(r.get("Metric_ID")) for r in out]
    kids=[clean(r.get("Knowledge_Evidence_ID")) for r in out]
    checks.append(("METRIC_ID_UNIQUE", len(set(mids))==31 and all(mids), len(set(mids)),31))
    checks.append(("KNOWLEDGE_ID_UNIQUE", len(set(kids))==31 and all(kids), len(set(kids)),31))

    # Do not silently alter authorization decisions.
    decision_ok=all(clean(r.get("Authorization_Decision"))=="GRANTED" for r in out)
    persistence_ok=all(clean(r.get("Metric_Persistence_Authorization"))=="GRANTED" for r in out)
    bridge_ok=all(clean(r.get("KnowledgeBridge_Write_Authorization"))=="GRANTED" for r in out)
    vault_ok=all(clean(r.get("Vault_Write_Authorization"))=="GRANTED" for r in out)
    checks += [
        ("AUTHORIZATION_DECISION_PRESERVED", decision_ok, sum(clean(r.get("Authorization_Decision"))=="GRANTED" for r in out),31),
        ("METRIC_PERSISTENCE_AUTH_PRESERVED", persistence_ok, sum(clean(r.get("Metric_Persistence_Authorization"))=="GRANTED" for r in out),31),
        ("KNOWLEDGEBRIDGE_AUTH_PRESERVED", bridge_ok, sum(clean(r.get("KnowledgeBridge_Write_Authorization"))=="GRANTED" for r in out),31),
        ("VAULT_AUTH_PRESERVED", vault_ok, sum(clean(r.get("Vault_Write_Authorization"))=="GRANTED" for r in out),31),
    ]

    # Identity contract itself must be canonical/identity-ready.
    status_ok=all(clean(r.get("Status"))=="IDENTITY_READY" for r in identity)
    checks.append(("IDENTITY_CONTRACT_READY", status_ok, sum(clean(r.get("Status"))=="IDENTITY_READY" for r in identity),31))

    gate=not errors and all(x[1] for x in checks)
    print()
    for name,passed,actual,expected in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: actual={actual} expected={expected}")
    print()
    if not gate:
        print("[STOP] reconciliation failed; no authorization artifact written")
        return 3

    REPORTS.mkdir(exist_ok=True)
    fields=[]
    for r in out:
        for k in r:
            if k not in fields: fields.append(k)
    with AUTH_OUT.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader(); w.writerows(out)

    with CHECK_OUT.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["Check","Status","Actual","Expected"])
        for n,p,a,e in checks: w.writerow([n,"PASS" if p else "FAIL",a,e])

    MD_OUT.write_text(
        "# D-OBSIDIAN-06.31.1 — Authorization Identity Reconciliation\n\n"
        "## Safety\n"
        "- Source authorization artifact was not modified.\n"
        "- Persistence contract was not modified.\n"
        "- Vault was not modified.\n"
        "- No KnowledgeBridge call was made.\n"
        "- This step creates a corrected authorization artifact only after exact "
        "scope and identity checks.\n\n"
        "## Identity source\n"
        f"- `{IDENTITY_IN.name}`\n"
        "- Identity fields are copied from the canonical persistence contract; "
        "nothing is inferred or manually assigned.\n\n"
        "## Result\n"
        f"- Rows: {len(out)}\n"
        f"- Unique Metric_ID: {len(set(mids))}\n"
        f"- Unique Knowledge_Evidence_ID: {len(set(kids))}\n"
        "- Authorization decisions preserved exactly from the prior artifact.\n"
        "- Next step: run the explicit 06.31 authorization gate against this "
        "corrected artifact before controlled execution.\n",
        encoding="utf-8"
    )
    print(f"[PASS] corrected authorization artifact: {AUTH_OUT}")
    print(f"SHA256: {sha256_file(AUTH_OUT)}")
    print("VAULT CHANGED: NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
