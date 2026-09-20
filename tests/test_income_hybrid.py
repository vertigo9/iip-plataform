from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.income_report import render_income_report
from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
)
from iip.portfolio.income import build_income
from iip.portfolio.income_cross_check import CrossCheck, save_validation
from iip.sources.fii_distribution_reports import reference_hint
from iip.universal.portfolio_state import PortfolioState, PositionState

TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


def _series(ticker, values):
    obs = tuple(
        _obs(f"2026-{m:02d}", v, nav=100.0 + i * 0.01)
        for i, (m, v) in enumerate(enumerate(values, start=3))
    )
    return HistoricalSeries(ticker, "0", "cvm", obs, source_documents=())


def _store(tmp_path, **series):
    store = HistoricalSeriesStore(tmp_path)
    for ticker, values in series.items():
        store.save(_series(ticker, values))
    return store


def _state(*positions):
    return PortfolioState(
        "2026-09-12",
        tuple(PositionState(t, q, q * 10, 0.0, "fund") for t, q in positions),
        sum(q * 10 for _, q in positions),
    )


def _check(ticker, status, declared, reference=None, url="http://relatorio"):
    return CrossCheck(
        ticker,
        status,
        "2026-09-20",
        declared=declared,
        source_url=url,
        evidence="frase",
        reference=reference,
    )


REGULAR = [0.95] * 6
IRREGULAR = [0.30, 0.36, 0.86, 1.47, 0.20, 1.90]


def _line(report, ticker):
    return next(ln for ln in report.lines if ln.ticker == ticker)


# --- the rules -----------------------------------------------------------------


def test_without_a_manager_check_the_effective_estimate_is_the_cvm_one(tmp_path):
    report = build_income(
        _state(("A11", 100)), _store(tmp_path, A11=REGULAR), today=TODAY
    )

    line = _line(report, "A11")
    assert line.estimate_source == "cvm" and line.override_reason == ""
    assert line.effective_estimate == line.cvm_estimate == line.per_unit
    assert not report.is_hybrid and report.adjustments == ()
    assert report.monthly_income == report.cvm_monthly_income


def test_a_fund_only_the_manager_can_project_enters_as_the_managers_estimate(tmp_path):
    checks = {"X11": _check("X11", "so_gestor", 0.92, "na frase: 18/08/2026, 25/08/26")}

    report = build_income(
        _state(("X11", 50)), _store(tmp_path, X11=IRREGULAR), today=TODAY, checks=checks
    )

    line = _line(report, "X11")
    assert (
        line.status == "sem projeção" and line.cvm_estimate is None
    )  # a CVM segue sem número
    assert line.estimate_source == "manager"
    assert line.effective_estimate == 0.92 and line.effective_income == pytest.approx(
        46.0
    )
    assert line.manager_reported_distribution == 0.92
    assert line.manager_reference == "na frase: 18/08/2026, 25/08/26"
    assert (
        line.validation_status == "so_gestor"
        and "identificada como tal" in line.override_reason
    )
    assert line in report.effective_lines and line not in report.excluded
    assert report.is_hybrid and report.monthly_income == pytest.approx(46.0)
    assert report.cvm_monthly_income == 0.0


def test_a_divergence_where_the_manager_says_less_caps_the_total_and_keeps_the_cvm_value(
    tmp_path,
):
    checks = {"B11": _check("B11", "diverge", 0.81)}

    report = build_income(
        _state(("B11", 100)), _store(tmp_path, B11=REGULAR), today=TODAY, checks=checks
    )

    line = _line(report, "B11")
    assert line.estimate_source == "cvm_capped_by_manager"
    assert line.cvm_estimate == pytest.approx(0.95, abs=0.001)  # NÃO sobrescrito
    assert line.monthly_income == pytest.approx(95.0, abs=0.1)  # a renda da CVM segue
    assert line.effective_estimate == 0.81
    assert line.effective_income == pytest.approx(81.0)
    assert "limite conservador provisório" in line.override_reason
    assert report.monthly_income == pytest.approx(81.0)
    assert report.cvm_monthly_income == pytest.approx(95.0, abs=0.1)


