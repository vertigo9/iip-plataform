import csv
from pathlib import Path
from collections import defaultdict

REPORT = Path(r"reports\0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv")
OUT_MD = Path(r"reports\AUDIT_0695_METRIC_IDENTITY_SOURCE_R1.md")

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
    "Relevant_Facts_Count",
    "Relevant_Facts",
    "Validation_Status",
    "Validation_Reason",
]

def clean(v):
    return (v or "").strip()

def source_key(row):
    return (
        clean(row.get("SHA256")),
        clean(row.get("Metric")),
        clean(row.get("Resolved_Period")),
    )

def compare_fields(rows):
    differing = []
    for field in FIELDS:
        values = {clean(r.get(field)) for r in rows}
        if len(values) > 1:
            differing.append(field)
    return differing

def classify(rows):
    differing = compare_fields(rows)
    if len(rows) == 1:
        return "UNIQUE", differing
    if not differing:
        return "EXACT_DUPLICATE", differing

    value_set = {clean(r.get("Value_Parsed")) for r in rows}
    if len(value_set) > 1:
        return "DISTINCT_VALUE_SAME_ID", differing

    return "REPEATED_CANDIDATE_SAME_VALUE", differing

def main():
    print("0695 METRIC IDENTITY — SOURCE AUDIT R1")
    print("=" * 110)

    if not REPORT.exists():
        print(f"ERRO: arquivo não encontrado: {REPORT.resolve()}")
        return

    with REPORT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"Rows loaded: {len(rows)}")

    groups = defaultdict(list)
    for row in rows:
        groups[source_key(row)].append(row)

    repeated = {k: v for k, v in groups.items() if len(v) > 1}

    print(f"Repeated SHA+Metric+Resolved_Period groups: {len(repeated)}")

    md = [
        "# 0695 Metric Identity — Source Audit R1",
        "",
        f"- Input: `{REPORT}`",
        f"- Rows: **{len(rows)}**",
        f"- Repeated source groups: **{len(repeated)}**",
        "",
    ]

    if not repeated:
        print("No repeated groups found.")
        OUT_MD.write_text("\n".join(md), encoding="utf-8")
        print(f"MD: {OUT_MD.resolve()}")
        return

    for index, (key, items) in enumerate(repeated.items(), 1):
        classification, differing = classify(items)

        print(f"\nGROUP {index}")
        print("-" * 110)
        print(f"SHA256             : {key[0]}")
        print(f"Metric             : {key[1]}")
        print(f"Resolved_Period    : {key[2]}")
        print(f"Classification     : {classification}")
        print(f"Differing fields   : {', '.join(differing) if differing else 'NONE'}")

        md.extend([
            f"## Group {index}",
            "",
            f"- SHA256: `{key[0]}`",
            f"- Metric: `{key[1]}`",
            f"- Resolved_Period: `{key[2]}`",
            f"- Classification: **{classification}**",
            f"- Differing fields: `{', '.join(differing) if differing else 'NONE'}`",
            "",
        ])

        for occurrence, row in enumerate(items, 1):
            print(f"\n  OCCURRENCE {occurrence}")
            for field in FIELDS:
                value = clean(row.get(field))
                if field == "Relevant_Facts":
                    print(f"    {field:22}:")
                    print(f"      {value}")
                else:
                    print(f"    {field:22}: {value}")

            md.append(f"### Occurrence {occurrence}")
            for field in FIELDS:
                value = clean(row.get(field))
                md.append(f"- `{field}`: `{value}`")
            md.append("")

    # Extra ID-level collision analysis.
    metric_ids = defaultdict(list)
    knowledge_ids = defaultdict(list)
    for row in rows:
        mid = clean(row.get("Metric_Evidence_ID"))
        kid = clean(row.get("Knowledge_Evidence_ID"))
        if mid:
            metric_ids[mid].append(row)
        if kid:
            knowledge_ids[kid].append(row)

    metric_collisions = {
        k: v for k, v in metric_ids.items()
        if len({clean(x.get("Value_Parsed")) for x in v}) > 1
    }
    knowledge_collisions = {
        k: v for k, v in knowledge_ids.items()
        if len({clean(x.get("Value_Parsed")) for x in v}) > 1
    }

    print("\nID COLLISION WITH DISTINCT VALUES")
    print("-" * 110)
    print(f"Metric_Evidence_ID collisions   : {len(metric_collisions)}")
    print(f"Knowledge_Evidence_ID collisions: {len(knowledge_collisions)}")

    md.extend([
        "## ID collisions with distinct values",
        "",
        f"- Metric_Evidence_ID collisions: **{len(metric_collisions)}**",
        f"- Knowledge_Evidence_ID collisions: **{len(knowledge_collisions)}**",
        "",
    ])

    if metric_collisions:
        md.append("### Metric_Evidence_ID")
        for key, items in metric_collisions.items():
            md.append(f"#### `{key}`")
            for row in items:
                md.append(
                    f"- Row `{clean(row.get('Row'))}` | "
                    f"value `{clean(row.get('Value_Parsed'))}` | "
                    f"source `{clean(row.get('FileName'))}`"
                )
            md.append("")

    if knowledge_collisions:
        md.append("### Knowledge_Evidence_ID")
        for key, items in knowledge_collisions.items():
            md.append(f"#### `{key}`")
            for row in items:
                md.append(
                    f"- Row `{clean(row.get('Row'))}` | "
                    f"value `{clean(row.get('Value_Parsed'))}` | "
                    f"source `{clean(row.get('FileName'))}`"
                )
            md.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\nMD output: {OUT_MD.resolve()}")
    print("Persistence executed     : NO")
    print("KnowledgeBridge executed : NO")
    print("Vault changed            : NO")

if __name__ == "__main__":
    main()
