
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path
import traceback


AUDIT_NAME = "POL_25_28_FLOW_CONTRACT_AUDIT"

TARGETS = {
    "refresh_portfolio",
    "analyze_portfolio",
    "harvest_metrics_to_evidence",
    "persist_if_eligible",
    "dispatch_harvest_to_engine",
    "run_asset",
    "run_portfolio_cycle",
    "persist_evidence",
    "persist",
    "on_document",
    "FullIngestionPipeline",
    "AtlasKnowledgeAdapter",
    "KnowledgeBridge",
    "MetricObservationIdentity",
    "HistoricalMetricEvidence",
}

KEYWORDS = (
    "harvest_metrics_to_evidence",
    "persist_if_eligible",
    "persist_evidence",
    "HistoricalMetricEvidence",
    "MetricObservationIdentity",
    "KnowledgeBridge",
    "AtlasKnowledgeAdapter",
    "FullIngestionPipeline",
    "document_id",
    "document_hash",
    "source_locator",
    "lineage",
    "repository",
    "commit",
    "write_text",
    "open(",
)

MAX_FILE_BYTES = 3_000_000


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def is_test(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def node_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = node_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return node_name(node.func)
    return None


def source_segment(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def function_index(tree: ast.AST):
    result = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope = []

        def visit_ClassDef(self, node):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node):
            full = ".".join(self.scope + [node.name])
            result.append((node, full, "function"))
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_AsyncFunctionDef(self, node):
            full = ".".join(self.scope + [node.name])
            result.append((node, full, "async function"))
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

    Visitor().visit(tree)
    return result


def main() -> int:
    root = Path.cwd().resolve()
    package = root / "src" / "iip"

    if not package.is_dir():
        script_root = Path(__file__).resolve().parent
        if (script_root / "src" / "iip").is_dir():
            root = script_root
            package = root / "src" / "iip"

    if not package.is_dir():
        print("ERROR: src/iip not found. Run from repository root.")
        return 2

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = root / "audit_traces"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"TRACE_{AUDIT_NAME}_{stamp}.txt"

    files = sorted(package.rglob("*.py"))
    parsed = []
    errors = []
    skipped = []

    # utf-8-sig accepts ordinary UTF-8 and strips a leading BOM.
    for path in files:
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                skipped.append((path, "file exceeds size limit"))
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(text, filename=str(path))
            parsed.append((path, text, tree))
        except Exception as exc:
            errors.append((path, type(exc).__name__, str(exc)))

    lines = []

    def out(s=""):
        lines.append(s)

    out("=" * 88)
    out(AUDIT_NAME)
    out(f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}")
    out(f"Root: {root}")
    out(f"Files discovered: {len(files)}")
    out(f"Files parsed: {len(parsed)}")
    out(f"Parse errors: {len(errors)}")
    out("Mode: read-only AST and source inspection")
    out("No tests executed; no source files modified.")
    out("=" * 88)

    # Index definitions by qualified and simple name.
    definitions = {}
    for path, text, tree in parsed:
        for node, qualified, kind in function_index(tree):
            simple = qualified.split(".")[-1]
            definitions.setdefault(simple, []).append(
                (path, text, node, qualified, kind)
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                definitions.setdefault(node.name, []).append(
                    (path, text, node, node.name, "class")
                )

    out("\n[1] TARGET FUNCTION / CLASS BODIES")
    for symbol in sorted(TARGETS):
        entries = definitions.get(symbol, [])
        if not entries:
            continue

        out(f"\n### SYMBOL: {symbol}")
        for path, text, node, qualified, kind in entries:
            category = "TEST/NON-PRODUCTION" if is_test(path) else "PRODUCTION CANDIDATE"
            out(f"\n--- {category} | {rel(path, root)}:{node.lineno} | {kind} {qualified} ---")
            body = source_segment(text, node)
            out(body if body else "<source segment unavailable>")

    out("\n[2] IMPORTS IN RELEVANT FILES")
    relevant_files = set()
    for path, text, tree in parsed:
        low = str(path).lower()
        if any(term.lower() in low for term in (
            "portfolio", "harvest", "metric", "knowledge",
            "atlas", "execution", "event_adapter"
        )):
            relevant_files.add(path)

    for path, text, tree in sorted(parsed, key=lambda x: str(x[0])):
        if path not in relevant_files:
            continue
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.append((node.lineno, source_segment(text, node)))
            elif isinstance(node, ast.ImportFrom):
                imports.append((node.lineno, source_segment(text, node)))
        if imports:
            out(f"\n--- {rel(path, root)} ---")
            for lineno, statement in sorted(imports):
                out(f"{lineno}: {statement}")

    out("\n[3] EXACT SYMBOL REFERENCES ACROSS PACKAGE")
    for path, text, tree in parsed:
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in TARGETS:
                out(
                    f"{'TEST' if is_test(path) else 'PRODUCTION CANDIDATE'} | "
                    f"{rel(path, root)}:{node.lineno} | Name: {node.id}"
                )
            elif isinstance(node, ast.Attribute) and node.attr in TARGETS:
                out(
                    f"{'TEST' if is_test(path) else 'PRODUCTION CANDIDATE'} | "
                    f"{rel(path, root)}:{node.lineno} | Attribute: {node.attr}"
                )

    out("\n[4] PROVENANCE AND STORAGE KEYWORD CONTEXT")
    for path, text, tree in parsed:
        source_lines = text.splitlines()
        hits = []
        for i, line in enumerate(source_lines):
            if any(keyword.lower() in line.lower() for keyword in KEYWORDS):
                hits.append(i)

        if not hits:
            continue

        out(f"\n--- {'TEST' if is_test(path) else 'PRODUCTION CANDIDATE'} | {rel(path, root)} ---")
        emitted = set()
        for i in hits:
            start = max(0, i - 2)
            end = min(len(source_lines), i + 3)
            for j in range(start, end):
                if j not in emitted:
                    out(f"{j + 1}: {source_lines[j]}")
                    emitted.add(j)
            out("...")

    out("\n[5] PARSE ERRORS")
    if errors:
        for path, kind, message in errors:
            out(f"{rel(path, root)} | {kind}: {message}")
    else:
        out("None.")

    out("\n[6] SKIPPED FILES")
    if skipped:
        for path, reason in skipped:
            out(f"{rel(path, root)} | {reason}")
    else:
        out("None.")

    out("\n[7] AUDIT LIMITATIONS")
    out("- Static references do not prove runtime reachability.")
    out("- Same-name methods may belong to different classes or modules.")
    out("- Dependency injection and dynamic dispatch require manual tracing.")
    out("- A call to persist_evidence does not by itself prove durable storage.")
    out("- Confirm actual backend, write boundary, errors, and transaction semantics.")
    out("- Separate production code from tests, mocks, stubs, and simulations.")

    out("\n[8] REVIEW QUESTIONS")
    out("1. Does refresh_portfolio invoke the metric harvest adapter?")
    out("2. Does analyze_portfolio invoke it, directly or through a runtime service?")
    out("3. What production caller, if any, invokes persist_if_eligible?")
    out("4. Which concrete bridge instance receives the evidence?")
    out("5. Which backend receives the evidence and what confirms durable persistence?")
    out("6. Are document_id, document_hash, ticker, period, source_locator, and lineage preserved?")
    out("7. Are there competing KnowledgeBridge implementations or import-path ambiguities?")
    out("8. Which links remain unproven and require a runtime trace or focused test?")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 72)
    print("POL 25.28 audit completed.")
    print(f"Discovered: {len(files)} | Parsed: {len(parsed)} | Errors: {len(errors)}")
    print(f"Report: {report}")
    print("Read-only scan; no tests executed.")
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