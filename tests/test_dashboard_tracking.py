import json
import re
from datetime import date

from click.testing import CliRunner

from iip.cli.main import cli
from iip.obsidian import dashboard as dash
from iip.obsidian.dashboard import DASHBOARD_TEMPLATE, generate_portfolio_dashboard
from iip.obsidian.decision_report import (
    REPORT_RELATIVE_PATH as DECISIONS_PATH,
)
from iip.obsidian.decision_report import (
    render_decision_report,
)
from iip.obsidian.exposure_report import (
    REPORT_RELATIVE_PATH as EXPOSURE_PATH,
)
from iip.obsidian.exposure_report import (
    render_exposure_report,
)
from iip.obsidian.income_report import REPORT_RELATIVE_PATH as INCOME_PATH
from iip.obsidian.income_report import render_income_report
from iip.obsidian.series_report import REPORT_RELATIVE_PATH as SERIES_PATH
from iip.obsidian.series_report import render_series_report
from iip.portfolio.batch_decide import DecisionOutcome, DecisionRunResult
from iip.portfolio.exposure import build_exposure
from iip.portfolio.income import IncomeLine, IncomeReport
from iip.portfolio.series_state import SeriesState, series_alerts
from iip.portfolio_data.income_forecast import MonthlyDistribution
from iip.universal.portfolio_state import PortfolioState, PositionState

TODAY = date(2026, 9, 20)


def _frontmatter(text):
    """As linhas `chave: valor` do cabeçalho; os valores em JSON de uma linha viram objetos."""
    block = text.split("---")[1]
    out = {}
    for line in block.strip().splitlines():
        key, _, value = line.partition(": ")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def _ok(ticker, verdict, previous=None):
    return DecisionOutcome(
        ticker,
        "ok",
        verdict,
        asset_class="equity",
        verdict=verdict,
        score=5.0,
        confidence=0.5,
        previous_verdict=previous,
        analysis_score=50.0,
    )


# --- the dashboard reads the same paths and keys the reports write -------------


def test_each_report_path_matches_the_path_the_dashboard_reads():
    assert dash.DECISIONS_NOTE_DV_PATH + ".md" == DECISIONS_PATH.as_posix()
    assert dash.EXPOSURE_NOTE_DV_PATH + ".md" == EXPOSURE_PATH.as_posix()
    assert dash.INCOME_NOTE_DV_PATH + ".md" == INCOME_PATH.as_posix()
    assert dash.SERIES_NOTE_DV_PATH + ".md" == SERIES_PATH.as_posix()


def test_every_block_reads_a_key_that_its_note_actually_writes():
    decisions = _frontmatter(
        render_decision_report(
            DecisionRunResult(
                (_ok("PASS3", "REDUZIR", "MANTER"), _ok("XPML11", "MANTER")),
                "nota",
                TODAY,
            )
        )
    )
    state = PortfolioState(
        "2026-09-12",
        (PositionState("BBSE3", 1.0, 600.0, 0.6, "equity"),),
        600.0,
    )
    exposure = _frontmatter(render_exposure_report(build_exposure(state, today=TODAY)))
    income = _frontmatter(
        render_income_report(
            IncomeReport(
                None,
                1000.0,
                (
                    IncomeLine(
                        "HGRU11",
                        10,
                        500.0,
                        "projetada",
                        per_unit=0.9,
                        monthly_income=9.0,
                        months=(MonthlyDistribution("2026-08", 0.9),),
                        code="regular",
                    ),
                    IncomeLine(
                        "XPML11",
                        10,
                        500.0,
                        "sem projeção",
                        "irregular",
                        code="irregular",
                        last_period="2026-08",
                    ),
                ),
                6,
                TODAY,
            )
        )
    )
    series = _frontmatter(
        render_series_report(
            (SeriesState("XPML11", "irregular", "2026-08", 12, "2026-09-20", False),),
            (),
            today_iso="2026-09-20",
        )
    )

    assert (
        dash.DECISIONS_SUMMARY_KEY in decisions
        and dash.DECISIONS_CHANGES_KEY in decisions
    )
    for key in (
        dash.EXPOSURE_AGE_KEY,
        dash.EXPOSURE_DATE_KEY,
        dash.EXPOSURE_STALE_KEY,
        dash.EXPOSURE_MISSING_KEY,
        dash.EXPOSURE_FLAGS_KEY,
    ):
        assert key in exposure
    for key in (
        dash.INCOME_MONTHLY_KEY,
        dash.INCOME_COVERAGE_KEY,
        dash.INCOME_EXCLUDED_KEY,
    ):
        assert key in income
    assert dash.SERIES_TOTAL_KEY in series and dash.SERIES_PROBLEMS_KEY in series


