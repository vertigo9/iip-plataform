import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.intelligence.metric_persistence_adapter import inspect_final_gate


def main() -> int:
    report = ROOT / "reports" / "0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv"
    output = ROOT / "reports" / "0695_7_PERSISTENCE_CONTRACT_DRY_RUN_R1.csv"

    if not report.exists():
        print(f"ERRO: {report} não encontrado.")
        return 2

    result = inspect_final_gate(report)

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Observation_Key",
                "Metric_Evidence_ID",
                "Knowledge_Evidence_ID",
                "Ticker",
                "Metric",
                "Value",
                "Unit",
                "Scale",
                "Period",
                "Semantic_Dimension",
                "Document_Hash",
                "Status",
                "Classification",
            ]
        )

        for candidate in result.candidates:
            observation = candidate.observation
            metric_id = (
                f"metric:{observation.canonical_ticker}:"
                f"{observation.period}:{observation.metric_name}"
            )
            # The actual stable metric ID belongs to metric_persistence.py;
            # keeping this runner dependency-light for review.
            writer.writerow(
                [
                    observation.observation_key,
                    metric_id,
                    candidate.knowledge_evidence.evidence_id,
                    observation.canonical_ticker,
                    observation.metric_name,
                    observation.value,
                    observation.unit or "",
                    observation.scale or "",
                    observation.period,
                    observation.semantic_dimension or "",
                    observation.document_hash,
                    candidate.status,
                    candidate.classification,
                ]
            )

    print("0695.7 PERSISTENCE CONTRACT DRY-RUN R1")
    print("=" * 90)
    print(f"Rows read                 : {result.rows_read}")
    print(f"Canonical observations    : {result.canonical_observations}")
    print(f"Exact duplicate rows     : {result.exact_duplicate_rows}")
    print(f"Blocked rows              : {result.blocked_rows}")
    print(f"CSV                       : {output}")
    print("Persistence executed     : NO")
    print("KnowledgeBridge executed : NO")
    print("Vault changed            : NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
