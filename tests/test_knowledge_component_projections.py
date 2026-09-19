"""sync_identity_projection / sync_portfolio_composition_projection /
sync_distributions_projection / sync_events_projection /
sync_performance_projection / sync_sources_summary_projection --
real-data-only versions of the 6 component notes PCIP11 had from a
one-off manual pilot, now backed only by what this project's real
sources (CVM/B3/Sparta) actually provide."""

from iip.knowledge.bridge import KnowledgeBridge
from iip.knowledge.models import Evidence
from iip.knowledge.sync import ProjectionStatus
from iip.portfolio.historical_series import HistoricalObservation, HistoricalSeries
from iip.portfolio.registry import ClassificationProvenance, PortfolioAsset


def _asset(**overrides) -> PortfolioAsset:
    defaults = {
        "ticker": "BTCI11",
        "asset_class": "fund",
        "subtype": "FII",
        "structure": "Papel",
        "segment": "Crédito Imobiliário",
        "manager": "BTG Pactual",
        "source_url": "https://btgpactual.com/btci11",
        "indexation": ("CDI",),
        "risk_profile": "Médio",
        "strategy": "Recebíveis",
        "classification_provenance": ClassificationProvenance.USER,
        "cnpj": "09.552.812/0001-14",
    }
    defaults.update(overrides)
    return PortfolioAsset(**defaults)


def _observation(
    period, valor=10.0, pl=1_000_000.0, dy=None, cotistas=100.0, valor_ativo=1_100_000.0
):
    return HistoricalObservation(
        period=period,
        patrimonio_liquido=pl,
        valor_patrimonial_cotas=valor,
        dividend_yield_mes=dy,
        rentabilidade_patrimonial_mes=0.0,
        valor_ativo=valor_ativo,
        total_numero_cotistas=cotistas,
        document_id="doc",
        document_hash="hash",
        discovered_year=2026,
    )


