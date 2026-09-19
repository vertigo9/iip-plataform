from iip.analysis import AssetData, ETFAnalyzer, FIIAnalyzer
from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.sync import ProjectionStatus


def make_fii_report(dividend_yield=8.5, price=95.5):
    data = AssetData(
        symbol="BTLG11",
        sector="Logística",
        industry="Galpões",
        price=price,
        financials={"dividend_yield": dividend_yield},
    )
    return FIIAnalyzer().analyze(data)


def test_sync_analysis_projection_creates_note(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    report = make_fii_report()

    result = bridge.sync_analysis_projection(report, "BTLG11", "FII")

    assert result.status == ProjectionStatus.CREATED
    assert result.path.exists()


def test_sync_analysis_projection_uses_scoring_note_path(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    report = make_fii_report()

    result = bridge.sync_analysis_projection(report, "BTLG11", "FII")

    assert result.path.name == "BTLG11 - Score e Ranking.md"
    assert "FIIs" in str(result.path)


def test_sync_analysis_projection_content_includes_score_and_pillars(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    report = make_fii_report()

    result = bridge.sync_analysis_projection(report, "BTLG11", "FII")
    content = result.path.read_text(encoding="utf-8")

    assert f"{report.overall_score:.1f}" in content
    assert report.recommendation in content
    assert "business_model" in content
    assert "IIP:BEGIN IIP:analysis" in content
    assert "IIP:END IIP:analysis" in content


def test_sync_analysis_projection_is_idempotent_for_unchanged_report(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    report = make_fii_report()

    bridge.sync_analysis_projection(report, "BTLG11", "FII")
    second = bridge.sync_analysis_projection(report, "BTLG11", "FII")

    assert second.status == ProjectionStatus.UNCHANGED


def test_sync_analysis_projection_updates_on_score_change_without_duplicating(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))

    first = bridge.sync_analysis_projection(
        make_fii_report(dividend_yield=2.0), "BTLG11", "FII"
    )
    second = bridge.sync_analysis_projection(
        make_fii_report(dividend_yield=12.0), "BTLG11", "FII"
    )

    assert first.status == ProjectionStatus.CREATED
    assert second.status == ProjectionStatus.UPDATED
    content = second.path.read_text(encoding="utf-8")
    assert content.count("IIP:BEGIN IIP:analysis") == 1


def test_sync_analysis_projection_preserves_human_content_around_it(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    report = make_fii_report()

    result = bridge.sync_analysis_projection(report, "BTLG11", "FII")
    result.path.write_text(
        "# Notas minhas\n\n"
        "Comprei mais cotas em agosto.\n\n" + result.path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    bridge.sync_analysis_projection(
        make_fii_report(dividend_yield=12.0), "BTLG11", "FII"
    )
    content = result.path.read_text(encoding="utf-8")

    assert "Comprei mais cotas em agosto." in content


def test_sync_analysis_projection_works_for_etf(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    data = AssetData(symbol="BOVA11", sector="Renda Variável", industry="Índice Amplo")
    report = ETFAnalyzer().analyze(data)

    result = bridge.sync_analysis_projection(report, "BOVA11", "ETF")

    assert result.status == ProjectionStatus.CREATED
    assert "ETFs" in str(result.path)
