import ast
import datetime as dt
import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from iip.cli.main import cli
from iip.config import get_settings
from iip.decision.catalog_valuation import catalog_valuation_for_decision
from iip.macro.scenarios import Scenario, ScenarioSet
from iip.macro.sensitivity import analyse_asset
from iip.obsidian.valuation_exceptions_report import render_exceptions_report
from iip.obsidian.valuation_report import render_valuation_report
from iip.portfolio.batch_value import ValuationRunResult, value_portfolio
from iip.portfolio.registry import PortfolioAsset
from iip.portfolio.valuation_inputs import PositionInputs
from iip.portfolio_data.valuation import ValuationMethod
from iip.portfolio_data.valuation_exceptions import (
    DEFAULT_EXCEPTIONS,
    NO_EXCEPTIONS,
    MethodException,
    ValuationExceptions,
    exceptions_for,
    load_exceptions,
    save_exceptions,
    validate,
)
from iip.portfolio_data.valuation_methods import (
    applicability,
    evaluate_valuations,
    ordered_methods,
)
from iip.sources.tesouro_direto import NtnbRate

TODAY = dt.date(2026, 9, 20)
RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)
# a classificação de CSUD3 depois do PR cadastral (Financeiro / Serviços Financeiros Diversos)
FIN = ("Financeiro", "Serviços Financeiros Diversos")
INPUTS = {
    "lpa": 2.45,
    "vpa": 11.75,
    "dividend_per_share": 0.87,
    "ntnb_real_yield": 0.0731,
}


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    from iip.config import IIPSettings

    monkeypatch.setitem(IIPSettings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _item(**changes):
    base = {
        "id": "X-graham-excluir",
        "ticker": "CSUD3",
        "method": "Graham",
        "action": "exclude",
        "reason": "premissa metodológica do teste",
        "decided_on": "2026-09-20",
        "decided_by": "usuário",
        "review_by": "2027-03-20",
    }
    base.update(changes)
    return MethodException(**base)


def _exc(*items):
    return ValuationExceptions("teste.1", "teste", tuple(items))


def _methods(ticker, sector, industry, exceptions):
    attempts = evaluate_valuations(
        ticker=ticker,
        asset_class="equity",
        sector=sector,
        industry=industry,
        price=13.81,
        inputs=INPUTS,
        exceptions=exceptions,
    )
    return {a.method.value: a for a in attempts}


# --- the contract: file, hash, strict loading ---------------------------------------------


def test_the_declared_default_is_valid_and_has_the_mandatory_review_date():
    validate(DEFAULT_EXCEPTIONS)

    [item] = DEFAULT_EXCEPTIONS.items
    assert (item.ticker, item.method, item.action) == ("CSUD3", "Graham", "exclude")
    assert item.review_by and item.decided_by == "usuário"
    assert "não uma conclusão sobre o valor justo" in item.reason


def test_the_exceptions_survive_a_save_and_load_with_the_same_hash(tmp_path):
    save_exceptions(tmp_path, DEFAULT_EXCEPTIONS)

    loaded = load_exceptions(tmp_path)

    assert loaded == DEFAULT_EXCEPTIONS
    assert loaded.content_hash == DEFAULT_EXCEPTIONS.content_hash


def test_a_missing_file_means_no_exceptions_and_a_missing_vault_too(tmp_path):
    assert load_exceptions(tmp_path) is None
    assert exceptions_for(tmp_path) is NO_EXCEPTIONS
    assert exceptions_for(None) is NO_EXCEPTIONS


def test_the_hash_follows_the_content_and_ignores_the_origin():
    changed = replace(
        DEFAULT_EXCEPTIONS,
        items=(replace(DEFAULT_EXCEPTIONS.items[0], reason="outro"),),
    )

    assert changed.content_hash != DEFAULT_EXCEPTIONS.content_hash
    assert (
        replace(DEFAULT_EXCEPTIONS, origin="x").content_hash
        == DEFAULT_EXCEPTIONS.content_hash
    )


def _write(tmp_path, mutate):
    path = save_exceptions(tmp_path, DEFAULT_EXCEPTIONS)
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _first(payload, **changes):
    payload["exceptions"][0].update(changes)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda p: p.update(surpresa=1), "chave desconhecida na raiz"),
        (lambda p: p.update(schema="outro"), "schema"),
        (lambda p: p.update(exceptions="nenhuma"), "precisa ser uma lista"),
        (lambda p: _first(p, chave_nova=1), "chave desconhecida"),
        (lambda p: p["exceptions"][0].pop("review_by"), "faltam as chaves"),
        (lambda p: p["exceptions"][0].pop("decided_by"), "faltam as chaves"),
        (lambda p: _first(p, method="DCF"), "método 'DCF'"),
        (lambda p: _first(p, action="ignorar"), "action 'ignorar'"),
        (lambda p: _first(p, ticker="csud3"), "maiúsculas"),
        (lambda p: _first(p, reason="  "), "reason é obrigatório"),
        (lambda p: _first(p, decided_by=""), "decided_by é obrigatório"),
        (lambda p: _first(p, review_by="março"), "review_by 'março' não é AAAA-MM-DD"),
        (
            lambda p: _first(p, decided_on="ontem"),
            "decided_on 'ontem' não é AAAA-MM-DD",
        ),
        (lambda p: _first(p, review_by="2026-01-01"), "anterior a decided_on"),
        (lambda p: _first(p, review_by=20270320), "todos os campos são texto"),
        (lambda p: p["exceptions"].append(dict(p["exceptions"][0])), "id repetido"),
        (
            lambda p: p["exceptions"].append({**p["exceptions"][0], "id": "outro-id"}),
            "já existe uma exceção",
        ),
        (
            lambda p: p["exceptions"].append(
                {**p["exceptions"][0], "id": "l1", "method": "Bazin", "action": "lead"}
            )
            or p["exceptions"].append(
                {**p["exceptions"][0], "id": "l2", "method": "Graham", "action": "lead"}
            ),
            "já existe uma exceção|já tem um método líder",
        ),
        (lambda p: _first(p, ticker="HGRU11"), "não é uma ação do registro"),
        (lambda p: _first(p, ticker="NAOEXISTE3"), "não é uma ação do registro"),
    ],
)
def test_a_wrong_file_is_an_explicit_error_never_a_silent_no_exceptions(
    tmp_path, mutate, reason
):
    path = _write(tmp_path, mutate)

    with pytest.raises(ValueError, match=reason) as error:
        load_exceptions(tmp_path)

    assert str(path) in str(error.value)
    with pytest.raises(ValueError):
        exceptions_for(tmp_path)  # o caminho do cálculo também não engole o erro


