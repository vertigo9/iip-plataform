from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.income_report import render_income_report
from iip.obsidian.income_validation_report import (
    render_validation_report,
    write_validation_report,
)
from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
)
from iip.portfolio.income_cross_check import (
    CrossCheck,
    cross_check_fund,
    load_validation,
    run_cross_checks,
    save_validation,
)
from iip.sources import fii_distribution_harvester
from iip.sources.fii_distribution_reports import (
    DeclaredDistribution,
    parse_alzr,
    parse_btg,
    parse_hedge,
    parse_hsi,
    parse_knri,
    parse_rbva,
    parse_trx,
    parse_xp,
    read_declared,
    supports,
)

TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- the readers, on the real sentences of the 20/09/2026 reports ----------------


def test_xp_reads_the_announced_distribution_with_a_footnote_mark():
    text = (
        "Distribuição de Rendimentos\n"
        "No dia 18/08/2026 o Fundo divulgou a distribuição de R$ 0,92¹ por cota, com "
        "pagamento em 25/08/26 para os\n"
    )

    assert parse_xp(text)[0] == 0.92


def test_trx_reads_an_english_report_with_a_decimal_point():
    text = "Monthly Distribution\nTRXF11 announced a monthly distribution of BRL 0.93 per share, equivalent to\n"

    assert parse_trx(text)[0] == 0.93


def test_knri_reads_the_line_before_the_monthly_distribution_date():
    text = "PLANILHA DE FUNDAMENTOS\nR$ 1,10/cota\nDISTRIBUIÇÃO MENSAL EM 15/09/2026\nDiversificação\n"

    assert parse_knri(text)[0] == 1.10


def test_knri_ignores_the_distribution_of_contracts_by_sector():
    assert parse_knri("R$ 5,00/cota\nDISTRIBUIÇÃO DOS CONTRATOS POR SETOR\n") is None


def test_btg_reads_the_line_under_the_monthly_income_label():
    text = "LTV\n²\n1,9%\nRENDIMENTO MENSAL\nR$ 0,81 por cota\nCOTA DE MERCADO\n"

    assert parse_btg(text)[0] == 0.81


def test_hedge_reads_the_announced_distribution_per_quota():
    text = "Em agosto, o resultado do Fundo foi de R$ 0,233 / cota. O Fundo anunciou a distribuição de R$ 0,170 / cota como"

    assert parse_hedge(text)[0] == 0.170


def test_rbva_reads_the_distribution_not_the_result():
    text = "No mês, o resultado do Fundo foi de R$ 0,10/cota e a distribuição, de R$0,09/cota, seguindo o guidance"

    assert parse_rbva(text)[0] == 0.09


def test_alzr_reads_the_distributed_result_not_the_cash_result():
    text = (
        "O Resultado Caixa gerado no mês foi de R$ 0,0887/cota. Será\n"
        "mantido, para o mês, um Resultado Distribuído de R$ 0,0840/cota, valor"
    )

    assert parse_alzr(text)[0] == 0.0840


def test_hsi_reads_the_first_column_of_the_rendimento_per_quota_row():
    text = "Resultado Realizado/Cota -0,70 2,09 6,60\nRendimento/Cota4 0,75 1,50 5,81\n"

    assert parse_hsi(text)[0] == 0.75


def test_a_reader_returns_none_when_the_layout_does_not_match():
    assert parse_xp("um relatório com outro texto") is None
    assert read_declared("XPML11", "outro texto", "http://x") is None


def test_a_fund_without_a_reader_is_not_supported():
    assert supports("XPML11") and not supports("HGRU11")
    assert read_declared("HGRU11", "qualquer", "http://x") is None


def test_read_declared_carries_the_source_and_the_matched_phrase():
    found = read_declared(
        "rbva11", "a distribuição, de R$0,09/cota, seguindo", "http://relatorio"
    )

    assert found == DeclaredDistribution(
        "RBVA11", 0.09, "http://relatorio", "distribuição, de R$0,09/cota"
    )


# --- the comparison ------------------------------------------------------------


def _obs(period, per_unit, nav=100.0):
    return HistoricalObservation(
        period=f"{period}-01",
        patrimonio_liquido=1e9,
        valor_patrimonial_cotas=nav,
        dividend_yield_mes=per_unit / nav,
        rentabilidade_patrimonial_mes=None,
        valor_ativo=None,
        total_numero_cotistas=None,
        document_id="d",
        document_hash="h",
        discovered_year=2026,
    )


