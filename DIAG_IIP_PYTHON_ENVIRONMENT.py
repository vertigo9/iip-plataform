from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path


ROOT = Path.cwd()


def print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def module_info(name: str) -> dict:
    result = {
        "module": name,
        "importable": False,
        "file": "",
        "error": "",
    }
    try:
        mod = importlib.import_module(name)
        result["importable"] = True
        result["file"] = str(getattr(mod, "__file__", "") or "")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def find_symbols(root: Path, names: set[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {name: [] for name in names}
    if not root.exists():
        return found

    for py_file in root.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        for name in names:
            if name in text:
                found[name].append(str(py_file.relative_to(ROOT)))
    return found


print_section("IIP - PYTHON ENVIRONMENT / ARCHITECTURE DIAGNOSTIC")
print(f"Python        : {sys.version.splitlines()[0]}")
print(f"Executable    : {sys.executable}")
print(f"Platform      : {platform.platform()}")
print(f"Working dir   : {ROOT}")

print_section("1. PROJECT STRUCTURE")

paths = [
    "pyproject.toml",
    "src",
    "src/iip",
    "src/iip/atlas",
    "src/iip/knowledge",
    "src/iip/cycle",
    "src/iip/decision",
    "src/iip/portfolio_data",
    "tests",
    "reports",
]

for rel in paths:
    state = "FOUND" if exists(rel) else "MISSING"
    print(f"{state:<8} {rel}")

print_section("2. IIP PYTHON MODULES")

modules = [
    "iip",
    "iip.atlas",
    "iip.knowledge",
    "iip.cycle",
    "iip.decision",
    "iip.portfolio_data",
]

module_results = [module_info(name) for name in modules]

for item in module_results:
    if item["importable"]:
        print(f"PASS     {item['module']:<24} {item['file']}")
    else:
        print(f"FAIL     {item['module']:<24} {item['error']}")

print_section("3. IMPORTANT PYTHON FILES")

important_files = [
    "src/iip/atlas/history.py",
    "src/iip/atlas/batch.py",
    "src/iip/cycle/historical_bridge.py",
    "src/iip/knowledge/bridge.py",
    "src/iip/knowledge/repository.py",
    "src/iip/portfolio_data/market_data.py",
    "src/iip/portfolio_data/yield_metrics.py",
    "src/iip/portfolio_data/valuation.py",
]

for rel in important_files:
    state = "FOUND" if exists(rel) else "MISSING"
    print(f"{state:<8} {rel}")

print_section("4. DOMAIN SYMBOL SEARCH")

symbols = {
    "Evidence",
    "Metric",
    "Registry",
    "Repository",
    "Historical",
    "Promotion",
    "Lineage",
}

search = find_symbols(ROOT / "src" / "iip", symbols)

for symbol in sorted(symbols):
    files = search[symbol]
    print(f"\n[{symbol}] {len(files)} file(s)")
    for rel in files[:20]:
        print(f"  - {rel}")
    if len(files) > 20:
        print(f"  ... +{len(files) - 20} more")

print_section("5. CURRENT 0695.6 OUTPUTS")

report_files = [
    "reports/PCIP11_EVIDENCE_VALIDATION_0695_5R2.csv",
    "reports/PCIP11_METRIC_EVIDENCE_CANDIDATES_0695_4.csv",
    "reports/PCIP11_STRUCTURED_EVIDENCE_0695_6R2.csv",
    "reports/PCIP11_METRIC_PROMOTION_CANDIDATES_0695_6R2.csv",
    "reports/PCIP11_METRIC_CANDIDATE_AUDIT_0695_6R3R1.csv",
    "reports/PCIP11_SEMANTIC_RESOLUTION_0695_6R4R4.csv",
]

for rel in report_files:
    path = ROOT / rel
    if path.exists():
        size = path.stat().st_size
        print(f"FOUND    {rel} ({size:,} bytes)")
    else:
        print(f"MISSING  {rel}")

print_section("6. PYTHON PACKAGE METADATA")

pyproject = ROOT / "pyproject.toml"
if pyproject.exists():
    try:
        text = pyproject.read_text(encoding="utf-8")
        for needle in [
            "[project]",
            "[tool.pytest",
            "[tool.coverage",
            "[build-system]",
        ]:
            print(f"{'FOUND' if needle in text else 'MISSING':<8} {needle}")
    except Exception as exc:
        print(f"Could not read pyproject.toml: {type(exc).__name__}: {exc}")
else:
    print("pyproject.toml not found.")

print_section("7. TEST DISCOVERY")

tests_dir = ROOT / "tests"
if tests_dir.exists():
    test_files = sorted(tests_dir.rglob("test_*.py"))
    print(f"Test files    : {len(test_files)}")
    for path in test_files[:25]:
        print(f"  - {path.relative_to(ROOT)}")
    if len(test_files) > 25:
        print(f"  ... +{len(test_files) - 25} more")
else:
    print("tests directory not found.")

print_section("8. DIAGNOSTIC JSON")

summary = {
    "python": sys.version.splitlines()[0],
    "executable": sys.executable,
    "root": str(ROOT),
    "project": {
        "pyproject": exists("pyproject.toml"),
        "src_iip": exists("src/iip"),
        "tests": exists("tests"),
    },
    "modules": module_results,
    "important_files": {
        rel: exists(rel) for rel in important_files
    },
    "reports": {
        rel: exists(rel) for rel in report_files
    },
}

print(json.dumps(summary, indent=2, ensure_ascii=False))
print()
print("DIAGNOSTIC COMPLETED")
