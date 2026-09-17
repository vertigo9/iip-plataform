
from __future__ import annotations

import ast
import datetime as dt
import os
from pathlib import Path
import sys
import traceback


# ============================================================
# POL 25.27 — Persistence Call Graph Closure
# Read-only static audit. No source files are modified.
# ============================================================

AUDIT_NAME = "POL_25_27_PERSISTENCE_CALL_GRAPH_AUDIT"

TARGET_SYMBOLS = {
    "harvest_metrics_to_evidence",
    "persist_if_eligible",
    "persist_evidence",
    "dispatch_harvest_to_engine",
    "MetricObservationIdentity",
    "HistoricalMetricEvidence",
    "KnowledgeBridge",
    "AtlasKnowledgeAdapter",
    "FullIngestionPipeline",
    "refresh_portfolio",
    "analyze_portfolio",
    "run_asset",
}

TARGET_FRAGMENTS = (
    "metric_persistence",
    "fii_metric_adapter",
    "harvest_metric_adapter",
    "knowledge_bridge",
    "portfolio_runner",
    "batch_analyze",
    "refresh",
    "ingestion",
)

MAX_FILE_BYTES = 3_000_000


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def safe_read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return f"# SKIPPED: file exceeds {MAX_FILE_BYTES} bytes\n"
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"# READ ERROR: {type(exc).__name__}: {exc}\n"


def is_test_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    return None


class SourceFacts(ast.NodeVisitor):
    def __init__(self, source: str, path: Path):
        self.source = source.splitlines()
        self.path = path
        self.definitions: list[tuple[int, str, str]] = []
        self.imports: list[tuple[int, str, str]] = []
        self.calls: list[tuple[int, str, str | None, str]] = []
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []

    def current_scope(self) -> str:
        return ".".join(self.class_stack + self.function_stack) or "<module>"

    def visit_ClassDef(self, node: ast.ClassDef):
        self.definitions.append((node.lineno, "class", node.name))
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.definitions.append((node.lineno, "function", node.name))
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.definitions.append((node.lineno, "async function", node.name))
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(
                (node.lineno, alias.name, alias.asname or alias.name)
            )

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            self.imports.append(
                (node.lineno, module, alias.asname or alias.name)
            )

    def visit_Call(self, node: ast.Call):
        callee = dotted_name(node.func) or "<dynamic-call>"
        self.calls.append(
            (node.lineno, callee, self.current_scope(),
             ast.get_source_segment("\n".join(self.source), node) or "")
        )
        self.generic_visit(node)


def matches_target(text: str) -> bool:
    return any(symbol in text for symbol in TARGET_SYMBOLS)


