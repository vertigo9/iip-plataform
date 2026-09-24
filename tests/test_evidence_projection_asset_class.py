"""``sync_evidence_projection`` used to hardcode ``asset_class="FII"`` for every ticker,
misfiling the sources section of non-FII positions into the FIIs folder (a pre-existing bug,
documented in ``iip.portfolio.historical_series._persist_atlas_evidence``, confirmed live
against the real vault on 24/09/2026: 17 misplaced ``{ticker} - Fontes.md`` notes). Fixed by
resolving the real class from the Registry (``_locator_asset_class``), following the taxonomy
already in use by the vault's existing note-sets -- not the locator's own declared (but never
actually used) ``"fi-infra" -> "FIInfra"`` alias, which this fix deliberately does NOT touch
(a separate, still-open question)."""

import datetime as dt

import pytest

from iip.knowledge.bridge import KnowledgeBridge, _locator_asset_class
from iip.knowledge.models import Evidence


def _evidence(ticker: str, **overrides) -> Evidence:
    defaults = {
        "evidence_id": f"test:{ticker}:1",
        "ticker": ticker,
        "date": dt.date(2026, 9, 24),
        "source_type": "historical_metric",
        "source_url": None,
        "title": "teste",
        "document_hash": "abc123",
        "relevant_facts": ("metric=teste",),
    }
    defaults.update(overrides)
    return Evidence(**defaults)


@pytest.mark.parametrize(
    "ticker, expected_folder",
    [
        ("BTLG11", "FIIs"),  # fund + FII
        ("BBSE3", "Equities"),  # equity
        (
            "CDII11",
            "FixedIncome",
        ),  # fund + FI-Infra -- NÃO "FIInfra" (regressão central)
        ("CRAA11", "FIAgro"),  # fund + FI-Agro
        ("LFTB11", "ETFs"),  # etf
        ("AXIA3", "FixedIncome"),  # fixed_income puro
    ],
)
def test_sync_evidence_projection_resolves_the_real_class(
    tmp_path, ticker, expected_folder
):
    bridge = KnowledgeBridge(str(tmp_path))

    result = bridge.sync_evidence_projection(_evidence(ticker))

    assert result.path.parts[-3] == expected_folder, result.path
    assert result.path.parts[-2] == ticker


def test_fi_infra_never_resolves_to_the_locators_own_declared_alias():
    """Regressão explícita: alguém pode, no futuro, tentar "corrigir" isto reaproveitando o
    alias que o locator já declara (``"fi-infra" -> "FIInfra"``) -- essa pasta nunca existiu
    no vault real. FI-Infra deve continuar resolvendo para "fixed_income", não "fi-infra".
    """
    assert _locator_asset_class("CDII11") == "fixed_income"
    assert _locator_asset_class("CDII11") != "fi-infra"


def test_sync_evidence_projection_resolves_a_closed_asset(tmp_path):
    """BTCI11 está encerrado (fora de PORTFOLIO_ASSETS), mas ainda tem evidência histórica
    legítima -- a resolução precisa olhar também os ativos encerrados."""
    bridge = KnowledgeBridge(str(tmp_path))

    result = bridge.sync_evidence_projection(_evidence("BTCI11"))

    assert result.path.parts[-3] == "FIIs"


def test_sync_evidence_projection_raises_for_a_ticker_outside_the_registry(tmp_path):
    bridge = KnowledgeBridge(str(tmp_path))

    with pytest.raises(ValueError, match="não está no registro"):
        bridge.sync_evidence_projection(_evidence("NAOEXISTE99"))


def test_sync_evidence_projection_content_is_unaffected_by_the_fix(tmp_path):
    """A correção mexe só na PASTA resolvida, nunca no conteúdo projetado."""
    bridge = KnowledgeBridge(str(tmp_path))

    result = bridge.sync_evidence_projection(
        _evidence("BBSE3", source_type="historical_metric", title="b3_cotahist:BBSE3")
    )
    content = result.path.read_text(encoding="utf-8")

    assert "Tipo: historical_metric" in content
    assert "Título: b3_cotahist:BBSE3" in content
    assert "metric=teste" in content
