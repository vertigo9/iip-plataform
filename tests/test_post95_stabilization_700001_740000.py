import json
import subprocess
import sys
from pathlib import Path

BASELINE = {
    "passed": 715,
    "skipped": 4,
    "coverage": 95.02,
    "gate": True,
}


def test_release_baseline_metadata():
    assert BASELINE["passed"] == 715
    assert BASELINE["skipped"] == 4
    assert BASELINE["coverage"] >= 95.0
    assert BASELINE["gate"] is True


def test_project_configuration_and_test_tree():
    root = Path.cwd()
    assert (root / "pyproject.toml").exists()
    assert (root / "tests").is_dir()
    assert (root / "src" / "iip").is_dir()


def test_protected_release_files_present():
    root = Path.cwd()
    required = (
        "tests/test_last_mile_620001_660000.py",
        "tests/test_final_gate_540001_580000.py",
        "tests/test_final95_behavior_460001_500000.py",
        "tests/test_portfolio_matrix_contract_fix1.py",
        "tests/test_portfolio_validation_import_fix1.py",
    )
    missing = [item for item in required if not (root / item).exists()]
    assert not missing, f"Arquivos de checkpoint ausentes: {missing}"


def test_release_command_available():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "tests collected" in result.stdout or "items" in result.stdout


def test_no_legacy_broken_portfolio_operations_import():
    path = Path("src/iip/portfolio/validation.py")
    text = path.read_text(encoding="utf-8-sig")
    assert "from .operations import ProviderOperations" not in text
    assert "from iip.providers.operations import ProviderOperations" in text


def test_portfolio_matrix_uses_operational_registry():
    path = Path("src/iip/portfolio/matrix.py")
    text = path.read_text(encoding="utf-8-sig")
    assert "from iip.providers.registry import" in text
    assert "FUND_MANAGERS" in text
    assert "manifest_map" in text


def test_release_checkpoint_json_matches_baseline():
    data = json.loads(
        Path("POST95_RELEASE_CHECKPOINT.json").read_text(encoding="utf-8-sig")
    )
    assert data["release"] == "D-OBSIDIAN-06.2"
    assert data["tests"]["passed"] == 715
    assert data["tests"]["skipped"] == 4
    assert data["coverage"]["percent"] == 95.02
    assert data["coverage"]["gate"] == "PASS"