def test_a_file_that_is_not_json_is_an_explicit_error(tmp_path):
    path = _write(tmp_path, lambda p: None)
    path.write_text("{quebrado", encoding="utf-8")

    with pytest.raises(ValueError, match="não é um JSON válido"):
        load_exceptions(tmp_path)


def test_two_leaders_for_one_ticker_are_rejected():
    two = _exc(
        _item(id="a", method="Graham", action="lead"),
        _item(id="b", method="Bazin", action="lead"),
    )

    with pytest.raises(ValueError, match="já tem um método líder"):
        validate(two)


# --- precedence: a declared exception beats the sector keywords ---------------------------


def test_without_an_exception_the_new_classification_makes_graham_apply_to_csud3():
    methods = _methods("CSUD3", *FIN, None)

    assert methods["Graham"].status == "ok"
    assert (
        list(methods)[0] == "Graham"
    )  # e passa a liderar: financeiro não é "dividendo"


def test_a_declared_exclusion_keeps_graham_out_whatever_the_sector_says():
    methods = _methods("CSUD3", *FIN, DEFAULT_EXCEPTIONS)

    assert methods["Graham"].status == "not_applicable"
    assert methods["Bazin"].status == "ok"
    assert "CSUD3-graham-excluir" in methods["Graham"].reason


def test_the_result_cites_the_reason_who_decided_and_the_review_date():
    reason = _methods("CSUD3", *FIN, DEFAULT_EXCEPTIONS)["Graham"].reason

    assert "exceção metodológica CSUD3-graham-excluir" in reason
    assert "valor patrimonial" in reason
    assert "decidida em 2026-09-20 por usuário; revisão até 2027-03-20" in reason


def test_the_exception_wins_over_the_keyword_reason_when_both_would_exclude():
    old = ("Utilidade Pública / Tecnologia", "Processamento de Dados e Serviços")

    with_exc = _methods("CSUD3", *old, DEFAULT_EXCEPTIONS)["Graham"].reason
    without = _methods("CSUD3", *old, None)["Graham"].reason

    assert with_exc.startswith("exceção metodológica")
    assert "tecnologia" in without.lower() and not without.startswith("exceção")


def test_the_exclusion_only_touches_the_named_ticker_and_method():
    other = _methods("OUTRA3", *FIN, DEFAULT_EXCEPTIONS)

    assert other["Graham"].status == "ok" and other["Bazin"].status == "ok"
    assert _methods("CSUD3", *FIN, DEFAULT_EXCEPTIONS)["Bazin"].status == "ok"


