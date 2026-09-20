from datetime import date

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.obsidian.decision_report import render_decision_report, write_decision_report
from iip.portfolio import batch_decide
from iip.portfolio.batch_decide import (
    DecisionOutcome,
    DecisionRunResult,
    _Deps,
    decide_portfolio,
    engine_verdict_name,
)
from iip.portfolio.evidence_lookup import find_evidence_ids, previous_decision_verdict
from iip.portfolio.registry import PortfolioAsset
from iip.sources.cvm_cda import CdaError
from iip.sources.tesouro_direto import NtnbRate

RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)
TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _evidence(vault, evidence_id, ticker, day, provider="cvm_fii"):
    path = vault / "04_Evidence" / f"{evidence_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "type: evidence\n"
        f"evidence_id: {evidence_id}\n"
        f"ticker: {ticker}\n"
        f"date: {day}\n"
        "source_type: atlas\n"
        "relevant_facts:\n"
        f"- provider={provider}\n"
        "---\n",
        encoding="utf-8",
    )


def _decision_note(vault, ticker, day, verdict, note_type="decision"):
    path = vault / "03_Decisions" / f"DEC-{ticker}-{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: {note_type}\ndecision_id: DEC-{ticker}-{day}\nticker: {ticker}\n"
        f"date: {day}\nnew_verdict: {verdict}\nconfidence: 0.5\n---\n",
        encoding="utf-8",
    )


# --- evidence and previous decision lookup ----------------------------------------