def _series(ticker, values, start=(2026, 3)):
    year, month = start
    out = []
    for value in values:
        out.append(_obs(f"{year:04d}-{month:02d}", value, nav=100.0 + len(out) * 0.01))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return HistoricalSeries(ticker, "0", "cvm", tuple(out), source_documents=())


def _declared(value, competencia=None):
    return DeclaredDistribution("X11", value, "http://r", "frase", competencia)


def test_a_projection_within_five_percent_of_the_manager_confirms():
    check = cross_check_fund(
        "X11", _series("X11", [0.95] * 6), _declared(0.93), today=TODAY
    )

    assert check.status == "confere"
    assert check.diff_projection == pytest.approx((0.95 - 0.93) / 0.93, abs=0.002)
    assert check.checked_at == "2026-09-20"


def test_a_projection_far_from_the_manager_and_from_the_last_month_diverges():
    check = cross_check_fund(
        "X11", _series("X11", [0.95] * 6), _declared(0.70), today=TODAY
    )

    assert check.status == "diverge"


def test_a_recent_change_is_told_apart_from_a_divergence():
    # o fundo passou de 0,90 para 1,00: a mediana dos 6 meses fica em 0,90
    series = _series("X11", [0.90, 0.90, 0.90, 0.90, 1.00, 1.00])

    check = cross_check_fund("X11", series, _declared(1.00), today=TODAY)

    assert check.status == "mudanca_recente"
    assert "mudou há pouco" in check.note


def test_a_stated_month_is_compared_with_that_same_month():
    # o gestor fala de mar/2026 (0,90); o último mês da CVM (ago) é 1,00
    series = _series("X11", [0.90, 0.90, 0.90, 0.90, 0.90, 1.00])

    check = cross_check_fund(
        "X11", series, _declared(0.90, competencia="2026-03"), today=TODAY
    )

    assert check.cvm_last_period == "2026-03"
    assert check.diff_last == pytest.approx(0.0, abs=0.001)


def test_when_the_cvm_cannot_project_only_the_manager_has_a_number():
    irregular = _series("X11", [0.30, 0.36, 0.86, 1.47, 0.20, 1.90])

    check = cross_check_fund("X11", irregular, _declared(0.92), today=TODAY)

    assert check.status == "so_gestor"
    assert check.declared == 0.92 and check.cvm_projection is None
    assert "decisão do usuário" in check.note


def test_no_reader_is_no_source_not_a_guess():
    check = cross_check_fund("X11", _series("X11", [0.95] * 6), None, today=TODAY)

    assert check.status == "sem_gestor" and check.declared is None
    assert check.cvm_projection == pytest.approx(0.95, abs=0.001)


def test_a_failed_reading_is_reported_with_the_error():
    check = cross_check_fund("X11", None, None, today=TODAY, error="OSError: sem rede")

    assert check.status == "leitura_falhou" and "sem rede" in check.note


def test_a_missing_series_still_records_what_the_manager_says():
    check = cross_check_fund("X11", None, _declared(0.92), today=TODAY)

    assert check.status == "so_gestor" and check.cvm_last is None


# --- the run -------------------------------------------------------------------


def test_one_failing_fetch_does_not_stop_the_others(tmp_path):
    store = HistoricalSeriesStore(tmp_path)
    store.save(_series("A11", [0.95] * 6))
    store.save(_series("B11", [0.95] * 6))

    def fetch(ticker):
        if ticker == "A11":
            raise OSError("sem rede")
        return DeclaredDistribution(ticker, 0.95, "http://r", "frase")

    checks = run_cross_checks(("A11", "B11"), store, fetch, today=TODAY)

    assert [c.status for c in checks] == ["leitura_falhou", "confere"]
    assert "OSError" in checks[0].note


def test_the_validation_round_trips_through_its_file(tmp_path):
    checks = (
        cross_check_fund(
            "X11", _series("X11", [0.95] * 6), _declared(0.93), today=TODAY
        ),
        cross_check_fund("Y11", None, None, today=TODAY),
    )

    save_validation(tmp_path, checks)
    loaded = load_validation(tmp_path)

    assert loaded["X11"] == checks[0] and loaded["Y11"].status == "sem_gestor"


def test_a_missing_or_old_format_validation_file_is_ignored(tmp_path):
    assert load_validation(tmp_path) == {}
    path = tmp_path / "02_Portfolio" / "Historical" / "_validacao.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"X11": {"campo_que_nao_existe": 1}}', encoding="utf-8")
    assert load_validation(tmp_path) == {}


# --- notes ---------------------------------------------------------------------


