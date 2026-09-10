from __future__ import annotations

import ast
import inspect
import importlib
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

ROOT = Path.cwd()

TARGETS = [
    ("iip.knowledge.models", "src/iip/knowledge/models.py"),
    ("iip.platform.contracts", "src/iip/platform/contracts.py"),
    ("iip.knowledge.repository", "src/iip/knowledge/repository.py"),
    ("iip.knowledge.bridge", "src/iip/knowledge/bridge.py"),
    ("iip.atlas.history", "src/iip/atlas/history.py"),
    ("iip.atlas.batch", "src/iip/atlas/batch.py"),
    ("iip.cycle.historical_bridge", "src/iip/cycle/historical_bridge.py"),
    ("iip.intelligence.evidence_chain", "src/iip/intelligence/evidence_chain.py"),
    ("iip.intelligence.intelligence_pipeline", "src/iip/intelligence/intelligence_pipeline.py"),
    ("iip.metrics", "src/iip/metrics/__init__.py"),
]


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def safe_ast(path: Path):
    try:
        text = path.read_text(encoding="utf-8-sig")
        return ast.parse(text)
    except Exception as exc:
        print(f"AST ERROR: {type(exc).__name__}: {exc}")
        return None


def print_ast_summary(path: Path) -> None:
    print(f"\nFILE: {path.relative_to(ROOT)}")
    if not path.exists():
        print("  MISSING")
        return

    print(f"  bytes: {path.stat().st_size:,}")
    tree = safe_ast(path)
    if tree is None:
        return

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            print(f"  class {node.name}")
            for m in methods:
                print(f"    method: {m}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            print(f"  function {node.name}")


def runtime_module(name: str) -> None:
    print(f"\nMODULE: {name}")
    try:
        mod = importlib.import_module(name)
    except Exception as exc:
        print(f"  IMPORT ERROR: {type(exc).__name__}: {exc}")
        return

    print(f"  file: {getattr(mod, '__file__', '')}")

    public = [
        (k, v) for k, v in vars(mod).items()
        if not k.startswith("_")
    ]

    for k, v in public:
        if inspect.isclass(v) and getattr(v, "__module__", None) == name:
            print(f"  CLASS: {k}")
            if is_dataclass(v):
                print("    dataclass fields:")
                for f in fields(v):
                    print(f"      - {f.name}: {f.type!r}; default={f.default!r}")
            try:
                sig = inspect.signature(v)
                print(f"    constructor: {sig}")
            except Exception:
                pass

            for member_name, member in inspect.getmembers(v):
                if member_name.startswith("_"):
                    continue
                if inspect.isfunction(member) or inspect.ismethod(member):
                    try:
                        print(f"    method {member_name}{inspect.signature(member)}")
                    except Exception:
                        print(f"    method {member_name}")

        elif inspect.isfunction(v) and getattr(v, "__module__", None) == name:
            try:
                print(f"  FUNCTION: {k}{inspect.signature(v)}")
            except Exception:
                print(f"  FUNCTION: {k}")


section("IIP - PYTHON DOMAIN CONTRACT DIAGNOSTIC")

print(f"Python executable: {sys.executable}")
print(f"Python version   : {sys.version.splitlines()[0]}")
print(f"Root             : {ROOT}")

section("1. AST CHECK OF TARGET FILES")
for _, rel in TARGETS:
    print_ast_summary(ROOT / rel)

section("2. RUNTIME IMPORT CHECK")
for name, _ in TARGETS:
    runtime_module(name)

section("3. METRICS MODULE SPECIAL CHECK")
metrics_path = ROOT / "src/iip/metrics/__init__.py"
if metrics_path.exists():
    raw = metrics_path.read_bytes()
    print(f"metrics/__init__.py first 16 bytes: {raw[:16]!r}")
    if raw.startswith(b"\xef\xbb\xbf"):
        print("WARNING: UTF-8 BOM detected. Python should normally tolerate BOM, but this file was previously reported with U+FEFF syntax failure.")
    try:
        clean = metrics_path.read_text(encoding="utf-8-sig")
        ast.parse(clean)
        print("AST with utf-8-sig: PASS")
    except Exception as exc:
        print(f"AST with utf-8-sig: FAIL - {type(exc).__name__}: {exc}")

section("4. RECOMMENDED INTEGRATION POINTS")

print("""
The next implementation should prefer the existing domain contracts:

- iip.knowledge.models.Evidence
- iip.platform.contracts.Evidence
- iip.platform.evidence.EvidenceStore
- iip.intelligence.evidence_chain.EvidenceChain
- iip.knowledge.bridge.KnowledgeBridge

Before creating a MetricPromotionGate, we need the exact constructor/signature
and field contracts of these objects. This diagnostic is read-only.
""")

print("DIAGNOSTIC COMPLETED")
