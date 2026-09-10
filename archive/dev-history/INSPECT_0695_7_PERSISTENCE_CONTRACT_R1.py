from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "iip"
TESTS = ROOT / "tests"

TARGETS = [
    SRC / "intelligence" / "metric_evidence.py",
    SRC / "intelligence" / "evidence_chain.py",
    SRC / "intelligence" / "intelligence_pipeline.py",
    SRC / "knowledge" / "models.py",
    SRC / "knowledge" / "bridge.py",
    SRC / "knowledge" / "repository.py",
    SRC / "platform" / "evidence.py",
    SRC / "platform" / "contracts.py",
]

TEST_TARGET_HINTS = (
    "metric",
    "evidence",
    "knowledge",
    "bridge",
    "intelligence",
)


def configure_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def safe_unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ast.dump(node, include_attributes=False)


def annotation_of(node: ast.AnnAssign | ast.arg | ast.AsyncFunctionDef | ast.FunctionDef | None) -> str:
    if isinstance(node, ast.AnnAssign):
        return safe_unparse(node.annotation)
    if isinstance(node, ast.arg):
        return safe_unparse(node.annotation)
    return ""


def class_fields(node: ast.ClassDef) -> list[str]:
    fields = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            fields.append(
                f"{item.target.id}: {safe_unparse(item.annotation)}"
            )
        elif (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
        ):
            # Keep simple class constants visible.
            fields.append(
                f"{item.targets[0].id} = {safe_unparse(item.value)}"
            )
    return fields


def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)

    for arg, default in zip(positional, defaults):
        text = arg.arg
        if arg.annotation:
            text += f": {safe_unparse(arg.annotation)}"
        if default is not None:
            text += f" = {safe_unparse(default)}"
        args.append(text)

    if node.args.vararg:
        text = "*" + node.args.vararg.arg
        if node.args.vararg.annotation:
            text += f": {safe_unparse(node.args.vararg.annotation)}"
        args.append(text)

    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if arg.annotation:
            text += f": {safe_unparse(arg.annotation)}"
        if default is not None:
            text += f" = {safe_unparse(default)}"
        args.append(text)

    if node.args.kwarg:
        text = "**" + node.args.kwarg.arg
        if node.args.kwarg.annotation:
            text += f": {safe_unparse(node.args.kwarg.annotation)}"
        args.append(text)

    result = ", ".join(args)
    if node.returns:
        result += f" -> {safe_unparse(node.returns)}"

    return f"({result})"


def inspect_file(path: Path) -> dict:
    result = {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "encoding": "",
        "parse_status": "",
        "imports": [],
        "classes": [],
        "functions": [],
        "references": [],
    }

    if not path.exists():
        result["parse_status"] = "MISSING"
        return result

    raw = path.read_bytes()

    if raw.startswith(b"\xef\xbb\xbf"):
        result["encoding"] = "UTF-8-BOM"
    else:
        result["encoding"] = "UTF-8-or-other"

    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            result["encoding"] = encoding
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        result["parse_status"] = "DECODE_ERROR"
        return result

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        result["parse_status"] = (
            f"SYNTAX_ERROR:{exc.lineno}:{exc.offset}:{exc.msg}"
        )
        return result

    result["parse_status"] = "OK"

    for node in tree.body:
        if isinstance(node, ast.Import):
            result["imports"].extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            result["imports"].append(f"{module}: {names}")

        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(
                        f"{item.name}{function_signature(item)}"
                    )
            result["classes"].append(
                {
                    "name": node.name,
                    "bases": [safe_unparse(base) for base in node.bases],
                    "fields": class_fields(node),
                    "methods": methods,
                }
            )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(
                f"{node.name}{function_signature(node)}"
            )

    lowered = text.casefold()
    for token in (
        "MetricObservation",
        "HistoricalMetricEvidence",
        "MetricPromotionAssessment",
        "EvidenceChain",
        "KnowledgeBridge",
        "Evidence",
        "save_evidence",
        "persist_evidence",
        "persist_snapshot",
        "assemble",
        "sync_evidence_projection",
    ):
        if token.casefold() in lowered:
            result["references"].append(token)

    return result


def discover_relevant_tests() -> list[Path]:
    if not TESTS.exists():
        return []

    candidates = []
    for path in TESTS.rglob("test_*.py"):
        lower = path.name.casefold()
        if any(hint in lower for hint in TEST_TARGET_HINTS):
            candidates.append(path)

    return sorted(candidates)


