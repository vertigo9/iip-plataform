from pathlib import Path

from iip.harvest.patria import DEFAULT_BASE, _safe_name


def test_default_url_is_patria():
    assert "realestate.patria.com" in DEFAULT_BASE
    assert "{ticker}" in DEFAULT_BASE


def test_safe_name_removes_problematic_characters():
    result = _safe_name("Relatório: PCIP11 / Julho 2026?")
    assert ":" not in result
    assert "/" not in result
    assert "PCIP11" in result


def test_project_patch_contains_expected_entrypoints():
    root = Path(__file__).resolve().parents[1]
    assert (root / "scripts" / "patria_harvester.py").exists()
    assert (root / "tests" / "test_patria_harvester.py").exists()
