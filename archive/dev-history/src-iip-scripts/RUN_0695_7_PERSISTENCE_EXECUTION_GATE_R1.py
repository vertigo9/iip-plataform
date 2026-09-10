from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "reports"

INPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_CONTRACT_R4.csv"
BRIDGE_CSV = REPORTS / "PCIP11_0695_7_KNOWLEDGE_BRIDGE_DRY_RUN_R1.csv"
REPO_CSV = REPORTS / "PCIP11_0695_7_REPOSITORY_DRY_RUN_R2.csv"

OUTPUT_CSV = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.csv"
OUTPUT_MD = REPORTS / "PCIP11_0695_7_PERSISTENCE_EXECUTION_GATE_R1.md"

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.intelligence.metric_identity import MetricObservationIdentity
from iip.intelligence.metric_persistence import (
    knowledge_evidence_id,
    metric_evidence_id,
)

REQUIRED_FIELDS = {
    "Metric_ID",
    "Knowledge_Evidence_ID",
    "Ticker",
    "Metric",
    "Value",
    "Unit",
    "Scale",
    "Period",
    "Semantic_Dimension",
    "Document_ID",
    "Document_Hash",
    "Source_Locator",
    "Lineage",
}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def field(row: dict[str, str], name: str) -> str:
    return str(row.get(name, "") or "").strip()


