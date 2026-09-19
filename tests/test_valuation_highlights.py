"""Highlights of the valuation note, and the dashboard block that reads them."""

from datetime import date

from iip.obsidian.dashboard import (
    DASHBOARD_TEMPLATE,
    HIGHLIGHTS_BOTTOM_KEY,
    HIGHLIGHTS_TOP_KEY,
    VALUATION_NOTE_DV_PATH,
    VALUATION_NOTE_LINK,
)
from iip.obsidian.valuation_report import compute_highlights, render_valuation_report
from iip.portfolio.batch_value import ValuationOutcome, ValuationRunResult
from iip.portfolio_data.valuation_methods import evaluate_valuations
from iip.sources.tesouro_direto import NtnbRate

RATE = NtnbRate(
    reference_date=date(2026, 9, 17), maturity=date(2060, 8, 15), real_yield=0.073
)


def _fii(ticker, price, nav, sector="Tijolo", segment="Logístico"):
    attempts = evaluate_valuations(
        ticker=ticker,
        asset_class="fii",
        sector=sector,
        industry=segment,
        price=price,
        inputs={"nav_per_share": nav, "ntnb_real_yield": 0.073},
    )
    return ValuationOutcome(
        ticker, "ok", "d", price, attempts, "fii", f"{sector} / {segment}"
    )


def _funds(margins):
    """One FII per margin: NAV 100 against price 100 / (1 + margin)."""
    return [
        _fii(f"F{i:02d}11", round(100 / (1 + m), 4), 100.0)
        for i, m in enumerate(margins)
    ]


def _result(*outcomes):
    return ValuationRunResult(tuple(outcomes), RATE, "NTN-B longa: IPCA + 7.30%")


# --- computing ---------------------------------------------------------------------------


def test_top_and_bottom_five_by_margin_of_safety_of_the_lead_method():
    result = _result(
        *_funds(
            [-0.30, -0.10, 0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70]
        )
    )

    top, bottom = compute_highlights(result)

    assert [e["margem"] for e in top] == [0.7, 0.6, 0.5, 0.4, 0.3]
    assert [e["margem"] for e in bottom] == [-0.3, -0.1, 0.0, 0.05, 0.1]  # worst first
    assert all(e["metodo"] == "NAV" and e["classe"] == "fii" for e in top + bottom)


def test_the_two_lists_never_share_a_ticker():
    top, bottom = compute_highlights(
        _result(*_funds([-0.2, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5]))
    )

    assert len(top) == 5 and len(bottom) == 2
    assert {e["ticker"] for e in top}.isdisjoint({e["ticker"] for e in bottom})


def test_a_short_portfolio_fills_the_top_and_leaves_the_bottom_empty():
    top, bottom = compute_highlights(_result(*_funds([0.1, 0.2, 0.3])))

    assert len(top) == 3 and bottom == []


def test_positions_without_a_margin_or_a_value_are_left_out():
    no_price = _fii("NOPR11", None, 100.0)  # a value but no price -> no margin
    failed = ValuationOutcome("BAD11", "erro", "x")
    skipped = ValuationOutcome("LFTB11", "pulado", "x")
    good = _fii("GOOD11", 80.0, 100.0)

    top, bottom = compute_highlights(_result(no_price, failed, skipped, good))

    assert [e["ticker"] for e in top] == ["GOOD11"] and bottom == []


def test_ranking_uses_the_margin_of_the_lead_method_not_the_best_one():
    # a dividend-centric equity: Bazin leads even though Graham gives a bigger margin
    attempts = evaluate_valuations(
        ticker="CPFE3",
        asset_class="equity",
        sector="Utilidade Pública",
        industry="Energia Elétrica",
        price=45.17,
        inputs={
            "lpa": 4.97,
            "vpa": 19.72,
            "dividend_per_share": 3.05,
            "dividend_consistency_years": 5,
            "payout_ratio": 61.0,
            "ntnb_real_yield": 0.073,
        },
    )
    outcome = ValuationOutcome("CPFE3", "ok", "d", 45.17, attempts, "equity", "x")

    top, _ = compute_highlights(_result(outcome))

    assert top[0]["metodo"] == "Bazin" and top[0]["margem"] < 0.05


# --- the note ----------------------------------------------------------------------------


def _frontmatter(text):
    return text.split("---")[1]


def _block_list(frontmatter, key):
    """Minimal reader for the block-style lists the report emits (PyYAML is not a
    project dependency): {key: [ {field: value, ...}, ... ]}."""
    lines = frontmatter.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{key}:"))
    if lines[start].strip() == f"{key}: []":
        return []
    items, current = [], None
    for line in lines[start + 1 :]:
        if line.startswith("  - "):
            current = {}
            items.append(current)
            line = line[4:]
        elif line.startswith("    "):
            line = line[4:]
        else:
            break
        name, _, value = line.partition(": ")
        current[name] = (
            None
            if value == "null"
            else (
                float(value)
                if value.replace("-", "").replace(".", "").isdigit()
                else value
            )
        )
    return items


