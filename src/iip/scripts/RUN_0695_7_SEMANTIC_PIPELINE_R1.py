import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iip.intelligence.metric_persistence_adapter import inspect_final_gate


def main() -> int:
    report = ROOT / "reports" / "0695_GENERIC_METRIC_PERSISTENCE_DRY_RUN_R1.csv"
    if not report.exists():
        print(f"ERRO: {report} não encontrado.")
        print("Execute primeiro o pipeline 0695.7 existente.")
        return 2

    result = inspect_final_gate(report)

    print("0695.7 GENERIC SEMANTIC PIPELINE R1")
    print("=" * 90)
    print(f"Rows read                 : {result.rows_read}")
    print(f"Canonical observations    : {result.canonical_observations}")
    print(f"Exact duplicate rows     : {result.exact_duplicate_rows}")
    print(f"Blocked rows              : {result.blocked_rows}")
    print("Persistence executed     : NO")
    print("KnowledgeBridge executed : NO")
    print("Vault changed            : NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
