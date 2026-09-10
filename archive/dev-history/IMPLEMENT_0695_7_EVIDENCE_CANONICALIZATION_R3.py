from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

SRC = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R2.csv"
RES = REPORTS / "PCIP11_0695_7_CONFLICT_RESOLUTION_R2.csv"

OUT_CSV = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R3.csv"
OUT_MD = REPORTS / "PCIP11_0695_7_EVIDENCE_CANONICALIZATION_R3.md"

def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def main():
    rows = read_csv(SRC)
    resolutions = read_csv(RES)

    resolution = next(
        (r for r in resolutions
         if r.get("Canonical_Ticker") == "PCIP11"
         and r.get("Resolved_Period") == "2024-01"
         and r.get("Metric") == "dividend_yield_annualized"),
        None
    )
    if resolution is None or resolution.get("Resolution_Status") != "RESOLVED":
        raise RuntimeError("Resolução R2 esperada não encontrada ou não está RESOLVED.")

    out = []
    conflict_seen = False

    for r in rows:
        if (
            r.get("Canonical_Ticker") == "PCIP11"
            and r.get("Resolved_Period") == "2024-01"
            and r.get("Metric") == "dividend_yield_annualized"
        ):
            if not conflict_seen:
                nr = dict(r)
                nr["Value_Parsed"] = resolution["Resolved_Value"]
                nr["Canonicalization_Status"] = "CANONICAL"
                nr["Canonicalization_Reason"] = "semantic_disambiguation_resolved"
                nr["Distinct_Value_Count"] = "1"
                nr["Distinct_Values"] = resolution["Resolved_Value"]
                nr["Persistence_Eligible"] = "YES"
                nr["Conflict_Resolution_Status"] = "RESOLVED"
                nr["Conflict_Resolution_Type"] = resolution["Resolution_Type"]
                nr["Conflict_Rejected_Value"] = resolution["Rejected_Value"]
                nr["Conflict_Evidence_SHA256"] = resolution["Evidence_SHA256"]
                nr["Conflict_Evidence_Pages"] = resolution["Evidence_Pages"]
                nr["Conflict_Selected_Context"] = resolution["Selected_Context"]
                nr["Conflict_Rejected_Context"] = resolution["Rejected_Context"]
                nr["Source_Rows"] = resolution.get("Source_Rows", nr.get("Source_Rows", "17,18,21"))
                out.append(nr)
                conflict_seen = True
            continue
        out.append(dict(r))

    canonical = sum(r.get("Canonicalization_Status") == "CANONICAL" for r in out)
    conflict = sum(r.get("Canonicalization_Status") == "CONFLICT" for r in out)
    review = sum(r.get("Canonicalization_Status") == "REVIEW" for r in out)
    incomplete = sum(not (r.get("Semantic_Identity_Key") or "").strip() for r in out)
    exact_dup = sum(
        r.get("Canonicalization_Reason") == "unique_or_exact_duplicate"
        and int(r.get("Source_Row_Count") or 1) > 1
        for r in out
    )

    # Preserve all source rows represented by the canonical observations.
    fields = []
    for r in out:
        for k in r:
            if k not in fields:
                fields.append(k)

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)

    md = f"""# 0695.7 Evidence Canonicalization R3

R3 applies only the formally resolved R2 semantic disambiguation to the
`PCIP11 / 2024-01 / dividend_yield_annualized` conflict. Other canonical
observations are preserved from R2.

## Result

- Source canonicalization rows consumed: {len(rows)}
- Canonical observations: {len(out)}
- CANONICAL / eligible: {canonical}
- CONFLICT / blocked: {conflict}
- REVIEW / blocked: {review}
- Incomplete identity rows: {incomplete}

## Applied resolution

- Ticker: `PCIP11`
- Period: `2024-01`
- Metric: `dividend_yield_annualized`
- Resolved value: `{resolution["Resolved_Value"]}%`
- Rejected value: `{resolution["Rejected_Value"]}%`
- Type: `{resolution["Resolution_Type"]}`
- Evidence SHA-256: `{resolution["Evidence_SHA256"]}`
- Evidence pages: `{resolution["Evidence_Pages"]}`

## Safety

- Persistence executed: NO
- KnowledgeBridge executed: NO
- Vault changed: NO
- This component performs canonicalization only.
"""

    OUT_MD.write_text(md, encoding="utf-8")

    print("0695.7 EVIDENCE CANONICALIZATION R3")
    print("=" * 88)
    print(f"R2 observations consumed      : {len(rows)}")
    print(f"Canonical observations        : {len(out)}")
    print(f"CANONICAL / eligible          : {canonical}")
    print(f"CONFLICT / blocked            : {conflict}")
    print(f"REVIEW / blocked              : {review}")
    print(f"Incomplete identity rows      : {incomplete}")
    print(f"Resolved conflict value       : {resolution['Resolved_Value']}%")
    print(f"Resolution type               : {resolution['Resolution_Type']}")
    print(f"CSV                           : {OUT_CSV}")
    print(f"MD                            : {OUT_MD}")
    print()
    print("Persistence executed          : NO")
    print("KnowledgeBridge executed      : NO")
    print("Vault changed                 : NO")

if __name__ == "__main__":
    main()