def identity_from_contract(row: dict[str, str]) -> MetricObservationIdentity:
    return MetricObservationIdentity(
        canonical_ticker=field(row, "Ticker"),
        original_ticker=field(row, "Original_Ticker") or field(row, "Ticker"),
        metric_name=field(row, "Metric"),
        value=field(row, "Value"),
        unit=field(row, "Unit") or None,
        scale=field(row, "Scale") or None,
        period=field(row, "Period"),
        semantic_dimension=field(row, "Semantic_Dimension") or None,
        document_hash=field(row, "Document_Hash"),
        document_id=field(row, "Document_ID") or None,
        source_locator=field(row, "Source_Locator") or None,
        lineage=field(row, "Lineage") or None,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    errors: Counter[str] = Counter()
    gate_rows: list[dict[str, str]] = []

    # ---- Gate 1: required source artifacts exist ----
    for path in (INPUT_CSV, BRIDGE_CSV, REPO_CSV):
        if not path.exists():
            errors[f"missing_artifact:{path.name}"] += 1

    if errors:
        OUTPUT_MD.write_text(
            "# PCIP11 — 0695.7 Persistence Execution Gate R1\n\n"
            "## Authorization\n"
            "- EXECUTION AUTHORIZED: NO\n"
            "- Persistence executed: NO\n"
            "- KnowledgeBridge executed: NO\n"
            "- Vault changed: NO\n\n"
            "## Failures\n"
            + "\n".join(f"- {k}: {v}" for k, v in sorted(errors.items()))
            + "\n",
            encoding="utf-8",
        )
        print("=" * 90)
        print("0695.7 PERSISTENCE EXECUTION GATE R1")
        print("=" * 90)
        print("EXECUTION AUTHORIZED        : NO")
        print("Persistence executed         : NO")
        print("KnowledgeBridge executed     : NO")
        print("Vault changed                : NO")
        return 1

    contract = load_csv(INPUT_CSV)
    bridge = load_csv(BRIDGE_CSV)
    repo = load_csv(REPO_CSV)

    # ---- Gate 2: exact cardinality and schema ----
    if len(contract) != 28:
        errors[f"contract_row_count:{len(contract)}"] += 1
    if len(bridge) != 28:
        errors[f"bridge_row_count:{len(bridge)}"] += 1
    if len(repo) != 28:
        errors[f"repo_row_count:{len(repo)}"] += 1

    if contract:
        missing_fields = REQUIRED_FIELDS.difference(contract[0].keys())
        for name in sorted(missing_fields):
            errors[f"contract_missing_field:{name}"] += 1

    # ---- Gate 3: status / authorization fields ----
    for idx, row in enumerate(contract, start=2):
        if field(row, "Status") != "IDENTITY_READY":
            errors[f"row_{idx}:status_not_identity_ready"] += 1

        # Contract R4 must remain canonical/eligible.
        if field(row, "Classification") != "CANONICAL":
            errors[f"row_{idx}:classification_not_canonical"] += 1

    # ---- Gate 4: rebuild canonical IDs from official implementation ----
    metric_ids: list[str] = []
    knowledge_ids: list[str] = []

    for idx, row in enumerate(contract, start=2):
        try:
            identity = identity_from_contract(row)

            expected_metric = metric_evidence_id(identity)
            expected_knowledge = knowledge_evidence_id(expected_metric)

            actual_metric = field(row, "Metric_ID")
            actual_knowledge = field(row, "Knowledge_Evidence_ID")

            if actual_metric != expected_metric:
                errors[f"row_{idx}:metric_id_mismatch"] += 1

            if actual_knowledge != expected_knowledge:
                errors[f"row_{idx}:knowledge_id_mismatch"] += 1

            if field(row, "Observation_Key") != identity.observation_key:
                errors[f"row_{idx}:observation_key_mismatch"] += 1

            metric_ids.append(actual_metric)
            knowledge_ids.append(actual_knowledge)

            gate_rows.append(
                {
                    "Source_Row": str(idx),
                    "Metric_ID": actual_metric,
                    "Knowledge_Evidence_ID": actual_knowledge,
                    "Ticker": field(row, "Ticker"),
                    "Metric": field(row, "Metric"),
                    "Value": field(row, "Value"),
                    "Period": field(row, "Period"),
                    "Semantic_Dimension": field(row, "Semantic_Dimension"),
                    "Document_Hash": field(row, "Document_Hash"),
                    "Gate_Status": "PASS",
                }
            )
        except Exception as exc:
            errors[f"row_{idx}:identity_rebuild:{type(exc).__name__}:{exc}"] += 1

    # ---- Gate 5: uniqueness / collision checks ----
    metric_counts = Counter(metric_ids)
    knowledge_counts = Counter(knowledge_ids)

    for key, count in metric_counts.items():
        if count > 1:
            errors[f"duplicate_metric_id:{key}"] += count - 1

    for key, count in knowledge_counts.items():
        if count > 1:
            errors[f"duplicate_knowledge_id:{key}"] += count - 1

    # ---- Gate 6: bridge / repository dry-runs must both be green ----
    bridge_statuses = Counter(field(row, "Mapping_Status") for row in bridge)
    repo_statuses = Counter(field(row, "Mapping_Status") for row in repo)

    if bridge_statuses.get("READY", 0) != 28:
        errors[f"bridge_ready_count:{bridge_statuses.get('READY', 0)}"] += 1

    if repo_statuses.get("READY", 0) != 28:
        errors[f"repo_ready_count:{repo_statuses.get('READY', 0)}"] += 1

    if bridge_statuses.get("BLOCKED", 0):
        errors[f"bridge_blocked_count:{bridge_statuses['BLOCKED']}"] += 1

    if repo_statuses.get("BLOCKED", 0):
        errors[f"repo_blocked_count:{repo_statuses['BLOCKED']}"] += 1

    # ---- Gate 7: source artifact fingerprints ----
    fingerprints = {
        "contract_sha256": sha256_file(INPUT_CSV),
        "bridge_sha256": sha256_file(BRIDGE_CSV),
        "repository_sha256": sha256_file(REPO_CSV),
    }

    authorized = (
        len(contract) == 28
        and len(bridge) == 28
        and len(repo) == 28
        and len(metric_ids) == 28
        and len(knowledge_ids) == 28
        and len(set(metric_ids)) == 28
        and len(set(knowledge_ids)) == 28
        and not errors
    )

    # Contract artifact is explicitly an authorization decision, not execution.
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "Source_Row",
                "Metric_ID",
                "Knowledge_Evidence_ID",
                "Ticker",
                "Metric",
                "Value",
                "Period",
                "Semantic_Dimension",
                "Document_Hash",
                "Gate_Status",
            ],
        )
        writer.writeheader()
        for row in gate_rows:
            writer.writerow(row)

    lines = [
        "# PCIP11 — 0695.7 Persistence Execution Gate R1",
        "",
        "## Authorization",
        f"- EXECUTION AUTHORIZED: {'YES' if authorized else 'NO'}",
        "- Persistence executed: NO",
        "- KnowledgeBridge executed: NO",
        "- Vault changed: NO",
        "",
        "## Gate checks",
        f"- Contract rows: {len(contract)}",
        f"- Bridge dry-run READY rows: {bridge_statuses.get('READY', 0)}",
        f"- Repository dry-run READY rows: {repo_statuses.get('READY', 0)}",
        f"- Unique Metric_ID: {len(set(metric_ids))}",
        f"- Unique Knowledge_Evidence_ID: {len(set(knowledge_ids))}",
        f"- Errors: {sum(errors.values())}",
        "",
        "## Artifact fingerprints",
    ]
    lines.extend(f"- {name}: {value}" for name, value in fingerprints.items())

    lines += [
        "",
        "## Failures",
    ]

    if errors:
        lines.extend(f"- {key}: {count}" for key, count in sorted(errors.items()))
    else:
        lines.append("- none")

    lines += [
        "",
        "This gate does not persist anything. A YES result only authorizes "
        "a separate execution step using the exact artifacts validated here.",
    ]

    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 90)
    print("0695.7 PERSISTENCE EXECUTION GATE R1")
    print("=" * 90)
    print(f"Contract rows                : {len(contract)}")
    print(f"Bridge READY rows            : {bridge_statuses.get('READY', 0)}")
    print(f"Repository READY rows        : {repo_statuses.get('READY', 0)}")
    print(f"Unique Metric_ID             : {len(set(metric_ids))}")
    print(f"Unique Knowledge_Evidence_ID : {len(set(knowledge_ids))}")
    print(f"Errors                       : {sum(errors.values())}")
    print(f"EXECUTION AUTHORIZED         : {'YES' if authorized else 'NO'}")
    print("Persistence executed         : NO")
    print("KnowledgeBridge executed     : NO")
    print("Vault changed                : NO")
    print(f"CSV                          : {OUTPUT_CSV}")
    print(f"MD                           : {OUTPUT_MD}")

    return 0 if authorized else 1


if __name__ == "__main__":
    raise SystemExit(main())