def test_the_dashboard_template_uses_each_key_it_defines():
    for key in (
        dash.DECISIONS_SUMMARY_KEY,
        dash.DECISIONS_CHANGES_KEY,
        dash.EXPOSURE_FLAGS_KEY,
        dash.EXPOSURE_STALE_KEY,
        dash.EXPOSURE_AGE_KEY,
        dash.EXPOSURE_DATE_KEY,
        dash.EXPOSURE_MISSING_KEY,
        dash.INCOME_MONTHLY_KEY,
        dash.INCOME_COVERAGE_KEY,
        dash.INCOME_EXCLUDED_KEY,
        dash.SERIES_PROBLEMS_KEY,
        dash.SERIES_TOTAL_KEY,
    ):
        assert f"p.{key}" in DASHBOARD_TEMPLATE, key


def test_the_wiki_links_point_at_notes_the_job_writes():
    targets = set(re.findall(r"\[\[(\w+)\|", DASHBOARD_TEMPLATE))

    assert {"Valuation", "Decisoes", "Exposicao", "Renda", "Series"} <= targets
    written = {
        DECISIONS_PATH.stem,
        EXPOSURE_PATH.stem,
        INCOME_PATH.stem,
        SERIES_PATH.stem,
        "Valuation",
    }
    assert targets <= written


def test_a_block_whose_note_is_missing_or_old_says_so_instead_of_an_empty_table():
    for note_path, key in (
        (dash.DECISIONS_NOTE_DV_PATH, dash.DECISIONS_SUMMARY_KEY),
        (dash.EXPOSURE_NOTE_DV_PATH, dash.EXPOSURE_AGE_KEY),
        (dash.INCOME_NOTE_DV_PATH, dash.INCOME_MONTHLY_KEY),
        (dash.SERIES_NOTE_DV_PATH, dash.SERIES_TOTAL_KEY),
    ):
        assert f'dv.page("{note_path}")' in DASHBOARD_TEMPLATE
        assert f"if (!p || p.{key} === undefined)" in DASHBOARD_TEMPLATE
    assert "versão anterior" in DASHBOARD_TEMPLATE


def test_the_dashboard_states_that_a_decision_is_a_proposal():
    assert "proposta para aprovação, não uma ordem" in DASHBOARD_TEMPLATE
    assert "não promessa" in DASHBOARD_TEMPLATE


# --- states: problematic series, changes and concerns reach the frontmatter ---------


def test_decision_changes_and_their_direction_reach_the_frontmatter():
    result = DecisionRunResult(
        (_ok("PASS3", "REDUZIR", "MANTER"), _ok("XPML11", "MANTER", "AGUARDAR")),
        "nota",
        TODAY,
    )

    fm = _frontmatter(render_decision_report(result))

    assert fm[dash.DECISIONS_SUMMARY_KEY] == {"MANTER": 1, "REDUZIR": 1}
    assert fm[dash.DECISIONS_CHANGES_KEY][0] == {
        "ticker": "PASS3",
        "de": "MANTER",
        "para": "REDUZIR",
        "sentido": "piora",
    }


def test_a_stale_snapshot_and_a_concentration_flag_reach_the_frontmatter():
    state = PortfolioState(
        "2026-09-12",
        (
            PositionState("BBSE3", 1.0, 600.0, 0.6, "equity"),
            PositionState("RF-A", 1.0, 400.0, 0.4, "fixed_income"),
        ),
        1000.0,
    )

    fm = _frontmatter(render_exposure_report(build_exposure(state, today=TODAY)))

    assert fm[dash.EXPOSURE_STALE_KEY] is True and fm[dash.EXPOSURE_AGE_KEY] == 8
    assert "HGRU11" in fm[dash.EXPOSURE_MISSING_KEY]
    assert any(
        f["grupo"] == "BBSE3" and f["tipo"] == "posição"
        for f in fm[dash.EXPOSURE_FLAGS_KEY]
    )