def classify_path(path: Path) -> str:
    return "TEST / NON-PRODUCTION" if is_test_path(path) else "PRODUCTION CANDIDATE"


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    root = Path.cwd().resolve()

    # Permit running from repository root or from a subdirectory.
    if not (root / "src" / "iip").is_dir():
        script_root = Path(__file__).resolve().parent
        if (script_root / "src" / "iip").is_dir():
            root = script_root

    package_root = root / "src" / "iip"
    if not package_root.is_dir():
        print("ERROR: Could not find src/iip.")
        print(f"Current directory: {Path.cwd()}")
        print(f"Script directory: {Path(__file__).resolve().parent}")
        print("Run this script from the repository root or place it there.")
        return 2

    timestamp = now_stamp()
    output_dir = root / "audit_traces"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"TRACE_{AUDIT_NAME}_{timestamp}.txt"

    python_files = sorted(package_root.rglob("*.py"))
    production_files = [p for p in python_files if not is_test_path(p)]
    test_files = [p for p in python_files if is_test_path(p)]

    parsed = []
    parse_errors = []
    unreadable = []

    for path in python_files:
        text = safe_read(path)
        if text.startswith("# READ ERROR:") or text.startswith("# SKIPPED:"):
            unreadable.append((path, text.strip()))
            continue
        try:
            tree = ast.parse(text, filename=str(path))
            facts = SourceFacts(text, path)
            facts.visit(tree)
            parsed.append((path, text, facts))
        except Exception as exc:
            parse_errors.append((path, type(exc).__name__, str(exc)))

    # Index function/class definitions by simple name.
    definitions_index: dict[str, list[tuple[Path, int, str]]] = {}
    for path, _, facts in parsed:
        for line, kind, name in facts.definitions:
            definitions_index.setdefault(name, []).append((path, line, kind))

    # Find candidate call edges targeting named symbols, including
    # qualified calls such as obj.persist_if_eligible(...).
    call_hits = []
    import_hits = []
    definition_hits = []

    for path, _, facts in parsed:
        file_class = classify_path(path)

        for line, kind, name in facts.definitions:
            if matches_target(name):
                definition_hits.append((path, line, kind, name, file_class))

        for line, module, imported in facts.imports:
            if matches_target(module) or matches_target(imported):
                import_hits.append(
                    (path, line, module, imported, file_class)
                )

        for line, callee, scope, source_segment in facts.calls:
            leaf = callee.split(".")[-1]
            if matches_target(callee) or leaf in TARGET_SYMBOLS:
                call_hits.append(
                    (path, line, callee, scope, source_segment, file_class)
                )

    lines: list[str] = []

    def out(text: str = ""):
        lines.append(text)

    out("=" * 88)
    out(f"{AUDIT_NAME}")
    out(f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}")
    out(f"Repository root: {root}")
    out(f"Package root: {package_root}")
    out("Mode: READ-ONLY STATIC AST SCAN")
    out("No source files changed. No tests executed. No runtime calls made.")
    out("=" * 88)

    out("\n[1] SCAN SUMMARY")
    out(f"Python files discovered: {len(python_files)}")
    out(f"Production-candidate files: {len(production_files)}")
    out(f"Test/non-production-path files: {len(test_files)}")
    out(f"Files parsed: {len(parsed)}")
    out(f"Parse errors: {len(parse_errors)}")
    out(f"Unreadable/skipped files: {len(unreadable)}")
    out(f"Matching definitions: {len(definition_hits)}")
    out(f"Matching imports: {len(import_hits)}")
    out(f"Matching calls: {len(call_hits)}")

    out("\n[2] TARGET DEFINITIONS")
    for path, line, kind, name, file_class in sorted(
        definition_hits, key=lambda x: (str(x[0]), x[1])
    ):
        out(f"{file_class} | {relative(path, root)}:{line} | {kind} {name}")

    out("\n[3] TARGET IMPORTS")
    for path, line, module, imported, file_class in sorted(
        import_hits, key=lambda x: (str(x[0]), x[1])
    ):
        out(
            f"{file_class} | {relative(path, root)}:{line} | "
            f"from {module} import {imported}"
        )

    out("\n[4] CALL-SITE CANDIDATES")
    for path, line, callee, scope, source_segment, file_class in sorted(
        call_hits, key=lambda x: (str(x[0]), x[1])
    ):
        out(
            f"{file_class} | {relative(path, root)}:{line} | "
            f"scope={scope} | call={callee}"
        )
        if source_segment:
            out(f"    SOURCE: {source_segment.strip().replace(chr(10), ' ')}")

    out("\n[5] TARGET DEFINITIONS WITH KNOWN CALLERS")
    for symbol in sorted(TARGET_SYMBOLS):
        defs = definitions_index.get(symbol, [])
        if not defs:
            continue
        out(f"\nSYMBOL: {symbol}")
        for def_path, def_line, def_kind in defs:
            out(
                f"  DEFINITION: {relative(def_path, root)}:{def_line} "
                f"({def_kind})"
            )
            found = False
            for path, line, callee, scope, _, file_class in call_hits:
                if callee.split(".")[-1] == symbol:
                    out(
                        f"    POSSIBLE CALLER: {file_class} | "
                        f"{relative(path, root)}:{line} | {scope} | {callee}"
                    )
                    found = True
            if not found:
                out("    POSSIBLE CALLER: none found by static name matching")

    out("\n[6] RELEVANT FILE INVENTORY")
    for path in python_files:
        p = str(path).lower()
        if any(fragment in p for fragment in TARGET_FRAGMENTS):
            out(f"{classify_path(path)} | {relative(path, root)}")

    out("\n[7] STATIC CALL GRAPH LIMITATIONS")
    out("- Name-based AST matching is not proof of runtime reachability.")
    out("- Aliases, dependency injection, decorators, reflection, and dynamic dispatch")
    out("  may hide or alter call relationships.")
    out("- A call to an adapter is not proof that evidence was accepted or persisted.")
    out("- A persistence method call is not proof of durable storage or transaction commit.")
    out("- Test fixtures, mocks, and synthetic evidence must not be treated as production proof.")
    out("- Provenance must be verified field-by-field at the actual production call path.")

    out("\n[8] PARSE ERRORS")
    if parse_errors:
        for path, kind, message in parse_errors:
            out(f"{relative(path, root)} | {kind}: {message}")
    else:
        out("None.")

    out("\n[9] UNREADABLE / SKIPPED FILES")
    if unreadable:
        for path, message in unreadable:
            out(f"{relative(path, root)} | {message}")
    else:
        out("None.")

    out("\n[10] NEXT MANUAL VERIFICATION CHECKLIST")
    out("- Trace production callers of harvest_metrics_to_evidence().")
    out("- Trace production callers of persist_if_eligible().")
    out("- Establish whether refresh/analyze paths reach either function.")
    out("- Follow accepted evidence into KnowledgeBridge.persist_evidence().")
    out("- Identify the concrete persistent repository/backend and commit boundary.")
    out("- Verify ticker, period, document_id, document_hash, and source provenance.")
    out("- Classify stubs, dry-run paths, mocks, fixtures, and synthetic examples separately.")
    out("- Do not patch until the production path and missing contract are evidenced.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 72)
    print("POL 25.27 audit completed.")
    print(f"Files scanned: {len(python_files)}")
    print(f"Matching calls: {len(call_hits)}")
    print(f"Report: {report_path}")
    print("Read-only source scan; no tests executed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)