def test_frontmatter_carries_both_lists_in_block_style():
    text = render_valuation_report(
        _result(*_funds([-0.2, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5])), as_of=date(2026, 9, 18)
    )
    head = _frontmatter(text)

    top = _block_list(head, HIGHLIGHTS_TOP_KEY)
    bottom = _block_list(head, HIGHLIGHTS_BOTTOM_KEY)

    assert [e["margem"] for e in top] == [0.5, 0.4, 0.3, 0.2, 0.1]
    assert [e["margem"] for e in bottom] == [-0.2, 0.0]
    assert set(top[0]) == {"ticker", "classe", "metodo", "preco", "valor", "margem"}
    assert (
        "{" not in head.split("tags:")[0].split(HIGHLIGHTS_TOP_KEY)[1]
    )  # no flow mappings


def test_empty_highlights_are_valid_empty_lists():
    head = _frontmatter(render_valuation_report(_result(), as_of=date(2026, 9, 18)))

    assert (
        f"{HIGHLIGHTS_TOP_KEY}: []" in head and f"{HIGHLIGHTS_BOTTOM_KEY}: []" in head
    )


def test_a_missing_price_is_written_as_null_not_omitted():
    top = [
        {
            "ticker": "X",
            "classe": "fii",
            "metodo": "NAV",
            "preco": None,
            "valor": 1.0,
            "margem": 0.1,
        }
    ]
    from iip.obsidian.valuation_report import _yaml_list

    assert "    preco: null" in _yaml_list("k", top)


def test_the_body_repeats_the_highlights_as_readable_tables():
    text = render_valuation_report(
        _result(*_funds([-0.2, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5])), as_of=date(2026, 9, 18)
    )

    section = text.split("## Destaques")[1].split("\n## ")[0]
    assert "**Maiores margens**" in section and "**Menores margens**" in section
    assert "+50%" in section and "-20%" in section
    assert "não são diretamente comparáveis" in section


def test_no_highlights_section_when_nothing_has_a_margin():
    text = render_valuation_report(
        _result(ValuationOutcome("BAD11", "erro", "x")), as_of=date(2026, 9, 18)
    )

    assert "## Destaques" not in text


# --- the dashboard -----------------------------------------------------------------------


def _block():
    start = DASHBOARD_TEMPLATE.index("const p = dv.page(")
    fence = DASHBOARD_TEMPLATE.rindex("```dataviewjs", 0, start)
    end = DASHBOARD_TEMPLATE.index("```\n", start)
    return DASHBOARD_TEMPLATE[fence : end + 3]


def test_the_dashboard_links_the_valuation_note_and_reads_its_frontmatter_fields():
    assert VALUATION_NOTE_LINK in DASHBOARD_TEMPLATE
    block = _block()
    assert f'dv.page("{VALUATION_NOTE_DV_PATH}")' in block
    assert f"p.{HIGHLIGHTS_TOP_KEY}" in block and f"p.{HIGHLIGHTS_BOTTOM_KEY}" in block


def test_the_dashboard_and_the_report_agree_on_the_note_location_and_the_field_names():
    from iip.obsidian.valuation_report import REPORT_RELATIVE_PATH

    assert f"{VALUATION_NOTE_DV_PATH}.md" == REPORT_RELATIVE_PATH.as_posix()
    head = _frontmatter(
        render_valuation_report(_result(*_funds([0.1])), as_of=date(2026, 9, 18))
    )
    assert f"{HIGHLIGHTS_TOP_KEY}:" in head and f"{HIGHLIGHTS_BOTTOM_KEY}:" in head


def test_the_dashboard_block_reads_every_field_the_report_writes():
    block = _block()
    written = set(compute_highlights(_result(*_funds([0.1])))[0][0])

    for field in written:
        assert f"x.{field}" in block, field


def test_the_dashboard_block_degrades_when_the_note_does_not_exist_yet():
    block = _block()

    assert "if (!p)" in block and "iip value-portfolio --report" in block


def test_the_dashboard_block_is_structurally_balanced():
    block = _block()

    assert block.startswith("```dataviewjs") and block.rstrip().endswith("```")
    body = block.split("\n", 1)[1].rsplit("```", 1)[0]
    assert body.count("{") == body.count("}")
    assert body.count("(") == body.count(")")
    assert body.count("[") == body.count("]")
    assert (
        "??" not in body and "?." not in body
    )  # same plain syntax as the other blocks