def test_sync_identity_projection_writes_verified_registry_fields(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    asset = _asset()

    result = bridge.sync_identity_projection(asset, "BTCI11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "CNPJ: 09.552.812/0001-14" in content
    assert "Gestora/Administrador: BTG Pactual" in content
    assert "Estrutura: Papel" in content
    assert "IIP:BEGIN IIP:identity" in content


def test_sync_identity_projection_handles_missing_fields_honestly(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    asset = _asset(structure=None, manager=None, indexation=())

    result = bridge.sync_identity_projection(asset, "BTCI11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "Estrutura: não informado" in content
    assert "Gestora/Administrador: não informado" in content
    assert "Indexadores: não informado" in content


def test_sync_portfolio_composition_projection_uses_latest_observation(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="BTCI11",
        cnpj="09552812000114",
        provider="cvm",
        observations=(_observation("2026-07-01", pl=500_000.0, cotistas=200.0),),
        source_documents=(),
    )

    result = bridge.sync_portfolio_composition_projection(series, "BTCI11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "Patrimônio líquido (2026-07-01): R$ 500,000.00" in content
    assert "Número de cotistas: 200" in content
    assert "Composição individual de créditos" in content


def test_sync_portfolio_composition_projection_handles_empty_series(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="LFTB11",
        cnpj="",
        provider="b3_cotahist",
        observations=(),
        source_documents=(),
    )

    result = bridge.sync_portfolio_composition_projection(series, "LFTB11", "etf")
    content = result.path.read_text(encoding="utf-8")

    assert "Sem série histórica persistida" in content


def test_sync_portfolio_composition_projection_handles_source_without_pl_fields(
    tmp_path,
):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="BBSE3",
        cnpj="",
        provider="b3_cotahist",
        observations=(
            _observation(
                "2026-09-17", valor=40.0, pl=None, cotistas=None, valor_ativo=None
            ),
        ),
        source_documents=(),
    )

    result = bridge.sync_portfolio_composition_projection(series, "BBSE3", "equity")
    content = result.path.read_text(encoding="utf-8")

    assert "não reporta patrimônio/cotistas" in content


def test_sync_distributions_projection_computes_ttm_from_fii_series(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="BTCI11",
        cnpj="09552812000114",
        provider="cvm",
        observations=tuple(
            _observation(f"2026-{m:02d}-01", dy=0.01) for m in range(1, 8)
        ),
        source_documents=(),
    )

    result = bridge.sync_distributions_projection("BTCI11", "fii", series=series)
    content = result.path.read_text(encoding="utf-8")

    assert "Dividend yield TTM" in content
    assert "7.00%" in content  # 7 months * 1% each


def test_sync_distributions_projection_uses_snapshot_yield_for_equity(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))

    result = bridge.sync_distributions_projection(
        "BBSE3", "equity", snapshot_yield_pct=4.2
    )
    content = result.path.read_text(encoding="utf-8")

    assert "Dividend yield (snapshot, bolsai): 4.20%" in content


def test_sync_distributions_projection_honest_when_nothing_available(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))

    result = bridge.sync_distributions_projection("LFTB11", "etf")
    content = result.path.read_text(encoding="utf-8")

    assert "Sem dado de distribuição disponível" in content


def test_sync_events_projection_lists_real_adjustments(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="BTCI11",
        cnpj="09552812000114",
        provider="cvm",
        observations=(_observation("2023-01-01"),),
        source_documents=(),
        adjustments=(
            {
                "period": "2023-01-01",
                "field": "valor_patrimonial_cotas",
                "factor": 8.99717,
                "reason": "quota split/grouping confirmed via patrimonio_liquido continuity",
            },
        ),
    )

    result = bridge.sync_events_projection(series, "BTCI11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "2023-01-01" in content
    assert "8.997170" in content


def test_sync_events_projection_includes_user_confirmed_manual_events(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="PCIP11",
        cnpj="28729197000113",
        provider="cvm",
        observations=(_observation("2026-01-01"),),
        source_documents=(),
    )

    result = bridge.sync_events_projection(
        series,
        "PCIP11",
        "fii",
        manual_events=(
            "24/09/2025: fundo passou a negociar sob o ticker PCIP11 "
            "(anteriormente CVBI11), confirmado pelo usuário",
        ),
    )
    content = result.path.read_text(encoding="utf-8")

    assert "CVBI11" in content
    assert "24/09/2025" in content


def test_sync_events_projection_reports_no_events_honestly(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="BTCI11",
        cnpj="09552812000114",
        provider="cvm",
        observations=(_observation("2026-01-01"),),
        source_documents=(),
    )

    result = bridge.sync_events_projection(series, "BTCI11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "Nenhum desdobramento/grupamento" in content


def test_sync_performance_projection_shows_real_range(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    series = HistoricalSeries(
        ticker="BTCI11",
        cnpj="09552812000114",
        provider="cvm",
        observations=(
            _observation("2021-01-01", valor=90.5),
            _observation("2026-07-01", valor=10.08),
        ),
        source_documents=(),
    )

    result = bridge.sync_performance_projection(series, "BTCI11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "Observações: 2" in content
    assert "2021-01-01 a 2026-07-01" in content
    assert "benchmark (IFIX/CDI) não disponível" in content


def test_sync_sources_summary_projection_lists_real_evidence(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    bridge.persist_evidence(
        Evidence(
            evidence_id="cvm:BTCI11:2026:abc123",
            ticker="BTCI11",
            date=__import__("datetime").date(2026, 9, 1),
            source_type="atlas",
            source_url="https://dados.cvm.gov.br/x.zip",
            title="CVM FII Informe Mensal 2026",
            document_hash="abc123",
        )
    )

    result = bridge.sync_sources_summary_projection("BTCI11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "Total de evidências no Atlas: 1" in content
    assert "CVM FII Informe Mensal 2026" in content


def test_sync_sources_summary_projection_honest_when_no_evidence(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))

    result = bridge.sync_sources_summary_projection("XPTO11", "fii")
    content = result.path.read_text(encoding="utf-8")

    assert "Nenhuma evidência registrada" in content


def test_component_projections_are_idempotent(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))
    asset = _asset()

    bridge.sync_identity_projection(asset, "BTCI11", "fii")
    second = bridge.sync_identity_projection(asset, "BTCI11", "fii")

    assert second.status == ProjectionStatus.UNCHANGED
