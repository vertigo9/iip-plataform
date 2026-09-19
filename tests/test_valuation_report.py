from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.valuation_report import (
    find_asset_links,
    render_valuation_report,
    write_valuation_report,
)
from iip.portfolio.batch_value import (
    NO_METHOD_PREFIX,
    ValuationOutcome,
    ValuationRunResult,
    value_portfolio,
)
from iip.portfolio.registry import PortfolioAsset
from iip.portfolio_data.valuation_methods import evaluate_valuations
from iip.sources.tesouro_direto import NtnbRate

RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)
AS_OF = date(2026, 9, 18)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _outcome(ticker, asset_class, sector, industry, price, **inputs):
    attempts = evaluate_valuations(
        ticker=ticker,
        asset_class=asset_class,
        sector=sector,
        industry=industry,
        price=price,
        inputs={"ntnb_real_yield": 0.073, **inputs},
    )
    return ValuationOutcome(
        ticker, "ok", "detail", price, attempts, asset_class, f"{sector} / {industry}"
    )


def _result(*outcomes, rate=RATE, note="NTN-B longa: IPCA + 7.30%"):
    return ValuationRunResult(tuple(outcomes), rate, note)


EQUITY = _outcome(
    "CXSE3",
    "equity",
    "Financeiro",
    "Previdência e Seguros",
    20.54,
    lpa=1.43,
    vpa=4.6,
    dividend_per_share=1.26,
    dividend_consistency_years=5,
    payout_ratio=88.0,
)
FII = _outcome(
    "BTLG11",
    "fii",
    "Tijolo",
    "Logístico",
    99.78,
    nav_per_share=106.86,
    dividend_per_share=11.56,
    dividend_yield_ttm=10.82,
)
PAPER = _outcome(
    "HGCR11",
    "fii",
    "Papel",
    "Crédito Imobiliário",
    95.45,
    nav_per_share=97.4,
    dividend_per_share=11.99,
    dividend_yield_ttm=12.31,
)


def _class_row(text, section, ticker):
    """The row of ``ticker`` inside the ``## <section>`` class table (the highlights
    table above it repeats some tickers with other columns)."""
    body = text.split(f"## {section}")[1].split("\n## ")[0]
    return next(
        line
        for line in body.splitlines()
        if line.startswith(f"| {ticker}") or f"|{ticker}]]" in line
    )


# --- rendering -----------------------------------------------------------------------


def test_frontmatter_carries_the_date_and_the_ntnb_rate():
    text = render_valuation_report(_result(EQUITY), as_of=AS_OF)

    head = text.split("---")[1]
    assert "type: valuation_report" in head and "as_of: 2026-09-18" in head
    assert "ntnb_real_yield: 0.073" in head and "ntnb_maturity: 2060-08-15" in head


def test_without_a_rate_the_note_says_so_and_omits_the_rate_fields():
    text = render_valuation_report(
        _result(EQUITY, rate=None, note="taxa real da NTN-B indisponível"), as_of=AS_OF
    )

    assert "ntnb_real_yield" not in text.split("---")[1]
    assert "taxa real da NTN-B indisponível" in text


def test_one_table_per_class_with_that_classs_own_methods():
    text = render_valuation_report(_result(EQUITY, FII), as_of=AS_OF)

    assert "## Ações" in text and "## FIIs" in text
    equity_table = text.split("## Ações")[1].split("## FIIs")[0]
    fii_table = text.split("## FIIs")[1].split("## ")[0]
    assert "| Graham |" in equity_table or "Graham |" in equity_table
    assert "Bazin" in equity_table and "NAV" not in equity_table
    assert "NAV" in fii_table and "Yield" in fii_table and "Graham" not in fii_table


def test_the_lead_method_and_every_value_with_its_margin_are_shown():
    text = render_valuation_report(_result(EQUITY), as_of=AS_OF)

    row = _class_row(text, "Ações", "CXSE3")
    assert "**Bazin**" in row  # dividend-centric sector: Bazin leads
    assert "17.26" in row and "12.17" in row  # Bazin and Graham
    assert "(-16%)" in row and "(-41%)" in row