def main() -> None:
    print("0695.7 PERSISTENCE CONTRACT INSPECTOR R1")
    print("=" * 110)
    print(f"Repository root : {ROOT}")
    print(f"Python          : {sys.version.split()[0]}")
    print()

    results = []
    for path in TARGETS:
        results.append(inspect_file(path))

    test_results = [
        inspect_file(path) for path in discover_relevant_tests()
    ]

    print("TARGET MODULES")
    print("-" * 110)

    for result in results:
        print()
        print(f"[{result['parse_status']}] {result['path']}")
        print(f"Size       : {result['size']} bytes")
        print(f"Encoding   : {result['encoding']}")

        if result["imports"]:
            print("Imports:")
            for item in result["imports"][:25]:
                print(f"  - {item}")

        if result["classes"]:
            print("Classes:")
            for cls in result["classes"]:
                bases = ", ".join(cls["bases"]) or "(none)"
                print(f"  CLASS {cls['name']}({bases})")

                if cls["fields"]:
                    for field in cls["fields"]:
                        print(f"    FIELD {field}")

                if cls["methods"]:
                    for method in cls["methods"]:
                        print(f"    METHOD {method}")

        if result["functions"]:
            print("Functions:")
            for function in result["functions"]:
                print(f"  - {function}")

        if result["references"]:
            print("Relevant references:")
            print("  " + ", ".join(result["references"]))

    print()
    print("RELEVANT TEST MODULES")
    print("-" * 110)

    if not test_results:
        print("No relevant test_*.py files discovered.")
    else:
        for result in test_results:
            print(
                f"[{result['parse_status']}] {result['path']} "
                f"({result['size']} bytes)"
            )
            for cls in result["classes"]:
                print(f"  CLASS {cls['name']}")
                for method in cls["methods"]:
                    print(f"    METHOD {method}")
            for function in result["functions"]:
                print(f"  FUNCTION {function}")

    print()
    print("CONTRACT QUESTIONS")
    print("-" * 110)

    # Emit a compact machine-oriented checklist.
    path_map = {item["path"]: item for item in results}

    def has_class(path_suffix: str, class_name: str) -> bool:
        result = next(
            (
                item for item in results
                if item["path"].replace("\\", "/").endswith(path_suffix)
            ),
            None,
        )
        return bool(result and any(
            cls["name"] == class_name for cls in result["classes"]
        ))

    def has_method(path_suffix: str, method_name: str) -> bool:
        result = next(
            (
                item for item in results
                if item["path"].replace("\\", "/").endswith(path_suffix)
            ),
            None,
        )
        if not result:
            return False
        return any(
            method.startswith(method_name + "(")
            for cls in result["classes"]
            for method in cls["methods"]
        )

    questions = {
        "MetricObservation exists":
            has_class("intelligence\\metric_evidence.py", "MetricObservation")
            or has_class("intelligence/metric_evidence.py", "MetricObservation"),
        "HistoricalMetricEvidence exists":
            has_class("intelligence\\metric_evidence.py", "HistoricalMetricEvidence")
            or has_class("intelligence/metric_evidence.py", "HistoricalMetricEvidence"),
        "EvidenceChain exists":
            has_class("intelligence\\evidence_chain.py", "EvidenceChain")
            or has_class("intelligence/evidence_chain.py", "EvidenceChain"),
        "KnowledgeBridge exists":
            has_class("knowledge\\bridge.py", "KnowledgeBridge")
            or has_class("knowledge/bridge.py", "KnowledgeBridge"),
        "KnowledgeRepository save_evidence":
            has_method("knowledge\\repository.py", "save_evidence")
            or has_method("knowledge/repository.py", "save_evidence"),
        "KnowledgeBridge persist_evidence":
            has_method("knowledge\\bridge.py", "persist_evidence")
            or has_method("knowledge/bridge.py", "persist_evidence"),
    }

    for question, value in questions.items():
        print(f"{'PASS' if value else 'MISSING':8} {question}")

    # Duplicate Evidence classes across contracts.
    evidence_locations = []
    for result in results:
        if any(cls["name"] == "Evidence" for cls in result["classes"]):
            evidence_locations.append(result["path"])

    print()
    print(
        "Evidence class locations: "
        + (" | ".join(evidence_locations) if evidence_locations else "none")
    )

    print()
    print("SAFETY")
    print("-" * 110)
    print("Vault changed       : NO")
    print("Metric promoted     : NO")
    print("Persistence executed: NO")
    print("KnowledgeBridge write: NO")
    print()
    print("Inspection complete.")


if __name__ == "__main__":
    configure_utf8()
    main()
