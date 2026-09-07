import csv
from pathlib import Path
from collections import defaultdict

REPORT = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv")
OUT_CSV = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_GRANULARITY_AUDIT_R1.csv")
OUT_MD = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_GRANULARITY_AUDIT_R1.md")

FIELDS = [
    "Row",
    "SHA256",
    "FileName",
    "Original_Identity",
    "Original_Ticker",
    "Canonical_Ticker",
    "Lineage",
    "Lineage_Status",
    "Metric",
    "Value_Raw",
    "Value_Parsed",
    "Original_Unit",
    "Resolved_Unit",
    "Scale",
    "Legacy_Period",
    "Resolved_Period",
    "Source_Date",
    "Document_ID",
    "Metric_Evidence_ID",
    "Knowledge_Evidence_ID",
    "Validation_Status",
    "Validation_Reason",
]

def clean(v):
    return (v or "").strip()

def main():
    print("0695 GENERIC METRIC PERSISTENCE — GRANULARITY AUDIT R1")
    print("=" * 115)

    if not REPORT.exists():
        print(f"ERRO: arquivo não encontrado: {REPORT.resolve()}")
        return

    with REPORT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"Rows loaded: {len(rows)}")

    # Create stable grouped keys based on actual source identity.
    def source_key(r):
        return (
            clean(r.get("SHA256")),
            clean(r.get("Metric")),
            clean(r.get("Resolved_Period")),
        )

    groups = defaultdict(list)
    for r in rows:
        groups[source_key(r)].append(r)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    audit_rows = []

    for r in rows:
        key = source_key(r)
        siblings = groups[key]

        # Compare all fields that may explain whether repeated rows are genuinely distinct.
        differing_fields = []
        for field in FIELDS:
            vals = {clean(x.get(field)) for x in siblings}
            if len(vals) > 1:
                differing_fields.append(field)

        # A repeated source tuple with no differing candidate fields is an exact duplicate.
        if len(siblings) == 1:
            classification = "UNIQUE"
            reason = "single candidate for SHA+Metric+Resolved_Period"
        elif not differing_fields:
            classification = "EXACT_DUPLICATE"
            reason = "all inspected source/persistence fields identical inside SHA+Metric+Resolved_Period group"
        else:
            classification = "REPEATED_KEY_REQUIRES_SEMANTIC_REVIEW"
            reason = "same SHA+Metric+Resolved_Period but at least one candidate field differs"

        out = dict(r)
        out["Granularity_Key"] = "||".join(key)
        out["Group_Size"] = str(len(siblings))
        out["Granularity_Classification"] = classification
        out["Differing_Fields"] = "|".join(differing_fields)
        out["Granularity_Reason"] = reason
        audit_rows.append(out)

    # Write audit CSV.
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) + [
        "Granularity_Key",
        "Group_Size",
        "Granularity_Classification",
        "Differing_Fields",
        "Granularity_Reason",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    # Console summary.
    counts = defaultdict(int)
    for r in audit_rows:
        counts[r["Granularity_Classification"]] += 1

    print("\nCLASSIFICATION")
    print("-" * 115)
    for k in ("UNIQUE", "EXACT_DUPLICATE", "REPEATED_KEY_REQUIRES_SEMANTIC_REVIEW"):
        print(f"{k:40}: {counts[k]}")

    print("\nREPEATED GROUPS")
    print("-" * 115)
    if not duplicate_groups:
        print("None")
    else:
        for i, (key, items) in enumerate(duplicate_groups.items(), 1):
            print(f"\nGROUP {i} — {len(items)} rows")
            print(f"SHA256   : {key[0]}")
            print(f"Metric   : {key[1]}")
            print(f"Period   : {key[2]}")

            differing_fields = []
            for field in FIELDS:
                vals = {clean(x.get(field)) for x in items}
                if len(vals) > 1:
                    differing_fields.append(field)

            print(f"Differing fields: {', '.join(differing_fields) if differing_fields else 'NONE — exact duplicate'}")

            for n, r in enumerate(items, 1):
                print(f"\n  OCCURRENCE {n}")
                for field in FIELDS:
                    if field in r:
                        print(f"    {field:22}: {clean(r.get(field))}")

    # Inspect blocked records explicitly.
    blocked = [r for r in rows if clean(r.get("Validation_Status")).upper() == "BLOCKED"]
    print("\nBLOCKED CANDIDATES")
    print("-" * 115)
    if not blocked:
        print("None")
    else:
        for i, r in enumerate(blocked, 1):
            print(
                f"{i:02d}. Row={clean(r.get('Row'))} | "
                f"ticker={clean(r.get('Canonical_Ticker'))} | "
                f"metric={clean(r.get('Metric'))} | "
                f"value_raw={clean(r.get('Value_Raw'))} | "
                f"value_parsed={clean(r.get('Value_Parsed'))} | "
                f"unit={clean(r.get('Resolved_Unit'))} | "
                f"scale={clean(r.get('Scale'))} | "
                f"period={clean(r.get('Resolved_Period'))}"
            )
            print(f"    Validation_Reason: {clean(r.get('Validation_Reason'))}")
            print(f"    FileName: {clean(r.get('FileName'))}")
            print(f"    SHA256: {clean(r.get('SHA256'))}")

    # Markdown report.
    md = []
    md.append("# 0695 Generic Metric Persistence — Granularity Audit R1")
    md.append("")
    md.append(f"- Input rows: **{len(rows)}**")
    md.append(f"- Unique: **{counts['UNIQUE']}**")
    md.append(f"- Exact duplicates: **{counts['EXACT_DUPLICATE']}**")
    md.append(f"- Repeated keys requiring semantic review: **{counts['REPEATED_KEY_REQUIRES_SEMANTIC_REVIEW']}**")
    md.append("")
    md.append("## Repeated groups")
    if not duplicate_groups:
        md.append("- None")
    else:
        for i, (key, items) in enumerate(duplicate_groups.items(), 1):
            md.append(f"### Group {i}")
            md.append(f"- SHA256: `{key[0]}`")
            md.append(f"- Metric: `{key[1]}`")
            md.append(f"- Resolved_Period: `{key[2]}`")
            differing_fields = []
            for field in FIELDS:
                vals = {clean(x.get(field)) for x in items}
                if len(vals) > 1:
                    differing_fields.append(field)
            md.append(f"- Rows: **{len(items)}**")
            md.append(f"- Differing fields: `{', '.join(differing_fields) if differing_fields else 'NONE — exact duplicate'}`")
            for n, r in enumerate(items, 1):
                md.append(f"#### Occurrence {n}")
                for field in FIELDS:
                    md.append(f"- `{field}`: `{clean(r.get(field))}`")
    md.append("")
    md.append("## Blocked candidates")
    if not blocked:
        md.append("- None")
    else:
        for r in blocked:
            md.append(
                f"- Row `{clean(r.get('Row'))}` | "
                f"`{clean(r.get('Canonical_Ticker'))}` | "
                f"`{clean(r.get('Metric'))}` | "
                f"raw=`{clean(r.get('Value_Raw'))}` | "
                f"parsed=`{clean(r.get('Value_Parsed'))}` | "
                f"unit=`{clean(r.get('Resolved_Unit'))}` | "
                f"scale=`{clean(r.get('Scale'))}` | "
                f"period=`{clean(r.get('Resolved_Period'))}`"
            )
            md.append(f"  - Reason: `{clean(r.get('Validation_Reason'))}`")
            md.append(f"  - File: `{clean(r.get('FileName'))}`")
            md.append(f"  - SHA256: `{clean(r.get('SHA256'))}`")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\nCSV audit: {OUT_CSV.resolve()}")
    print(f"MD audit : {OUT_MD.resolve()}")
    print("Persistence executed     : NO")
    print("KnowledgeBridge executed : NO")
    print("Vault changed            : NO")

if __name__ == "__main__":
    main()