def test_a_paper_fund_shows_only_the_nav_and_a_dash_for_yield():
    text = render_valuation_report(_result(PAPER), as_of=AS_OF)

    row = _class_row(text, "FIIs", "HGCR11")
    assert "**NAV**" in row and "97.40 (+2%)" in row
    assert row.rstrip().endswith("— |")  # the Yield column has no value


def test_methods_without_value_are_listed_with_their_reason():
    text = render_valuation_report(_result(PAPER), as_of=AS_OF)

    section = text.split("## Métodos sem valor")[1].split("## ")[0]
    assert "HGCR11" in section and "Yield" in section and "CDI" in section


def test_skipped_and_failed_positions_are_reported():
    failed = ValuationOutcome(
        "BAD11",
        "erro",
        "preço indisponível (bolsai: falha/limite diário) — nada gravado",
    )
    skipped = ValuationOutcome("LFTB11", "pulado", f"{NO_METHOD_PREFIX} 'etf'")
    text = render_valuation_report(_result(EQUITY, failed, skipped), as_of=AS_OF)

    assert "## Erros" in text and "BAD11" in text and "nada gravado" in text
    assert "## Não avaliados" in text and "'etf'" in text and "LFTB11" in text


def test_a_source_note_is_shown_when_given():
    text = render_valuation_report(
        _result(EQUITY), as_of=AS_OF, source_note="valores da coleta de 18/09/2026"
    )

    assert "> valores da coleta de 18/09/2026" in text


def test_the_reading_guide_states_the_limits_and_that_it_is_not_a_recommendation():
    text = render_valuation_report(_result(EQUITY), as_of=AS_OF)

    guide = text.split("## Como ler")[1]
    for word in (
        "Graham",
        "Bazin",
        "NAV",
        "Yield",
        "prêmio",
        "calibração",
        "não é recomendação",
        "Método principal",
    ):
        assert word in guide


def test_pipes_in_text_cannot_break_the_table():
    odd = _outcome(
        "KLBN4",
        "equity",
        "Materiais | Básicos",
        "Madeiras e Papel",
        3.88,
        lpa=0.24,
        vpa=1.52,
    )

    text = render_valuation_report(_result(odd), as_of=AS_OF)

    row = _class_row(text, "Ações", "KLBN4")
    assert "Materiais \\| Básicos" in row


# --- links ---------------------------------------------------------------------------


def test_links_are_escaped_in_tables_and_plain_elsewhere():
    links = {"CXSE3": "CXSE3 - Score e Ranking", "HGCR11": "HGCR11 - Score e Ranking"}
    text = render_valuation_report(
        _result(EQUITY, PAPER), as_of=AS_OF, asset_links=links
    )

    table_row = next(line for line in text.splitlines() if line.startswith("| [[CXSE3"))
    assert "[[CXSE3 - Score e Ranking\\|CXSE3]]" in table_row
    reason = next(line for line in text.splitlines() if line.startswith("- [[HGCR11"))
    assert "[[HGCR11 - Score e Ranking|HGCR11]]" in reason and "\\|HGCR11" not in reason


def test_only_existing_asset_notes_are_linked(tmp_path):
    note = tmp_path / "01_Assets" / "FIIs" / "BTLG11" / "BTLG11 - Score e Ranking.md"
    note.parent.mkdir(parents=True)
    note.write_text("x", encoding="utf-8")

    assert find_asset_links(tmp_path, ["BTLG11", "HGRU11"]) == {
        "BTLG11": "BTLG11 - Score e Ranking"
    }
    assert find_asset_links(tmp_path / "missing", ["BTLG11"]) == {}


# --- writing -------------------------------------------------------------------------


def test_the_note_is_written_under_02_portfolio_and_overwritten_idempotently(tmp_path):
    first = write_valuation_report(tmp_path, _result(EQUITY), as_of=AS_OF)
    content = first.read_text(encoding="utf-8")
    second = write_valuation_report(tmp_path, _result(EQUITY), as_of=AS_OF)

    assert first == second == tmp_path / "02_Portfolio" / "Valuation.md"
    assert second.read_text(encoding="utf-8") == content