def test_a_declared_leader_goes_first_over_the_sector_order():
    dividend_led = ("Financeiro", "Previdência e Seguros")  # Bazin lidera pelo setor
    graham_first = _exc(_item(id="g", ticker="BBSE3", method="Graham", action="lead"))

    default = ordered_methods("equity", *dividend_led, ticker="BBSE3", exceptions=None)
    forced = ordered_methods(
        "equity", *dividend_led, ticker="BBSE3", exceptions=graham_first
    )

    assert default[0] is ValuationMethod.BAZIN
    assert forced[0] is ValuationMethod.GRAHAM
    assert set(forced) == set(default)  # os demais métodos continuam lá


def test_a_declared_leader_can_also_put_bazin_first_in_a_graham_led_sector():
    bazin_first = _exc(_item(id="b", ticker="KLBN4", method="Bazin", action="lead"))
    sector = ("Materiais Básicos", "Madeiras e Papel")

    assert (
        ordered_methods("equity", *sector, ticker="KLBN4")[0] is ValuationMethod.GRAHAM
    )
    assert (
        ordered_methods("equity", *sector, ticker="KLBN4", exceptions=bazin_first)[0]
        is ValuationMethod.BAZIN
    )
    # outro ativo do mesmo setor não muda
    assert (
        ordered_methods("equity", *sector, ticker="FESA4", exceptions=bazin_first)[0]
        is ValuationMethod.GRAHAM
    )


def test_an_exception_never_widens_the_class_catalog():
    lead_dcf_like = _exc(_item(id="z", ticker="BBSE3", method="Bazin", action="lead"))

    assert (
        applicability(
            ValuationMethod.GRAHAM, "fii", ticker="BBSE3", exceptions=lead_dcf_like
        ).applicable
        is False
    )  # Graham não é método de FII, exceção ou não


# --- traceability across the decision, the valuation run and the notes ---------------------


def test_the_decision_explanation_names_the_exceptions_and_their_hash_for_that_ticker_only():
    kwargs = {
        "asset_class": "equity",
        "sector": FIN[0],
        "industry": FIN[1],
        "price": 13.81,
        "financials": {k: v for k, v in INPUTS.items() if k != "ntnb_real_yield"},
        "ntnb_real_yield": 0.0731,
    }

    csud3 = catalog_valuation_for_decision(
        ticker="CSUD3", exceptions=DEFAULT_EXCEPTIONS, **kwargs
    )
    other = catalog_valuation_for_decision(
        ticker="OUTRA3", exceptions=DEFAULT_EXCEPTIONS, **kwargs
    )

    assert "CSUD3-graham-excluir" in csud3.explanation
    assert f"hash {DEFAULT_EXCEPTIONS.content_hash}" in csud3.explanation
    assert csud3.method == "Bazin"  # sem o Graham, o único método é o Bazin
    assert "exceções metodológicas" not in other.explanation
    assert other.method == "Graham"


def _equity(ticker, sector, industry):
    return PortfolioAsset(
        ticker, "equity", cnpj="00.000.000/0000-00", sector=sector, industry=industry
    )


def _value(vault, positions, templates):
    def fetch(symbol, cnpj, ano, bolsai_api_key, brapi_token):
        fetch.calls.append(symbol)
        return templates[symbol], object()

    fetch.calls = []
    result = value_portfolio(
        bolsai_api_key="k",
        brapi_token=None,
        vault_path=str(vault) if vault else None,
        positions=tuple(positions),
        fetch_equity=fetch,
        fetch_rate=lambda: RATE,
        ano=2025,
    )
    return result, fetch


TEMPLATE = {
    "price": 13.81,
    "financials": {"lpa": 2.45, "vpa": 11.75, "dividend_per_share": 0.87},
}


def test_the_valuation_run_reads_the_exceptions_from_the_vault_and_records_them(
    tmp_path,
):
    save_exceptions(tmp_path, DEFAULT_EXCEPTIONS)

    result, _ = _value(tmp_path, [_equity("CSUD3", *FIN)], {"CSUD3": TEMPLATE})

    by_method = {a.method: a for a in result.outcomes[0].attempts}
    assert by_method[ValuationMethod.GRAHAM].status == "not_applicable"
    assert "CSUD3-graham-excluir" in by_method[ValuationMethod.GRAHAM].reason
    assert result.exceptions == DEFAULT_EXCEPTIONS


def test_the_same_run_without_the_file_lets_the_new_classification_decide(tmp_path):
    result, _ = _value(tmp_path, [_equity("CSUD3", *FIN)], {"CSUD3": TEMPLATE})

    by_method = {a.method: a.status for a in result.outcomes[0].attempts}
    assert by_method[ValuationMethod.GRAHAM] == "ok"
    assert result.exceptions is NO_EXCEPTIONS


