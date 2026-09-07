from pathlib import Path

from iip.knowledge import AssetNoteProjector, ProjectionStatus, ProjectionSyncEngine


def test_empty_content_is_skipped_without_creating_file(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    result = engine.sync_section(path, "status", "   \n")

    assert result.status is ProjectionStatus.SKIPPED
    assert not path.exists()


def test_existing_note_without_managed_section_is_updated(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"
    path.write_text("# PCIP11\n\nNota humana.\n", encoding="utf-8")

    result = engine.sync_section(path, "status", "MANTER")
    text = path.read_text(encoding="utf-8")

    assert result.status is ProjectionStatus.UPDATED
    assert "Nota humana." in text
    assert "MANTER" in text


def test_existing_managed_content_with_crlf_is_unchanged(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"
    engine.sync_section(path, "status", "MANTER")
    path.write_text(
        path.read_text(encoding="utf-8").replace("\n", "\r\n"), encoding="utf-8"
    )

    result = engine.sync_section(path, "status", "MANTER")

    assert result.status is ProjectionStatus.UNCHANGED


def test_fingerprint_normalizes_line_endings_and_outer_newlines():
    from iip.knowledge.sync import ProjectionFingerprint

    left = ProjectionFingerprint.from_content("status", "MANTER\n")
    right = ProjectionFingerprint.from_content("status", "\r\nMANTER\r\n")

    assert left == right


def test_second_update_after_created_section_is_idempotent(tmp_path: Path):
    engine = ProjectionSyncEngine(AssetNoteProjector(tmp_path / "vault"))
    path = tmp_path / "note.md"

    first = engine.sync_section(path, "status", "MANTER")
    updated = engine.sync_section(path, "status", "AUMENTAR")
    again = engine.sync_section(path, "status", "AUMENTAR")

    assert first.status is ProjectionStatus.CREATED
    assert updated.status is ProjectionStatus.UPDATED
    assert again.status is ProjectionStatus.UNCHANGED
    assert path.read_text(encoding="utf-8").count("<!-- IIP:BEGIN status -->") == 1
