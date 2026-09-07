from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "reports"

INPUT = REPORTS / "PCIP11_0695_7_DOMAIN_ASSESSMENT_R1.csv"
OUTPUT = REPORTS / "PCIP11_0695_7_PROMOTION_GATE.csv"
SUMMARY = REPORTS / "PCIP11_0695_7_PROMOTION_GATE.md"


@dataclass(frozen=True)
class GateResult:
    status: str
    reason: str


ALLOWED_LINEAGE = {
    "PCIP11",
    "CVBI11 -> PCIP11",
}

ALLOWED_STATUSES = {
    "AUTO_RESOLVED_REVIEW_REQUIRED",
}

ALLOWED_ACTION = "ELIGIBLE_FOR_PROMOTION_GATE"


def s(v) -> str:
    return "" if v is None else str(v).strip()


def gate(row: dict) -> GateResult:
    lineage = s(row.get("Lineage"))
    resolution = s(row.get("Resolution_Status"))
    action = s(row.get("Promotion_Action"))
    scale_state = s(row.get("Scale_State"))
    plausibility = s(row.get("Plausibility"))
    metric = s(row.get("Metric"))

    reasons = []

    if lineage not in ALLOWED_LINEAGE:
        reasons.append("lineage_not_supported")

    if resolution not in ALLOWED_STATUSES:
        reasons.append("resolution_not_auto_resolved")

    if action != ALLOWED_ACTION:
        reasons.append("promotion_action_not_eligible")

    if scale_state != "RESOLVED":
        reasons.append("scale_not_resolved")

    if plausibility != "PASS":
        reasons.append("plausibility_not_pass")

    if not metric or metric == "UNSTRUCTURED_EVIDENCE":
        reasons.append("metric_not_structured")

    if reasons:
        return GateResult("BLOCKED", "|".join(reasons))

    return GateResult("PASS", "all_0695_7_promotion_prerequisites_satisfied")


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"Missing input: {INPUT}")

    with INPUT.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    output = []
    counts = Counter()

    for row in rows:
        result = gate(row)
        counts[result.status] += 1
        out = dict(row)
        out["Promotion_Gate"] = result.status
        out["Promotion_Gate_Reason"] = result.reason
        out["Vault_Write_Authorization"] = (
            "NOT_GRANTED" if result.status == "PASS" else "DENIED"
        )
        output.append(out)

    fields = list(output[0].keys()) if output else []

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    lines = [
        "# PCIP11 - 0695.7 Promotion Gate",
        "",
        f"- Input rows: {len(rows)}",
        f"- PASS: {counts['PASS']}",
        f"- BLOCKED: {counts['BLOCKED']}",
        "",
        "## Gate",
        "",
        "- PASS means the candidate is structurally eligible for the next persistence step.",
        "- PASS does NOT authorize writing to the Obsidian Vault.",
        "- CVBI11 -> PCIP11 lineage remains explicit.",
        "- Only 0695.6R4R4 semantic resolution fields are consumed.",
        "",
        "## Safety",
        "",
        "- No Vault modification.",
        "- No metric persistence.",
        "- No KnowledgeBridge write.",
    ]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("0695.7 PROMOTION GATE")
    print("=" * 72)
    print(f"Input rows : {len(rows)}")
    print(f"PASS       : {counts['PASS']}")
    print(f"BLOCKED    : {counts['BLOCKED']}")
    print(f"CSV        : {OUTPUT}")
    print(f"Summary    : {SUMMARY}")
    print("")
    print("Vault changed: NO")
    print("Metric promoted: NO")


if __name__ == "__main__":
    main()