def _checks():
    return (
        CrossCheck(
            "OK11",
            "confere",
            "2026-09-20",
            0.93,
            "http://a",
            "frase a",
            0.95,
            0.95,
            "2026-08",
            0.02,
            0.02,
        ),
        CrossCheck(
            "BAD11",
            "diverge",
            "2026-09-20",
            0.70,
            "http://b",
            "frase b",
            0.95,
            0.95,
            "2026-08",
            0.36,
            0.36,
        ),
        CrossCheck(
            "ONLY11",
            "so_gestor",
            "2026-09-20",
            0.92,
            "http://c",
            "frase c",
            None,
            0.86,
            "2026-08",
            None,
            -0.07,
            note="decisão do usuário",
        ),
        CrossCheck("NONE11", "sem_gestor", "2026-09-20", note="sem leitor"),
    )


def test_the_validation_note_states_coverage_and_puts_problems_first():
    text = render_validation_report(_checks())

    assert "3 de 4 FIIs têm um número do gestor" in text
    rows = [
        ln for ln in text.splitlines() if ln.startswith("| ") and "Ticker" not in ln
    ]
    assert [r.split(" | ")[0].removeprefix("| ") for r in rows] == [
        "BAD11",
        "ONLY11",
        "OK11",
        "NONE11",
    ]
    assert "decisão do usuário" in text
    assert '"frase a"' in text
    assert "Sem leitor: HGRU11" in text


def test_the_validation_note_is_written_to_the_portfolio_folder(tmp_path):
    path = write_validation_report(tmp_path, _checks())

    assert path == tmp_path / "02_Portfolio" / "Validacao_Renda.md"


def test_the_income_note_shows_what_the_manager_said_per_fund(tmp_path):
    from iip.portfolio.income import build_income
    from iip.universal.portfolio_state import PortfolioState, PositionState

    store = HistoricalSeriesStore(tmp_path)
    store.save(_series("OK11", [0.95] * 6))
    store.save(_series("NEW11", [0.50] * 6))
    state = PortfolioState(
        "2026-09-12",
        (
            PositionState("OK11", 10.0, 500.0, 0.5, "fund"),
            PositionState("NEW11", 10.0, 500.0, 0.5, "fund"),
        ),
        1000.0,
    )
    report = build_income(state, store, today=TODAY, checks={"OK11": _checks()[0]})

    text = render_income_report(report)

    assert "| Gestor (por cota) |" in text
    ok_row = next(ln for ln in text.splitlines() if ln.startswith("| OK11"))
    new_row = next(ln for ln in text.splitlines() if ln.startswith("| NEW11"))
    assert "R$ 0,9300" in ok_row and "confere" in ok_row
    assert "| — |" in new_row


# --- CLI -----------------------------------------------------------------------


class _FakeHarvester:
    def fetch_distribution(self, ticker):
        return DeclaredDistribution(ticker, 0.95, "http://r", "frase")

    def fetch_patria_sheet(self, ticker):
        return None


def _vault(tmp_path, tickers=("HGRU11", "KNRI11")):
    vault = tmp_path / "vault"
    store = HistoricalSeriesStore(vault)
    for ticker in tickers:
        store.save(_series(ticker, [0.95] * 6))
    return vault


def test_command_records_the_checks_and_writes_the_note(monkeypatch, tmp_path):
    monkeypatch.setattr(
        fii_distribution_harvester, "FiiDistributionHTTPHarvester", _FakeHarvester
    )
    vault = _vault(tmp_path)

    out = CliRunner().invoke(
        cli, ["validate-income", "--vault", str(vault), "--report"]
    )

    assert out.exit_code == 0, out.output
    checks = load_validation(vault)
    assert checks["HGRU11"].status == "confere"
    assert (vault / "02_Portfolio" / "Validacao_Renda.md").exists()
    assert "conferem" in out.output


def test_min_age_days_skips_a_recent_validation(monkeypatch, tmp_path):
    calls = []

    class Spy(_FakeHarvester):
        def fetch_distribution(self, ticker):
            calls.append(ticker)
            return super().fetch_distribution(ticker)

    monkeypatch.setattr(fii_distribution_harvester, "FiiDistributionHTTPHarvester", Spy)
    vault = _vault(tmp_path)
    today = date.today()  # noqa: DTZ011
    save_validation(vault, (CrossCheck("HGRU11", "confere", today.isoformat(), 0.95),))

    out = CliRunner().invoke(
        cli, ["validate-income", "--vault", str(vault), "--min-age-days", "6"]
    )

    assert out.exit_code == 0, out.output
    assert "Validação em dia" in out.output
    assert calls == []
