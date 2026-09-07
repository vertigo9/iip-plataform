from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "reports"

CANDIDATES = REPORTS / "PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv"
RESOLUTION = REPORTS / "PCIP11_SEMANTIC_RESOLUTION_0695_6R4R4.csv"
OUTPUT = REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT_R1.csv"
SUMMARY = REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT_R1.md"


def s(value) -> str:
    return "" if value is None else str(value).strip()


def norm_num(value: str) -> str:
    x = s(value)
    if not x:
        return ""
    return x.replace(",", ".")


def row_key(row: dict) -> tuple[str, str, str, str]:
    return (
        s(row.get("SHA256")),
        s(row.get("Metric")),
        norm_num(row.get("Value")),
        s(row.get("Original_Unit")),
    )


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Missing input: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    candidates = read_csv(CANDIDATES)
    resolved = read_csv(RESOLUTION)

    print("0695.7 R1 - DOMAIN ASSESSMENT FROM 6R4R4")
    print("=" * 72)
    print(f"Candidates 6R2 : {len(candidates)}")
    print(f"Resolution 6R4R4: {len(resolved)}")

    if len(candidates) != len(resolved):
        print("WARNING: row totals differ; matching by composite key.")

    resolved_groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in resolved:
        resolved_groups[row_key(row)].append(row)

    output_rows = []
    counters = Counter()
    unmatched = 0

    for idx, cand in enumerate(candidates, 1):
        key = (
            s(cand.get("SHA256")),
            s(cand.get("Metric")),
            norm_num(cand.get("Value")),
            s(cand.get("Unit")),
        )

        matches = resolved_groups.get(key, [])
        if matches:
            rr = matches.pop(0)
        else:
            unmatched += 1
            rr = {}

        resolution_status = s(rr.get("Resolution_Status"))
        promotion_action = s(rr.get("Promotion_Action"))
        lineage = s(rr.get("Lineage"))
        resolved_unit = s(rr.get("Resolved_Unit"))
        scale_state = s(rr.get("Scale_State"))
        scale_confidence = s(rr.get("Scale_Confidence"))
        plausibility = s(rr.get("Plausibility"))
        period = s(rr.get("Period"))

        if promotion_action == "ELIGIBLE_FOR_PROMOTION_GATE":
            domain_status = "ELIGIBLE"
            reason = "6R4R4_ELIGIBLE_FOR_PROMOTION_GATE"
        elif promotion_action == "HOLD_UNIT_SCALE":
            domain_status = "REVIEW"
            reason = "6R4R4_HOLD_UNIT_SCALE"
        elif promotion_action == "HOLD_CONFLICT":
            domain_status = "HOLD"
            reason = "6R4R4_HOLD_CONFLICT"
        elif promotion_action:
            domain_status = "REVIEW"
            reason = f"6R4R4_{promotion_action}"
        else:
            domain_status = "HOLD"
            reason = "NO_6R4R4_MATCH"

        counters[domain_status] += 1

        output_rows.append({
            "Row": idx,
            "Historical_ID": s(cand.get("Historical_ID")),
            "SHA256": s(cand.get("SHA256")),
            "FileName": s(cand.get("FileName")),
            "Original_Identity": s(cand.get("Identity_Class")),
            "Lineage": lineage,
            "Document_Role": s(cand.get("Document_Role")),
            "Metric": s(cand.get("Metric")),
            "Value": s(cand.get("Value")),
            "Original_Unit": s(cand.get("Unit")),
            "Resolved_Unit": resolved_unit,
            "Scale": s(rr.get("Scale")) or s(cand.get("Scale")),
            "Scale_State": scale_state,
            "Scale_Confidence": scale_confidence,
            "Period": period or s(cand.get("Period")),
            "Plausibility": plausibility,
            "Resolution_Status": resolution_status,
            "Promotion_Action": promotion_action,
            "Domain_Status": domain_status,
            "Domain_Reason": reason,
            "Domain_Confidence_Source": "6R4R4 semantic resolution; no synthetic numeric confidence",
            "Evidence_Text": s(cand.get("Evidence_Text")),
        })

    REPORTS.mkdir(parents=True, exist_ok=True)
    fields = list(output_rows[0].keys()) if output_rows else []

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    lines = [
        "# PCIP11 - 0695.7 R1 Domain Assessment",
        "",
        f"- Candidates: {len(candidates)}",
        f"- Resolution rows: {len(resolved)}",
        f"- ELIGIBLE: {counters['ELIGIBLE']}",
        f"- REVIEW: {counters['REVIEW']}",
        f"- HOLD: {counters['HOLD']}",
        f"- Unmatched: {unmatched}",
        "",
        "## Rule",
        "",
        "- 0695.6R4R4 is the authoritative semantic-resolution input for this adapter.",
        "- No synthetic numeric confidence is created from HIGH/LOW.",
        "- CVBI11 -> PCIP11 lineage remains explicit.",
        "- This stage still does not promote metrics or modify the Vault.",
    ]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"ELIGIBLE       : {counters['ELIGIBLE']}")
    print(f"REVIEW         : {counters['REVIEW']}")
    print(f"HOLD           : {counters['HOLD']}")
    print(f"Unmatched      : {unmatched}")
    print(f"Output         : {OUTPUT}")
    print(f"Summary        : {SUMMARY}")
    print("")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()
