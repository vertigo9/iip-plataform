"""sync_valuation_projection / sync_quantitative_projection /
sync_cross_asset_projection -- the three AssetE2ERunner stages that,
until now, only ever printed their results and never persisted them
anywhere (unlike sync_analysis_projection)."""

from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.sync import ProjectionStatus
from iip.portfolio_data.valuation import ValuationMethod, build_snapshot
from iip.universal.concentration import ConcentrationItem


def test_sync_valuation_projection_writes_frontmatter_and_section(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    snapshot = build_snapshot("BBSE3", ValuationMethod.BOOK, 5.61, 40.59)

    result = bridge.sync_valuation_projection(snapshot, "BBSE3", "equity")

    assert result.status == ProjectionStatus.CREATED
    content = result.path.read_text(encoding="utf-8")
    assert "IIP:BEGIN IIP:valuation" in content
    assert "fair_value: 5.61" in content
    assert "market_price: 40.59" in content
    assert "margin_of_safety:" in content
    assert "Margem de segurança:" in content


def test_sync_valuation_projection_handles_missing_market_price(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    snapshot = build_snapshot("LFTB11", ValuationMethod.BOOK, None, None)

    result = bridge.sync_valuation_projection(snapshot, "LFTB11", "etf")
    content = result.path.read_text(encoding="utf-8")

    assert "indisponível" in content
    assert "margin_of_safety" not in content  # None dropped, not fabricated


def test_sync_valuation_projection_is_idempotent(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    snapshot = build_snapshot("BBSE3", ValuationMethod.BOOK, 5.61, 40.59)

    bridge.sync_valuation_projection(snapshot, "BBSE3", "equity")
    second = bridge.sync_valuation_projection(snapshot, "BBSE3", "equity")

    assert second.status == ProjectionStatus.UNCHANGED


def test_sync_quantitative_projection_writes_frontmatter_and_section(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    stats = {
        "observations": 178.0,
        "mean_price": 36.94,
        "price_volatility": 2.55,
        "mean_return": 0.0008,
        "return_volatility": 0.0157,
        "total_return": 0.1307,
    }

    result = bridge.sync_quantitative_projection(stats, "BBSE3", "equity")
    content = result.path.read_text(encoding="utf-8")

    assert "IIP:BEGIN IIP:quantitative" in content
    assert "quantitative_observations: 178.0" in content
    assert "total_return: 0.1307" in content
    assert "return_volatility: 0.0157" in content


def test_sync_cross_asset_projection_filters_to_own_dimensions(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    concentrations = (
        ConcentrationItem(
            dimension="manager",
            value="BTG Pactual",
            weight=0.047,
            limit=0.2,
            breached=False,
        ),
        ConcentrationItem(
            dimension="manager", value="Sparta", weight=0.25, limit=0.2, breached=True
        ),
        ConcentrationItem(
            dimension="segment",
            value="Credito Imobiliario",
            weight=0.09,
            limit=0.3,
            breached=False,
        ),
    )

    result = bridge.sync_cross_asset_projection(
        concentrations,
        "BTCI11",
        "fii",
        own_dimensions=("BTG Pactual", "Credito Imobiliario"),
    )
    content = result.path.read_text(encoding="utf-8")

    assert "BTG Pactual" in content
    assert "Credito Imobiliario" in content
    assert "Sparta" not in content  # not this asset's own dimension
    assert "Grupos analisados na carteira: 3" in content


def test_sync_cross_asset_projection_flags_breach_in_frontmatter(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    concentrations = (
        ConcentrationItem(
            dimension="manager", value="Sparta", weight=0.25, limit=0.2, breached=True
        ),
    )

    result = bridge.sync_cross_asset_projection(
        concentrations, "CRAA11", "fii", own_dimensions=("Sparta",)
    )
    content = result.path.read_text(encoding="utf-8")

    assert "concentration_breaches: 1" in content
    assert "EXCEDIDO" in content


def test_sync_cross_asset_projection_handles_no_own_dimensions(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    concentrations = (
        ConcentrationItem(
            dimension="manager", value="Sparta", weight=0.25, limit=0.2, breached=True
        ),
    )

    result = bridge.sync_cross_asset_projection(concentrations, "XYZ11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "nenhuma dimensão de concentração própria identificada" in content
    assert "concentration_breaches: 0" in content