def test_an_invalid_file_stops_the_valuation_before_fetching_anything(tmp_path):
    path = save_exceptions(tmp_path, DEFAULT_EXCEPTIONS)
    path.write_text("{quebrado", encoding="utf-8")

    with pytest.raises(ValueError, match="não é um JSON válido"):
        _value(tmp_path, [_equity("CSUD3", *FIN)], {"CSUD3": TEMPLATE})


def _note(exceptions, as_of=TODAY):
    result = ValuationRunResult((), None, "NTN-B de teste", exceptions)
    return render_valuation_report(result, as_of=as_of)


def _fm(text):
    out = {}
    for line in text.split("---")[1].strip().splitlines():
        key, _, value = line.partition(": ")
        out[key] = value
    return out


def test_the_valuation_note_carries_the_hash_the_applied_and_the_overdue_exceptions():
    text = _note(DEFAULT_EXCEPTIONS)

    fm = _fm(text)
    assert fm["excecoes_hash"] == DEFAULT_EXCEPTIONS.content_hash
    assert (
        fm["excecoes_aplicadas"] == "[CSUD3-graham-excluir]"
        and fm["excecoes_vencidas"] == "[]"
    )
    assert (
        "## Exceções metodológicas" in text
        and "vigente (revisão até 2027-03-20)" in text
    )
    assert "não são conclusão sobre o valor justo" in text


def test_an_overdue_exception_is_flagged_but_keeps_being_applied():
    # revisão realmente no passado (contra qualquer relógio): 2020
    stale = _exc(_item(decided_on="2020-01-01", review_by="2020-06-01"))
    result = ValuationRunResult((), None, "NTN-B de teste", stale)

    text = render_valuation_report(result, as_of=TODAY)
    graham = _methods("CSUD3", *FIN, stale)["Graham"]

    assert _fm(text)["excecoes_vencidas"] == "[X-graham-excluir]"
    assert "**VENCIDA** (revisão era até 2020-06-01); segue aplicada" in text
    assert graham.status == "not_applicable"  # o vencimento não desliga a regra
    assert "exceção metodológica X-graham-excluir" in graham.reason


def test_a_run_without_exceptions_says_so_in_the_note():
    text = _note(NO_EXCEPTIONS)

    assert (
        _fm(text)["excecoes_hash"] == "null" and "## Exceções metodológicas" not in text
    )


def test_the_exceptions_note_shows_the_effect_and_the_rules():
    text = render_exceptions_report(DEFAULT_EXCEPTIONS, TODAY)

    assert "Graham excluído; método líder: Bazin" in text
    assert "prevalece sobre as palavras-chave do setor" in text
    assert "Vencida, **continua aplicada**" in text and "nada a remove" in text
    assert "não é conclusão sobre o valor justo" in text


# --- sensitivity honors the same exceptions ------------------------------------------------


def test_the_sensitivity_uses_the_same_exceptions_as_the_valuation():
    position = PositionInputs("CSUD3", "equity", FIN[0], FIN[1], 13.81, dict(INPUTS))
    scenarios = ScenarioSet("t", "t", (Scenario("s", "s", nominal_rate_shock_pp=1.0),))

    plain = analyse_asset(position, 0.0731, scenarios)
    declared = analyse_asset(position, 0.0731, scenarios, DEFAULT_EXCEPTIONS)

    assert {m.method for m in plain.base} >= {"Graham", "Bazin"}
    graham_declared = next(m for m in declared.base if m.method == "Graham")
    assert (
        graham_declared.fair_value is None
        and graham_declared.status == "not_applicable"
    )
    bazin = next(m for m in declared.base if m.method == "Bazin")
    assert bazin.status == "ok"  # a exceção só tira o Graham; o Bazin continua


# --- CLI -----------------------------------------------------------------------------------


def _flat(text):
    return "".join(text.split())


def test_the_command_creates_the_declared_exceptions_and_never_overwrites_edits(
    tmp_path,
):
    runner = CliRunner()

    created = runner.invoke(
        cli, ["valuation-exceptions", "--vault", str(tmp_path), "--init", "--report"]
    )
    assert created.exit_code == 0, created.output
    path = tmp_path / "02_Portfolio" / "Excecoes_Valuation.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "editada.9"
    path.write_text(json.dumps(payload), encoding="utf-8")

    again = runner.invoke(
        cli, ["valuation-exceptions", "--vault", str(tmp_path), "--init"]
    )

    assert again.exit_code == 0 and "editada.9" in _flat(again.output)
    assert (tmp_path / "02_Portfolio" / "Excecoes_Valuation.md").exists()


