from pathlib import Path

from iip.knowledge import (
    AssetNoteProjector,
    ProjectionStatus,
    ProjectionSyncEngine,
)


def test_first_sync_creates_note_and_fingerprint_is_deterministic(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    first = engine.sync_section(path, "status", "MANTER")
    second = engine.sync_section(path, "status", "MANTER")

    assert first.status is ProjectionStatus.CREATED
    assert second.status is ProjectionStatus.UNCHANGED
    assert first.fingerprint == second.fingerprint


def test_changed_managed_content_is_updated_without_duplication(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    engine.sync_section(path, "status", "MANTER")
    result = engine.sync_section(path, "status", "AUMENTAR")
    text = path.read_text(encoding="utf-8")

    assert result.status is ProjectionStatus.UPDATED
    assert text.count("<!-- IIP:BEGIN status -->") == 1
    assert "MANTER" not in text
    assert "AUMENTAR" in text


def test_human_content_is_preserved_on_update(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"
    path.write_text("# PCIP11\n\nObservação manual.\n", encoding="utf-8")

    engine.sync_section(path, "status", "MANTER")
    engine.sync_section(path, "status", "AUMENTAR")
    text = path.read_text(encoding="utf-8")

    assert "Observação manual." in text
    assert "AUMENTAR" in text
    assert "MANTER" not in text


def test_different_sections_have_independent_fingerprints_and_updates(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    a = engine.sync_section(path, "status", "MANTER")
    b = engine.sync_section(path, "summary", "Resumo")
    a2 = engine.sync_section(path, "status", "MANTER")

    assert a.fingerprint.digest != b.fingerprint.digest
    assert a2.status is ProjectionStatus.UNCHANGED
    text = path.read_text(encoding="utf-8")
    assert "MANTER" in text and "Resumo" in text


def test_asset_sync_uses_canonical_vault_path(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))

    result = engine.sync_asset_section(
        "pcip11", "FII", "events", "event-sync", "Novo evento"
    )

    assert result.status is ProjectionStatus.CREATED
    assert (
        result.path
        == (
            tmp_path
            / "vault"
            / "01_Assets"
            / "FIIs"
            / "PCIP11"
            / "PCIP11 - Eventos e Reestruturações.md"
        ).resolve()
    )


def test_notes_reach_canonical_note(tmp_path: Path):
    """FIX regression: mudança apenas no rodapé não pode dar UNCHANGED."""
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    engine.sync_section(path, "status", "MANTER", notes="Rodapé A")
    second = engine.sync_section(path, "status", "MANTER", notes="Rodapé B")
    text = path.read_text(encoding="utf-8")

    assert second.status is ProjectionStatus.UPDATED
    assert "> Rodapé: Rodapé B" in text
    assert "Rodapé A" not in text
    assert "MANTER" in text


def test_notes_are_idempotent_when_unchanged(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    first = engine.sync_section(path, "status", "MANTER", notes="Rodapé A")
    second = engine.sync_section(path, "status", "MANTER", notes="Rodapé A")

    assert first.status is ProjectionStatus.CREATED
    assert second.status is ProjectionStatus.UNCHANGED
    assert "> Rodapé: Rodapé A" in path.read_text(encoding="utf-8")


def test_no_notes_keeps_legacy_behavior(tmp_path: Path):
    """Sem o parâmetro, comportamento idêntico ao anterior (sem rodapé)."""
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    first = engine.sync_section(path, "status", "MANTER")
    second = engine.sync_section(path, "status", "MANTER")

    assert first.status is ProjectionStatus.CREATED
    assert second.status is ProjectionStatus.UNCHANGED
    assert "Rodapé:" not in path.read_text(encoding="utf-8")