def test_evidence_is_the_newest_of_each_source_up_to_three(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-A1", "CXSE3", "2025-12-31", "cvm_dfp")
    _evidence(tmp_path, "EV-CXSE3-A2", "CXSE3", "2026-06-30", "cvm_dfp")
    _evidence(tmp_path, "EV-CXSE3-B1", "CXSE3", "2026-08-01", "b3_cotahist")
    _evidence(tmp_path, "EV-CXSE3-C1", "CXSE3", "2026-01-01", "mziq")
    _evidence(tmp_path, "EV-CXSE3-D1", "CXSE3", "2024-01-01", "sparta")

    found = find_evidence_ids(tmp_path, "cxse3")

    assert found == ("EV-CXSE3-B1", "EV-CXSE3-A2", "EV-CXSE3-C1")


def test_evidence_matches_the_ticker_field_not_just_the_filename(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-OTHER", "ITUB4", "2026-01-01")
    _evidence(tmp_path, "EV-XCXSE3-1", "XCXSE3", "2026-01-01")
    (tmp_path / "04_Evidence" / "notes-CXSE3.md").write_text(
        "---\ntype: note\nticker: CXSE3\n---\n", encoding="utf-8"
    )

    assert find_evidence_ids(tmp_path, "CXSE3") == ()


def test_evidence_without_a_vault_folder_is_empty(tmp_path):
    assert find_evidence_ids(tmp_path, "CXSE3") == ()


def test_previous_verdict_is_the_latest_strictly_before_the_date(tmp_path):
    _decision_note(tmp_path, "CXSE3", "2026-09-10", "MANTER")
    _decision_note(tmp_path, "CXSE3", "2026-09-18", "REDUZIR")
    _decision_note(tmp_path, "CXSE3", "2026-09-20", "COMPRAR")
    _decision_note(tmp_path, "ITUB4", "2026-09-19", "VENDER")

    assert previous_decision_verdict(tmp_path, "CXSE3", before=TODAY) == "REDUZIR"


def test_previous_verdict_ignores_unknown_values_and_other_note_types(tmp_path):
    _decision_note(tmp_path, "CXSE3", "2026-09-18", "TALVEZ")
    _decision_note(tmp_path, "CXSE3", "2026-09-19", "COMPRAR", note_type="evidence")

    assert previous_decision_verdict(tmp_path, "CXSE3", before=TODAY) is None


# --- decide_portfolio -------------------------------------------------------------


def _equity(ticker, **kw):
    return PortfolioAsset(
        ticker,
        "equity",
        cnpj="00.000.000/0000-00",
        sector=kw.pop("sector", "Materiais Básicos"),
        industry=kw.pop("industry", "Madeiras e Papel"),
        **kw,
    )


def _fake_equity(templates):
    calls = []

    def fetch(symbol, cnpj, ano, bolsai_api_key, brapi_token):
        calls.append(symbol)
        outcome = templates[symbol]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, object()

    fetch.calls = calls
    return fetch


def _template(price=20.0, **financials):
    return {
        "price": price,
        "market_cap": 1e9,
        "financials": {"lpa": 1.51, "vpa": 4.60, **financials},
    }


def _run(vault, positions, templates, **kw):
    fetch = _fake_equity(templates)
    result = decide_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        vault_path=str(vault),
        positions=tuple(positions),
        today=TODAY,
        deps=_Deps(fetch_equity=fetch, fetch_rate=lambda: RATE),
        **kw,
    )
    return result, fetch


def test_a_position_with_evidence_is_decided_from_analysis_and_valuation(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")

    result, fetch = _run(tmp_path, [_equity("CXSE3")], {"CXSE3": _template()})

    outcome = result.outcomes[0]
    assert outcome.status == "ok"
    assert outcome.verdict in {"COMPRAR", "MANTER", "AGUARDAR", "REDUZIR", "VENDER"}
    assert outcome.evidence_ids == ("EV-CXSE3-1",)
    assert outcome.valuation_score is not None
    assert "Graham" in outcome.valuation_note
    assert outcome.analysis_score is not None
    assert outcome.persisted == ""
    assert fetch.calls == ["CXSE3"]  # UMA busca por posição


def test_nothing_is_written_without_persist(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")

    _run(tmp_path, [_equity("CXSE3")], {"CXSE3": _template()})

    assert not (tmp_path / "03_Decisions").exists()


def test_persist_writes_the_decision_once_per_day(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")

    first, _ = _run(tmp_path, [_equity("CXSE3")], {"CXSE3": _template()}, persist=True)
    second, _ = _run(tmp_path, [_equity("CXSE3")], {"CXSE3": _template()}, persist=True)

    note = tmp_path / "03_Decisions" / "DEC-CXSE3-2026-09-20.md"
    assert first.outcomes[0].persisted == "gravada"
    assert note.exists()
    expected = {"VENDER": "ENCERRAR"}.get(
        first.outcomes[0].verdict, first.outcomes[0].verdict
    )
    assert f"new_verdict: {expected}" in note.read_text(encoding="utf-8")
    assert second.outcomes[0].persisted == "já existia hoje"
    assert second.outcomes[0].status == "ok"


def test_the_previous_decision_is_reported_and_detects_a_change(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")
    _decision_note(tmp_path, "CXSE3", "2026-09-18", "COMPRAR")

    result, _ = _run(tmp_path, [_equity("CXSE3")], {"CXSE3": _template()})

    outcome = result.outcomes[0]
    assert outcome.previous_verdict == "COMPRAR"
    changed = outcome.verdict != "COMPRAR"
    assert (outcome in result.changed) is changed


def test_a_position_without_evidence_is_skipped_without_fetching(tmp_path):
    result, fetch = _run(tmp_path, [_equity("CXSE3")], {"CXSE3": _template()})

    outcome = result.outcomes[0]
    assert outcome.status == "pulado"
    assert "sem evidência real" in outcome.detail
    assert fetch.calls == []


def test_a_position_without_sector_is_skipped(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")
    position = PortfolioAsset("CXSE3", "equity", cnpj="00.000.000/0000-00")

    result, fetch = _run(tmp_path, [position], {"CXSE3": _template()})

    assert result.outcomes[0].status == "pulado"
    assert "sector/industry" in result.outcomes[0].detail
    assert fetch.calls == []


def test_one_failing_fetch_does_not_stop_the_others(tmp_path):
    _evidence(tmp_path, "EV-A3-1", "A3", "2026-08-01")
    _evidence(tmp_path, "EV-B3-1", "B3", "2026-08-01")

    result, _ = _run(
        tmp_path,
        [_equity("A3"), _equity("B3")],
        {"A3": RuntimeError("bolsai 429"), "B3": _template()},
    )

    assert [o.status for o in result.outcomes] == ["erro", "ok"]
    assert "bolsai 429" in result.outcomes[0].detail
    assert len(result.failed) == 1 and len(result.succeeded) == 1


def test_without_a_valuation_the_score_is_neutral_and_says_so(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")
    empty = {"price": 20.0, "market_cap": 1e9, "financials": {}}

    result, _ = _run(tmp_path, [_equity("CXSE3")], {"CXSE3": empty})

    outcome = result.outcomes[0]
    assert outcome.status == "ok"
    assert outcome.valuation_score is None
    assert any("valuation" in w.lower() for w in outcome.warnings)


def test_incomplete_market_data_is_an_error_not_a_guess(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")
    fetch = _fake_equity({"CXSE3": {"financials": {}}})

    result = decide_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        vault_path=str(tmp_path),
        positions=(_equity("CXSE3"),),
        today=TODAY,
        deps=_Deps(fetch_equity=fetch, fetch_rate=lambda: RATE),
    )

    assert result.outcomes[0].status == "erro"


def test_the_ntnb_rate_failure_only_degrades_bazin(tmp_path):
    _evidence(tmp_path, "EV-CXSE3-1", "CXSE3", "2026-08-01")

    def broken():
        raise RuntimeError("tesouro fora do ar")

    result = decide_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        vault_path=str(tmp_path),
        positions=(_equity("CXSE3"),),
        today=TODAY,
        deps=_Deps(
            fetch_equity=_fake_equity({"CXSE3": _template()}), fetch_rate=broken
        ),
    )

    assert "tesouro fora do ar" in result.ntnb_note
    assert result.outcomes[0].status == "ok"


def test_an_fmp_fgts_cda_failure_is_isolated(tmp_path):
    _evidence(tmp_path, "EV-AXIA3-1", "AXIA3", "2026-08-01")
    fmp = PortfolioAsset(
        "AXIA3",
        "fixed_income",
        subtype="Daycoval FMP FGTS / subjacente AXIA3",
        cnpj="45.121.022/0001-48",
        sector="Utilities",
        industry="Electric Utilities",
    )

    def fetch_fixed_income(symbol, cnpj, ano, mes, brapi_token=None):
        return {"financials": {"nav_per_share": 1.8956}}, object()

    def broken_cda(cnpj):
        raise CdaError("sem CDA")

    result = decide_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        vault_path=str(tmp_path),
        positions=(fmp, _equity("CXSE3")),
        today=TODAY,
        deps=_Deps(
            fetch_fixed_income=fetch_fixed_income,
            fetch_equity=_fake_equity({"CXSE3": _template()}),
            fetch_rate=lambda: RATE,
            fetch_cda=broken_cda,
        ),
    )

    assert result.outcomes[0].status == "erro"
    assert "sem CDA" in result.outcomes[0].detail
    assert result.outcomes[1].status == "pulado"  # o CXSE3 não tem evidência


def test_the_vault_and_engine_vocabularies_do_not_fake_a_change():
    assert engine_verdict_name("ENCERRAR") == "VENDER"
    assert engine_verdict_name("MANTER") == "MANTER"
    assert engine_verdict_name(None) is None


# --- report ---------------------------------------------------------------------


def _ok(ticker, verdict, score, previous=None):
    return DecisionOutcome(
        ticker,
        "ok",
        f"{verdict}",
        asset_class="equity",
        verdict=verdict,
        score=score,
        confidence=0.5,
        previous_verdict=previous,
        analysis_score=55.0,
        analysis_recommendation="Hold",
        valuation_score=6.0,
        valuation_note="Graham: 12.50 vs preço 10.00 (-20%) → nota 6.00/10",
        thesis_exit_state="REVIEW",
        evidence_ids=("EV-1",),
    )


def _result():
    return DecisionRunResult(
        outcomes=(
            _ok("LOW3", "REDUZIR", 3.9, previous="MANTER"),
            _ok("TOP3", "COMPRAR", 7.1),
            _ok("MID3", "MANTER", 6.0, previous="MANTER"),
            DecisionOutcome("SKP3", "pulado", "sem evidência real no vault"),
            DecisionOutcome("ERR3", "erro", "bolsai 429"),
        ),
        ntnb_note="NTN-B longa: IPCA + 7.30%",
        decision_date=TODAY,
    )


def test_report_groups_by_verdict_and_lists_changes_and_skips():
    text = render_decision_report(_result(), links={"TOP3": "TOP3 - Score e Ranking"})

    rows = [line for line in text.splitlines() if line.startswith("| ")][1:]
    assert [r.split(" | **")[0].removeprefix("| ") for r in rows] == [
        "[[TOP3 - Score e Ranking\\|TOP3]]",
        "MID3",
        "LOW3",
    ]
    assert "MANTER →" in text
    assert "## Mudanças desde a decisão anterior" in text
    assert "- LOW3: MANTER → **REDUZIR**" in text
    assert "SKP3 (pulado)" in text and "ERR3 (erro)" in text
    assert "Neutro" in text
    assert "1 COMPRAR, 1 MANTER, 1 REDUZIR" in text
    assert "3 decididas, 1 puladas, 1 com erro" in text


def test_report_is_written_to_the_portfolio_folder(tmp_path):
    path = write_decision_report(tmp_path, _result())

    assert path == tmp_path / "02_Portfolio" / "Decisoes.md"
    assert path.read_text(encoding="utf-8").startswith("---\ntype: portfolio_decisions")


# --- CLI ------------------------------------------------------------------------


def _patch_run(monkeypatch, result, captured=None):
    def fake(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return result

    monkeypatch.setattr(batch_decide, "decide_portfolio", fake)


def test_command_prints_the_table_and_the_changes(monkeypatch, tmp_path):
    _patch_run(monkeypatch, _result())

    out = CliRunner().invoke(cli, ["decide-portfolio", "--vault", str(tmp_path)])

    assert out.exit_code == 1  # ERR3 falhou
    assert "TOP3" in out.output and "COMPRAR" in out.output
    assert "LOW3: MANTER -> REDUZIR" in out.output
    assert "3 decididas, 1 erro, 1 pulado" in out.output
    assert not (tmp_path / "02_Portfolio").exists()


def test_command_passes_persist_and_writes_the_report(monkeypatch, tmp_path):
    ok_only = DecisionRunResult((_ok("TOP3", "COMPRAR", 7.1),), "nota", TODAY)
    captured = {}
    _patch_run(monkeypatch, ok_only, captured)

    out = CliRunner().invoke(
        cli,
        ["decide-portfolio", "--vault", str(tmp_path), "--persist", "--report"],
    )

    assert out.exit_code == 0, out.output
    assert captured["persist"] is True
    assert (tmp_path / "02_Portfolio" / "Decisoes.md").exists()


def test_command_keeps_the_previous_report_when_nothing_was_decided(
    monkeypatch, tmp_path
):
    nothing = DecisionRunResult(
        (DecisionOutcome("SKP3", "pulado", "sem evidência real"),), "nota", TODAY
    )
    _patch_run(monkeypatch, nothing)

    out = CliRunner().invoke(
        cli, ["decide-portfolio", "--vault", str(tmp_path), "--report"]
    )

    assert out.exit_code == 0
    assert "NÃO gravado" in out.output
    assert not (tmp_path / "02_Portfolio" / "Decisoes.md").exists()


def test_command_filters_by_ticker(monkeypatch, tmp_path):
    captured = {}
    _patch_run(monkeypatch, DecisionRunResult((), "nota", TODAY), captured)

    CliRunner().invoke(
        cli,
        ["decide-portfolio", "--vault", str(tmp_path), "--ticker", "lftb11"],
    )

    assert [p.ticker for p in captured["positions"]] == ["LFTB11"]


def test_command_rejects_a_ticker_outside_the_portfolio(tmp_path):
    out = CliRunner().invoke(
        cli, ["decide-portfolio", "--vault", str(tmp_path), "--ticker", "ZZZZ11"]
    )

    assert out.exit_code != 0
    assert "ZZZZ11" in out.output
