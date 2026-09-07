from pathlib import Path

import pytest

from iip.knowledge import AssetNoteProjector


def test_locate_returns_canonical_note_path(tmp_path: Path):
    projection = AssetNoteProjector(tmp_path / "vault").locate(
        "pcip11", "FII", "events"
    )

    assert projection.ticker == "PCIP11"
    assert projection.role == "events"
    assert (
        projection.path
        == (
            tmp_path
            / "vault"
            / "01_Assets"
            / "FIIs"
            / "PCIP11"
            / "PCIP11 - Eventos e Reestruturações.md"
        ).resolve()
    )


def test_project_section_preserves_human_content(tmp_path: Path):
    path = tmp_path / "PCIP11.md"
    path.write_text("# PCIP11\n\nTexto mantido pelo usuário.\n", encoding="utf-8")

    projector = AssetNoteProjector(tmp_path / "vault")
    projector.project_section(path, "IIP:status", "Status atual: MANTER")

    text = path.read_text(encoding="utf-8")
    assert "Texto mantido pelo usuário." in text
    assert "Status atual: MANTER" in text
    assert "<!-- IIP:BEGIN IIP:status -->" in text
    assert "<!-- IIP:END IIP:status -->" in text


def test_project_section_is_idempotent_and_replaces_only_its_block(tmp_path: Path):
    path = tmp_path / "PCIP11.md"
    projector = AssetNoteProjector(tmp_path / "vault")

    projector.project_section(path, "summary", "Versão 1")
    projector.project_section(path, "other", "Outro conteúdo")
    projector.project_section(path, "summary", "Versão 2")

    text = path.read_text(encoding="utf-8")
    assert text.count("<!-- IIP:BEGIN summary -->") == 1
    assert "Versão 1" not in text
    assert "Versão 2" in text
    assert "Outro conteúdo" in text


def test_project_asset_section_creates_only_canonical_note(tmp_path: Path):
    vault = tmp_path / "vault"
    projector = AssetNoteProjector(vault)

    path = projector.project_asset_section(
        "pcip11", "FII", "index", "IIP:identity", "Ticker canônico: PCIP11"
    )

    assert path.exists()
    assert path.parent == vault / "01_Assets" / "FIIs" / "PCIP11"
    assert "Ticker canônico: PCIP11" in path.read_text(encoding="utf-8")


def test_projector_rejects_invalid_role_or_section(tmp_path: Path):
    projector = AssetNoteProjector(tmp_path / "vault")

    with pytest.raises(ValueError):
        projector.locate("PCIP11", "FII", "unknown")

    with pytest.raises(ValueError):
        projector.project_section(tmp_path / "x.md", "", "content")

    with pytest.raises(ValueError):
        projector.project_section(tmp_path / "x.md", "bad\nsection", "content")
