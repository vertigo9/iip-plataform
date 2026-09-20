import ast
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from iip.obsidian.exposure_report import render_exposure_report
from iip.portfolio.exposure import build_exposure
from iip.portfolio.registry import (
    ALL_PORTFOLIO_ASSETS,
    CLOSED_ASSETS,
    PORTFOLIO_ASSETS,
    assets_by_class,
    assets_refreshable_now,
    assets_with_cnpj,
    get_asset,
)
from iip.portfolio.source_policy import PortfolioSourcePolicyResolver
from iip.portfolio.vault_snapshot import parse_current_snapshot
from iip.universal.portfolio_state import PortfolioState, PositionState

CLOSED = {"BTCI11": "2026-09-18", "PVBI11": "2026-08-14"}
TODAY = date(2026, 9, 20)


# --- the registry keeps closed positions, with their data, out of the active list ----------


def test_the_two_closed_positions_are_kept_with_their_closing_date():
    assert {a.ticker: a.closed_on for a in CLOSED_ASSETS} == CLOSED
    for asset in CLOSED_ASSETS:
        assert "zerada" in asset.closure_note


def test_closed_positions_keep_every_piece_of_their_data():
    btci = get_asset("BTCI11", include_closed=True)
    pvbi = get_asset("PVBI11", include_closed=True)

    assert (btci.cnpj, btci.manager, btci.segment) == (
        "09.552.812/0001-14",
        "BTG Pactual",
        "Crédito Imobiliário",
    )
    assert (pvbi.cnpj, pvbi.manager, pvbi.structure) == (
        "35.652.102/0001-76",
        "Pátria",
        "Tijolo",
    )


def test_the_active_list_is_the_registry_minus_the_closed_ones():
    assert len(ALL_PORTFOLIO_ASSETS) == len(PORTFOLIO_ASSETS) + len(CLOSED_ASSETS)
    assert not {a.ticker for a in PORTFOLIO_ASSETS} & set(CLOSED)
    assert {a.ticker for a in ALL_PORTFOLIO_ASSETS} >= set(CLOSED)
    assert all(a.closed_on is None for a in PORTFOLIO_ASSETS)
    assert len({a.ticker for a in ALL_PORTFOLIO_ASSETS}) == len(ALL_PORTFOLIO_ASSETS)


def test_get_asset_skips_closed_positions_unless_asked():
    assert get_asset("BTCI11") is None and get_asset("pvbi11") is None
    assert get_asset("btci11", include_closed=True).ticker == "BTCI11"
    assert get_asset("XPML11") is not None  # os demais não mudam


def test_reopening_a_position_is_just_clearing_the_closing_date():
    reopened = replace(get_asset("BTCI11", include_closed=True), closed_on=None)
    assert reopened.closed_on is None
    # tudo o mais é idêntico: nada do histórico se perde ao reativar
    original = get_asset("BTCI11", include_closed=True)
    assert replace(reopened, closed_on=original.closed_on) == original


# --- what the daily job walks over no longer includes them ---------------------------------


def test_the_registry_queries_the_job_uses_skip_closed_positions():
    for query in (
        assets_with_cnpj(),
        assets_refreshable_now(),
        assets_by_class("fund"),
        PortfolioSourcePolicyResolver().assets,
    ):
        assert not {a.ticker for a in query} & set(CLOSED)


def test_the_other_35_positions_are_untouched():
    assert len(PORTFOLIO_ASSETS) == 35
    tickers = {a.ticker for a in PORTFOLIO_ASSETS}
    assert {"AXIA3", "LFTB11", "XPML11", "HGRU11", "BBSE3", "CRAA11"} <= tickers


def test_only_the_snapshot_reader_and_the_exposure_look_at_closed_positions():
    """Quem percorre ``ALL_PORTFOLIO_ASSETS`` enxerga as encerradas; o job só usa as ativas."""
    users = set()
    for path in Path("src/iip").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        if any(
            isinstance(node, ast.Name) and node.id == "ALL_PORTFOLIO_ASSETS"
            for node in ast.walk(tree)
        ):
            users.add(str(path).replace("\\", "/"))

    assert users == {
        "src/iip/portfolio/registry.py",
        "src/iip/portfolio/vault_snapshot.py",
        "src/iip/portfolio/exposure.py",
        # valida o ticker de uma exceção contra TODAS as ações, encerradas incluídas
        "src/iip/portfolio_data/valuation_exceptions.py",
    }


# --- a closed position that comes back to the snapshot is noticed, not silently ignored ----


def _state(*tickers):
    positions = tuple(
        PositionState(
            ticker=t,
            quantity=1.0,
            market_value=1000.0,
            weight=0.0,
            asset_class="fund",
        )
        for t in tickers
    )
    return PortfolioState(
        as_of="2026-09-20",
        positions=positions,
        total_value=1000.0 * len(positions),
    )


def test_a_closed_position_is_not_reported_as_missing_from_the_snapshot():
    report = build_exposure(_state("XPML11"), today=TODAY)

    assert "BTCI11" not in report.missing_from_snapshot
    assert "PVBI11" not in report.missing_from_snapshot
    assert report.closed_in_snapshot == ()


def test_a_closed_position_that_returns_is_flagged_and_keeps_its_classification():
    report = build_exposure(_state("XPML11", "BTCI11"), today=TODAY)

    assert report.closed_in_snapshot == (("BTCI11", "2026-09-18"),)
    assert "BTCI11" not in report.missing_from_snapshot
    classes = {
        r.label: r.count
        for r in next(d for d in report.dimensions if d.name == "Gestora").rows
    }
    assert (
        classes.get("BTG Pactual") == 1
    )  # a gestora vem do registro, não caiu em "sem classificação"


def test_the_note_tells_the_user_how_to_reactivate_a_returned_position():
    report = build_exposure(_state("XPML11", "BTCI11"), today=TODAY)

    text = render_exposure_report(report)

    assert "Posição de ativo encerrado voltou ao snapshot" in text
    assert "`BTCI11`" in text and "2026-09-18" in text
    assert "não o atualiza, avalia nem decide" in text and "closed_on" in text


def test_the_snapshot_parser_keeps_the_registry_data_of_a_returned_position(tmp_path):
    path = tmp_path / "Current.md"
    path.write_text(
        "\n".join(
            [
                "| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | "
                "Peso alvo | Status |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
                "| BTCI11 | BTCI11 | fii | 283,0000 | R$ 9,21 | R$ 9,14 | R$ 2.586,62 "
                "| 100,00% |  | active |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    [position] = parse_current_snapshot(path).positions

    assert position.ticker == "BTCI11"
    assert (position.structure, position.manager) == ("Papel", "BTG Pactual")


@pytest.mark.parametrize("ticker", ["BTCI11", "PVBI11"])
def test_a_closed_position_still_resolves_its_provider_for_when_it_returns(ticker):
    resolver = PortfolioSourcePolicyResolver(assets=ALL_PORTFOLIO_ASSETS)

    assert resolver.resolve(ticker) is not None
    assert PortfolioSourcePolicyResolver().resolve(ticker) is None