def test_problematic_series_reach_the_frontmatter_and_healthy_ones_do_not():
    states = (
        SeriesState("OK11", "regular", "2026-08", 60, "2026-09-20", False),
        SeriesState("BTCI11", "zero", "2026-08", 60, "2026-09-20", False),
        SeriesState("OLD11", "regular", "2026-06", 60, "2026-09-01", True),
    )

    fm = _frontmatter(
        render_series_report(states, series_alerts({}, states), today_iso="2026-09-20")
    )

    assert fm[dash.SERIES_TOTAL_KEY] == 3
    by_ticker = {p["ticker"]: p for p in fm[dash.SERIES_PROBLEMS_KEY]}
    assert set(by_ticker) == {"BTCI11", "OLD11"}
    assert by_ticker["BTCI11"]["situacao"] == "rendimento zero ou negativo"
    assert by_ticker["OLD11"]["defasada"] is True


def test_the_income_frontmatter_lists_only_funds_with_a_series_but_no_projection():
    report = IncomeReport(
        None,
        1000.0,
        (
            IncomeLine(
                "HGRU11",
                10,
                400.0,
                "projetada",
                per_unit=0.9,
                monthly_income=9.0,
                months=(MonthlyDistribution("2026-08", 0.9),),
                code="regular",
                last_period="2026-08",
            ),
            IncomeLine(
                "XPML11",
                10,
                300.0,
                "sem projeção",
                "irregular",
                code="irregular",
                last_period="2026-08",
            ),
            IncomeLine("BBSE3", 10, 300.0, "sem projeção", "sem série", code="absent"),
        ),
        6,
        TODAY,
    )

    fm = _frontmatter(render_income_report(report))

    assert fm[dash.INCOME_MONTHLY_KEY] == 9.0
    assert fm[dash.INCOME_COVERAGE_KEY] == 0.4
    assert fm[dash.INCOME_EXCLUDED_KEY] == [
        {"ticker": "XPML11", "situacao": "irregular"}
    ]


def test_special_characters_in_a_value_do_not_break_the_frontmatter():
    state = PortfolioState(
        "2026-09-12",
        (PositionState("BBSE3", 1.0, 100.0, 1.0, "equity"),),
        100.0,
    )

    text = render_exposure_report(build_exposure(state, today=TODAY))

    fm = _frontmatter(text)
    assert isinstance(fm[dash.EXPOSURE_FLAGS_KEY], list)


# --- generation ----------------------------------------------------------------


def test_the_dashboard_is_still_idempotent_with_the_new_section(tmp_path):
    first = generate_portfolio_dashboard(tmp_path).read_text(encoding="utf-8")
    second = generate_portfolio_dashboard(tmp_path).read_text(encoding="utf-8")

    assert first == second and "Acompanhamento da Carteira" in first


def test_the_command_writes_the_dashboard(tmp_path):
    out = CliRunner().invoke(cli, ["dashboard", "--vault", str(tmp_path)])

    assert out.exit_code == 0, out.output
    assert (tmp_path / "02_Portfolio" / "Dashboard.md").exists()


# --- DataviewJS sanity (there is no JS engine in the test environment) --------------


def _balanced(js):
    """Chaves, colchetes e parênteses balanceados fora de literais de texto: pega o erro de
    montagem mais comum do template (uma chave duplicada ou perdida numa f-string)."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack, quote, escaped = [], None, False
    for ch in js:
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'`":
            quote = ch
        elif ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack and quote is None


def test_every_dataviewjs_block_has_balanced_brackets_and_strings():
    blocks = re.findall(r"```dataviewjs\n(.*?)```", DASHBOARD_TEMPLATE, re.S)

    assert len(blocks) >= 9  # os 5 já existentes + os 4 do acompanhamento
    for index, block in enumerate(blocks):
        assert _balanced(block), f"bloco {index} desbalanceado:\n{block}"


def test_the_balance_check_catches_a_broken_block():
    assert not _balanced('if (a) { dv.paragraph("x"); ')
    assert not _balanced('dv.paragraph("aberta);')
    assert _balanced('const a = {b: [1, 2]}; dv.table(["x"], a);')