def test_without_a_file_the_command_says_only_the_sector_keywords_apply(tmp_path):
    result = CliRunner().invoke(cli, ["valuation-exceptions", "--vault", str(tmp_path)])

    assert result.exit_code == 0
    flat = _flat(result.output)
    assert "Semarquivodeexceções" in flat  # e diz o que vale no lugar
    assert "palavra-chavedosetor" in flat


def test_the_command_stops_with_the_reason_on_an_invalid_file(tmp_path):
    _write(tmp_path, lambda p: _first(p, method="DCF"))

    result = CliRunner().invoke(cli, ["valuation-exceptions", "--vault", str(tmp_path)])

    assert result.exit_code == 1
    assert "inválidas" in _flat(result.output) and "DCF" in _flat(result.output)


def test_the_command_signals_an_overdue_review_without_removing_anything(
    tmp_path, monkeypatch
):
    late = _exc(_item(review_by="2026-09-21"))
    save_exceptions(tmp_path, late)

    class _Late(dt.date):
        @classmethod
        def today(cls):
            return cls(2027, 1, 1)

    monkeypatch.setattr("datetime.date", _Late)
    result = CliRunner().invoke(cli, ["valuation-exceptions", "--vault", str(tmp_path)])

    assert result.exit_code == 0
    flat = _flat(result.output)
    assert "VENCIDA" in flat and "continuaaplicada" in flat
    assert load_exceptions(tmp_path) == late  # nada foi removido ou alterado


def test_macro_sensitivity_also_stops_on_an_invalid_exceptions_file(tmp_path):
    path = save_exceptions(tmp_path, DEFAULT_EXCEPTIONS)
    path.write_text("{quebrado", encoding="utf-8")
    from iip.macro.scenarios import DEFAULT_SCENARIOS, save_scenarios

    save_scenarios(tmp_path, DEFAULT_SCENARIOS)
    from iip.portfolio.valuation_inputs import (
        BaseRate,
        ValuationInputs,
        save_valuation_inputs,
    )

    save_valuation_inputs(
        tmp_path,
        ValuationInputs(
            "2026-09-20", BaseRate(0.07, "2026-09-18", "2060-08-15", "t"), ()
        ),
    )

    result = CliRunner().invoke(cli, ["macro-sensitivity", "--vault", str(tmp_path)])

    assert result.exit_code == 1 and "inválidas" in _flat(result.output)


# --- architecture: data, not code; every production path passes the exceptions -----------


def _calls(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            called = (
                func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            )
            if called == name:
                yield node


def test_every_production_call_of_the_valuation_functions_passes_the_exceptions():
    checked = {
        "evaluate_valuations": 3,  # posicional/keyword: precisa do keyword exceptions
        "catalog_valuation_for_decision": 3,
    }
    missing = []
    for path in Path("src/iip").rglob("*.py"):
        if path.name in ("valuation_methods.py",):
            continue
        for name in checked:
            for call in _calls(path, name):
                if not any(kw.arg == "exceptions" for kw in call.keywords):
                    missing.append((str(path).replace("\\", "/"), name, call.lineno))
    assert missing == [], f"chamadas sem exceptions=: {missing}"


def test_analyse_asset_and_ntnb_impact_receive_the_exceptions_in_production_code():
    for name, position in (("analyse_asset", 3), ("ntnb_impact", 2)):
        for path in Path("src/iip").rglob("*.py"):
            for call in _calls(path, name):
                has = len(call.args) > position or any(
                    k.arg == "exceptions" for k in call.keywords
                )
                assert has, (str(path), name, call.lineno)


def test_no_ticker_is_hard_coded_in_the_valuation_logic():
    for path in (
        Path("src/iip/portfolio_data/valuation_methods.py"),
        Path("src/iip/decision/catalog_valuation.py"),
    ):
        text = path.read_text(encoding="utf-8-sig")
        assert not re.search(r"""['"][A-Z]{4}\d{1,2}['"]""", text), path
        assert "ticker ==" not in text, path


def test_the_exceptions_module_does_not_import_the_portfolio_package_at_load_time():
    # iip.portfolio importa o avaliador, que importa este módulo: um import no topo faria ciclo
    tree = ast.parse(
        Path("src/iip/portfolio_data/valuation_exceptions.py").read_text(
            encoding="utf-8"
        )
    )
    top = {n.module for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}

    assert not any(
        m and m.startswith("iip.portfolio.") or m == "iip.portfolio" for m in top
    )