def test_a_divergence_where_the_manager_says_more_does_not_inflate_the_total(tmp_path):
    checks = {"B11": _check("B11", "diverge", 1.20)}

    report = build_income(
        _state(("B11", 100)), _store(tmp_path, B11=REGULAR), today=TODAY, checks=checks
    )

    line = _line(report, "B11")
    assert line.estimate_source == "cvm"
    assert line.effective_estimate == line.cvm_estimate
    assert line.manager_reported_distribution == 1.20  # registrado, não usado
    assert not report.is_hybrid


@pytest.mark.parametrize(
    "status", ["confere", "mudanca_recente", "sem_gestor", "leitura_falhou"]
)
def test_the_other_statuses_keep_the_cvm_estimate(tmp_path, status):
    declared = None if status in ("sem_gestor", "leitura_falhou") else 1.00
    checks = {"A11": _check("A11", status, declared)}

    report = build_income(
        _state(("A11", 100)), _store(tmp_path, A11=REGULAR), today=TODAY, checks=checks
    )

    line = _line(report, "A11")
    assert (
        line.estimate_source == "cvm" and line.effective_estimate == line.cvm_estimate
    )
    assert line.validation_status == status


def test_the_manager_never_fills_in_a_fund_that_has_no_check_or_no_value(tmp_path):
    checks = {"X11": _check("X11", "sem_gestor", None)}

    report = build_income(
        _state(("X11", 50)), _store(tmp_path, X11=IRREGULAR), today=TODAY, checks=checks
    )

    line = _line(report, "X11")
    assert line.effective_estimate is None and line in report.excluded


def test_the_total_is_the_sum_of_the_effective_estimates(tmp_path):
    checks = {
        "X11": _check("X11", "so_gestor", 0.92),
        "B11": _check("B11", "diverge", 0.81),
    }
    store = _store(tmp_path, X11=IRREGULAR, B11=REGULAR, A11=REGULAR)

    report = build_income(
        _state(("X11", 50), ("B11", 100), ("A11", 100)),
        store,
        today=TODAY,
        checks=checks,
    )

    assert report.monthly_income == pytest.approx(46.0 + 81.0 + 95.0, abs=0.1)
    assert report.cvm_monthly_income == pytest.approx(95.0 + 95.0, abs=0.2)
    assert {ln.ticker for ln in report.adjustments} == {"X11", "B11"}
    assert report.covered_share == pytest.approx(1.0)


# --- the note ------------------------------------------------------------------


def _hybrid_report(tmp_path):
    checks = {
        "X11": _check(
            "X11", "so_gestor", 0.92, "na frase: 18/08/2026, 25/08/26", "http://xp"
        ),
        "B11": _check("B11", "diverge", 0.81, "relatório de 2026-08", "http://btg"),
    }
    store = _store(tmp_path, X11=IRREGULAR, B11=REGULAR, A11=REGULAR)
    return build_income(
        _state(("X11", 50), ("B11", 100), ("A11", 100)),
        store,
        today=TODAY,
        checks=checks,
    )


def test_the_note_says_the_total_is_hybrid_and_breaks_it_down(tmp_path):
    text = render_income_report(_hybrid_report(tmp_path))

    assert "estimativa HÍBRIDA" in text
    assert "(CVM pura)" in text and "(X11, estimativa do gestor)" in text
    assert "(B11, limite do gestor)" in text
    assert "nada do gestor substitui a CVM em silêncio" in text


def test_the_note_shows_cvm_manager_and_effective_side_by_side_with_the_source(
    tmp_path,
):
    text = render_income_report(_hybrid_report(tmp_path))

    rows = {
        ln.split(" | ")[0].removeprefix("| "): ln
        for ln in text.splitlines()
        if ln.startswith("| ")
    }
    assert "sem projeção" in rows["X11"] and "**gestor** ⚠" in rows["X11"]
    assert "**CVM limitada pelo gestor** ⚠" in rows["B11"]
    assert rows["A11"].count("**CVM**") == 1 and "⚠" not in rows["A11"]