def test_a_new_run_replaces_the_old_content_never_appends(tmp_path):
    write_valuation_report(tmp_path, _result(EQUITY, FII), as_of=AS_OF)

    path = write_valuation_report(tmp_path, _result(EQUITY), as_of=date(2026, 9, 19))
    text = path.read_text(encoding="utf-8")

    assert (
        "BTLG11" not in text
        and "as_of: 2026-09-19" in text
        and text.count("# Valuation da Carteira") == 1
    )


# --- through value_portfolio and the CLI ---------------------------------------------


def test_outcomes_from_a_real_batch_carry_class_and_segment():
    position = PortfolioAsset(
        "KLBN4",
        "equity",
        sector="Materiais Básicos",
        industry="Madeiras e Papel",
        cnpj="1",
    )

    result = value_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        positions=(position,),
        ano=2025,
        fetch_equity=lambda *a: (
            {"price": 3.88, "financials": {"lpa": 0.24, "vpa": 1.52}},
            object(),
        ),
        fetch_rate=lambda: RATE,
    )

    assert result.outcomes[0].asset_class == "equity"
    assert result.outcomes[0].segment == "Materiais Básicos / Madeiras e Papel"
    assert "Materiais Básicos / Madeiras e Papel" in render_valuation_report(
        result, as_of=AS_OF
    )


def test_the_cli_writes_the_report_only_when_asked(tmp_path, monkeypatch):
    import iip.cli.fetch_template as ft
    import iip.portfolio.batch_value as bv

    monkeypatch.setattr(
        bv,
        "assets_refreshable_now",
        lambda: (
            PortfolioAsset(
                "KLBN4",
                "equity",
                sector="Materiais Básicos",
                industry="Madeiras e Papel",
                cnpj="1",
            ),
        ),
    )
    monkeypatch.setattr(bv, "_default_fetch_rate", lambda: RATE)
    monkeypatch.setattr(
        ft,
        "fetch_equity_template_live",
        lambda *a, **k: (
            {"price": 3.88, "financials": {"lpa": 0.24, "vpa": 1.52}},
            object(),
        ),
    )
    report = tmp_path / "02_Portfolio" / "Valuation.md"

    without = CliRunner().invoke(cli, ["value-portfolio", "--vault", str(tmp_path)])
    assert without.exit_code == 0, without.output
    assert not report.exists()

    with_report = CliRunner().invoke(
        cli, ["value-portfolio", "--vault", str(tmp_path), "--report"]
    )
    assert with_report.exit_code == 0, with_report.output
    assert report.is_file() and "Valuation da Carteira" in report.read_text(
        encoding="utf-8"
    )
    assert "Relatório de valuation" in with_report.output


def test_the_cli_keeps_the_previous_report_when_nothing_was_valued(
    tmp_path, monkeypatch
):
    import iip.cli.fetch_template as ft
    import iip.portfolio.batch_value as bv

    monkeypatch.setattr(
        bv,
        "assets_refreshable_now",
        lambda: (
            PortfolioAsset(
                "KLBN4",
                "equity",
                sector="Materiais Básicos",
                industry="Madeiras e Papel",
                cnpj="1",
            ),
        ),
    )
    monkeypatch.setattr(bv, "_default_fetch_rate", lambda: RATE)
    report = tmp_path / "02_Portfolio" / "Valuation.md"
    report.parent.mkdir(parents=True)
    report.write_text("nota boa de ontem", encoding="utf-8")

    def _quota_exhausted(*args, **kwargs):
        raise RuntimeError("limite diario atingido")

    monkeypatch.setattr(ft, "fetch_equity_template_live", _quota_exhausted)

    result = CliRunner().invoke(
        cli, ["value-portfolio", "--vault", str(tmp_path), "--report"]
    )

    assert result.exit_code == 1  # the failed position still fails the run
    assert report.read_text(encoding="utf-8") == "nota boa de ontem"
    assert "NÃO gravado" in result.output
