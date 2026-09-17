
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "build",
    "dist",
}

TARGET_FILES = {
    "main.py",
    "portfolio_runner.py",
    "refresh.py",
    "batch_analyze.py",
    "fii_metric_adapter.py",
    "harvest_metric_adapter.py",
    "metric_persistence_adapter.py",
}

SYMBOLS = [
    "refresh_portfolio",
    "analyze_portfolio",
    "PortfolioOperationalRunner",
    "dispatch_harvest_to_engine",
    "MetricObservationIdentity",
    "HistoricalMetricEvidence",
    "persist_if_eligible",
    "persist_evidence",
    "sync_evidence_projection",
    "KnowledgeBridge",
    "AtlasKnowledgeAdapter",
    "FullIngestionPipeline",
    "persist_many",
    "document_id",
    "document_hash",
    "content_hash",
    "reference_period",
]

CONTEXT_BEFORE = 4
CONTEXT_AFTER = 6
MAX_MATCHES_PER_FILE = 250


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def read_text(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()


def matching_symbols(line: str) -> list[str]:
    found = []

    for symbol in SYMBOLS:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])"
        if re.search(pattern, line):
            found.append(symbol)

    return found


def add_context(
    output: list[str],
    path: Path,
    lines: list[str],
    line_index: int,
    symbols: list[str],
) -> None:
    start = max(0, line_index - CONTEXT_BEFORE)
    end = min(len(lines), line_index + CONTEXT_AFTER + 1)

    output.append("")
    output.append(
        f"--- {path} | linha {line_index + 1} | "
        f"símbolos: {', '.join(symbols)} ---"
    )

    for index in range(start, end):
        output.append(f"{index + 1:5}: {lines[index]}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent

    if not (repo_root / "src").is_dir():
        print(f"ERRO: pasta src não encontrada em {repo_root}")
        return 2

    audit_dir = repo_root / "audit_traces"
    audit_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = audit_dir / (
        f"TRACE_POL_25_26_CALL_GRAPH_AUDIT_{timestamp}.txt"
    )

    print("POL 25.26 - Call Graph Audit")
    print(f"Raiz: {repo_root}")
    print("Localizando arquivos Python...")

    python_files = sorted(
        path
        for path in repo_root.rglob("*.py")
        if not is_excluded(path.relative_to(repo_root))
    )

    if not python_files:
        print("ERRO: nenhum arquivo Python encontrado.")
        return 3

    target_files = [
        path for path in python_files if path.name in TARGET_FILES
    ]

    output: list[str] = [
        "POL 25.26 - CALL GRAPH / INTEGRATION AUDIT",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Repository: {repo_root}",
        "Mode: source-code read-only; report output only.",
        f"Python files scanned: {len(python_files)}",
        f"Target files found: {len(target_files)}",
        "",
        "TARGET FILE INVENTORY",
    ]

    for name in sorted(TARGET_FILES):
        matches = [path for path in target_files if path.name == name]

        if not matches:
            output.append(f"NOT FOUND: {name}")
        else:
            for path in matches:
                output.append(f"FOUND: {path.relative_to(repo_root)}")

    output.append("")
    output.append("=" * 100)
    output.append("FULL CONTENT OF TARGET FILES")
    output.append("=" * 100)

    for path in target_files:
        print(f"Lendo arquivo-alvo: {path.name}")
        lines = read_text(path)

        output.append("")
        output.append(f"FILE: {path.relative_to(repo_root)}")

        for index, line in enumerate(lines, start=1):
            output.append(f"{index:5}: {line}")

    output.append("")
    output.append("=" * 100)
    output.append("PROJECT-WIDE SYMBOL REFERENCES")
    output.append("=" * 100)

    total_matches = 0
    total_files_with_matches = 0

    for file_number, path in enumerate(python_files, start=1):
        if file_number % 200 == 0:
            print(f"Varredura: {file_number}/{len(python_files)}")

        lines = read_text(path)
        file_match_count = 0

        for index, line in enumerate(lines):
            found = matching_symbols(line)

            if not found:
                continue

            if file_match_count >= MAX_MATCHES_PER_FILE:
                output.append(
                    f"\nTRUNCATED: {path.relative_to(repo_root)} "
                    f"excedeu {MAX_MATCHES_PER_FILE} ocorrências."
                )
                break

            add_context(
                output,
                path.relative_to(repo_root),
                lines,
                index,
                found,
            )

            file_match_count += 1
            total_matches += 1

        if file_match_count:
            total_files_with_matches += 1

    output.extend(
        [
            "",
            "=" * 100,
            "SUMMARY",
            "=" * 100,
            f"Python files scanned: {len(python_files)}",
            f"Target files found: {len(target_files)}",
            f"Files with symbol matches: {total_files_with_matches}",
            f"Total matching lines: {total_matches}",
            f"Report: {report_path}",
            "Audit completed.",
        ]
    )

    report_path.write_text(
        "\n".join(output) + "\n",
        encoding="utf-8",
    )

    if not report_path.is_file() or report_path.stat().st_size == 0:
        print("ERRO: relatório não foi criado ou está vazio.")
        return 4

    print("")
    print("POL 25.26 concluído.")
    print(f"Relatório: {report_path}")
    print(f"Tamanho: {report_path.stat().st_size} bytes")
    print(f"Arquivos Python examinados: {len(python_files)}")
    print(f"Linhas correspondentes: {total_matches}")

    return 0


if __name__ == "__main__":
    sys.exit(main())