def test_the_note_registers_the_managers_report_and_reference_dates(tmp_path):
    text = render_income_report(_hybrid_report(tmp_path))

    assert "na frase: 18/08/2026, 25/08/26" in text
    assert "relatório de 2026-08" in text
    assert "http://xp" in text and "http://btg" in text
    assert "Estimativa da CVM:** sem projeção (série irregular)" in text
    assert "diferença para a CVM pura: −R$" in text  # o corte do BTLG-like


def test_a_report_without_a_date_says_it_was_not_identified(tmp_path):
    checks = {"X11": _check("X11", "so_gestor", 0.92, None)}
    report = build_income(
        _state(("X11", 50)), _store(tmp_path, X11=IRREGULAR), today=TODAY, checks=checks
    )

    assert "data do relatório não identificada no texto" in render_income_report(report)


def test_a_plain_cvm_note_is_not_labelled_hybrid(tmp_path):
    report = build_income(
        _state(("A11", 100)), _store(tmp_path, A11=REGULAR), today=TODAY
    )

    text = render_income_report(report)

    assert "HÍBRIDA" not in text and "## Ajustes a partir do gestor" not in text


# --- the report date hint ------------------------------------------------------


@pytest.mark.parametrize(
    ("evidence", "url", "expected"),
    [
        (
            "No dia 18/08/2026 o Fundo divulgou a distribuição de R$ 0,92 por cota, com pagamento em 25/08/26",
            "http://x/xp_malls_fii_ago.26_vf.pdf",
            "na frase: 18/08/2026, 25/08/26; relatório de 2026-08",
        ),
        ("frase", "http://x/REL31082026V01.pdf", "relatório de 2026-08"),
        ("frase", "http://x/2026_08_HGBS_Relatorio.pdf", "relatório de 2026-08"),
        ("frase", "http://x/KNRI_Carta-do-Gestor_08-2026.pdf", "relatório de 2026-08"),
        (
            "frase",
            "http://x/TRXF11-Investor-Report-July-2026.pdf",
            "relatório de 2026-07",
        ),
        ("frase", "http://x/qFuvgdWow==", None),
    ],
)
def test_the_reference_is_read_from_the_phrase_and_the_file_name(
    evidence, url, expected
):
    assert reference_hint(evidence, url) == expected


# --- CLI -----------------------------------------------------------------------

_SNAPSHOT = """\
| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| XPML11 | XPML11 | fii | 50,0000 | 100,00 | 100,00 | 5.000,00 | 100,00% | | active |
"""


def _vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / "02_Portfolio").mkdir(parents=True)
    (vault / "02_Portfolio" / "Current.md").write_text(_SNAPSHOT, encoding="utf-8")
    HistoricalSeriesStore(vault).save(_series("XPML11", IRREGULAR))
    save_validation(
        vault, (_check("XPML11", "so_gestor", 0.92, "relatório de 2026-08"),)
    )
    return vault


def test_command_uses_the_managers_estimate_and_says_the_total_is_hybrid(tmp_path):
    out = CliRunner().invoke(
        cli, ["portfolio-income", "--vault", str(_vault(tmp_path))]
    )

    assert out.exit_code == 0, out.output
    assert "estimativa HÍBRIDA" in out.output
    assert "R$ 46.00" in out.output
    assert "Só a CVM: R$ 0.00" in out.output
    assert "XPML11" in out.output and "gestor *" in out.output


def test_the_cvm_only_option_ignores_the_manager(tmp_path):
    out = CliRunner().invoke(
        cli, ["portfolio-income", "--vault", str(_vault(tmp_path)), "--somente-cvm"]
    )

    assert out.exit_code == 0, out.output
    assert "HÍBRIDA" not in out.output
    assert "R$ 0.00" in out.output
