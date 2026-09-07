from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path.cwd()
FILES = [
    "src/iip/atlas/history.py",
    "src/iip/atlas/batch.py",
    "src/iip/cycle/historical_bridge.py",
    "src/iip/knowledge/models.py",
    "src/iip/knowledge/repository.py",
    "src/iip/knowledge/bridge.py",
    "src/iip/knowledge/context.py",
    "src/iip/metrics/__init__.py",
    "src/iip/platform/evidence.py",
    "src/iip/platform/contracts.py",
    "src/iip/intelligence/evidence_chain.py",
    "src/iip/intelligence/intelligence_pipeline.py",
]

def qname(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = qname(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""

def inspect_file(rel: str) -> None:
    path = ROOT / rel
    print()
    print("-" * 72)
    print(rel)
    print("-" * 72)

    if not path.exists():
        print("MISSING")
        return

    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return

    imports = []
    classes = []
    functions = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
        elif isinstance(node, ast.ClassDef):
            methods = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(child.name)
            classes.append((node.name, methods))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    print(f"Lines: {len(text.splitlines())}")
    print(f"Imports: {len(imports)}")
    for item in imports[:25]:
        print(f"  import {item}")
    if len(imports) > 25:
        print(f"  ... +{len(imports)-25}")

    print("Classes:")
    if classes:
        for name, methods in classes:
            print(f"  class {name}")
            for method in methods[:30]:
                print(f"    - {method}")
            if len(methods) > 30:
                print(f"    ... +{len(methods)-30}")
    else:
        print("  (none)")

    print("Top-level functions:")
    if functions:
        for name in functions:
            print(f"  - {name}")
    else:
        print("  (none)")

print("=" * 72)
print("IIP - PYTHON DOMAIN INTERFACE MAP")
print("=" * 72)
print(f"Root: {ROOT}")
print()

for rel in FILES:
    inspect_file(rel)

print()
print("=" * 72)
print("TARGET INTERFACE QUESTIONS")
print("=" * 72)
print("1. Where are Evidence domain objects defined?")
print("2. Where are Metric/domain objects defined?")
print("3. Which registry/repository APIs already persist knowledge?")
print("4. Which historical bridge APIs can accept structured evidence?")
print("5. Is there an existing intelligence pipeline suitable for 0695.7?")
print("6. Which existing tests cover these interfaces?")
print()
print("DIAGNOSTIC COMPLETED")
