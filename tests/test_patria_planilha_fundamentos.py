from __future__ import annotations

import openpyxl
import pytest

from iip.cli import fetch_template
from iip.sources import patria_planilha_fundamentos_harvester as harvester_module
from iip.sources.patria_planilha_fundamentos import (
    FundamentosPlanilha,
    parse_resumo_tijolo,
)
from iip.sources.patria_planilha_fundamentos_harvester import (
    FetchedPlanilhaFundamentos,
    _planilha_category,
)


def _tijolo_workbook(*, start_col: int = 3, pl_format: str = "General"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumo"
    labels_and_values = [
        ("Patrimônio Líquido", 2500.0),
        ("Valor de Mercado", 2000.0),
        ("Nº de Ativos", 12),
        ("Nº de Locatários", 30),
        ("ABL (m2)", 500000.0),
        ("WALE", 4.5),
        ("Vacância Física", 0.05),
        ("Vacância Financeira", 0.02),
        ("P/VP", 0.9),
        ("DY (Mercado)", 0.08),
        ("DY (Patrimonial)", 0.07),
    ]
    for i, (label, value) in enumerate(labels_and_values):
        col = start_col + i
        ws.cell(row=10, column=col, value=label)
        cell = ws.cell(row=11, column=col, value=value)
        if label == "Patrimônio Líquido":
            cell.number_format = pl_format
    return wb


def test_parse_resumo_tijolo_reads_values_below_labels():
    result = parse_resumo_tijolo(_tijolo_workbook(), "lvbi11")

    assert result is not None
    assert result.ticker == "LVBI11"
    assert result.wale_anos == 4.5
    assert result.vacancia_financeira == 0.02
    assert result.n_locatarios == 30
    assert result.occupancy_rate == pytest.approx(0.98)


def test_parse_resumo_tijolo_is_column_position_independent():
    result = parse_resumo_tijolo(_tijolo_workbook(start_col=2), "HGRU11")

    assert result is not None
    assert result.wale_anos == 4.5


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ('"R$ "#,##0.0" milhões"', 2_500_000_000.0),
        ('"R$ "#,##0.0" bilhões"', 2_500_000_000_000.0),
        ("General", 2500.0),
    ],
)
def test_parse_resumo_tijolo_normalizes_unit_from_number_format(fmt, expected):
    result = parse_resumo_tijolo(_tijolo_workbook(pl_format=fmt), "PVBI11")

    assert result is not None
    assert result.patrimonio_liquido == expected


def test_parse_resumo_tijolo_returns_none_without_resumo_sheet():
    wb = openpyxl.Workbook()
    wb.active.title = "Outra"

    assert parse_resumo_tijolo(wb, "HGRU11") is None


def test_parse_resumo_tijolo_returns_none_for_credit_fund_layout():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resumo"
    ws["B2"] = "Patrimônio Líquido"
    ws["B3"] = 100
    ws["D2"] = "% PL por classe de ativo"

    assert parse_resumo_tijolo(wb, "HGCR11") is None


def test_occupancy_rate_is_none_without_vacancia_financeira():
    fund = FundamentosPlanilha(
        ticker="X",
        competencia=None,
        patrimonio_liquido=None,
        valor_mercado=None,
        n_ativos=None,
        n_locatarios=None,
        abl_m2=None,
        wale_anos=None,
        vacancia_fisica=None,
        vacancia_financeira=None,
        p_vp=None,
        dy_mercado=None,
        dy_patrimonial=None,
    )

    assert fund.occupancy_rate is None


def test_planilha_category_matches_slug_and_label_styles():
    assert (
        _planilha_category(("lvbi11_relatorio", "lvbi11_planilha_de_fundamentos"))
        == "lvbi11_planilha_de_fundamentos"
    )
    assert (
        _planilha_category(("HGRU - Planilha de Fundamentos",))
        == "HGRU - Planilha de Fundamentos"
    )
    assert _planilha_category(("hgru_relatorio_gerencial",)) is None


# --- _enrich_fii_with_patria_fundamentos -------------------------------


def _fundamentos(**overrides) -> FundamentosPlanilha:
    base = {
        "ticker": "LVBI11",
        "competencia": None,
        "patrimonio_liquido": None,
        "valor_mercado": None,
        "n_ativos": None,
        "n_locatarios": None,
        "abl_m2": None,
        "wale_anos": 4.5678,
        "vacancia_fisica": 0.05,
        "vacancia_financeira": 0.02,
        "p_vp": None,
        "dy_mercado": None,
        "dy_patrimonial": None,
    }
    base.update(overrides)
    return FundamentosPlanilha(**base)


def _patch_harvester(monkeypatch, *, result=None, error=None):
    class _FakeHarvester:
        def fetch(self, ticker):
            if error is not None:
                raise error
            return result

    monkeypatch.setattr(
        harvester_module, "PatriaPlanilhaFundamentosHTTPHarvester", _FakeHarvester
    )


def test_enrich_is_silent_noop_for_non_patria_ticker(monkeypatch):
    _patch_harvester(monkeypatch, error=AssertionError("must not be called"))
    financials = {"occupancy_rate": 0.85}

    out, fetched, warnings = fetch_template._enrich_fii_with_patria_fundamentos(
        financials, "BTLG11"
    )

    assert out is financials
    assert fetched == []
    assert warnings == []


def test_enrich_fills_occupancy_and_wale(monkeypatch):
    _patch_harvester(
        monkeypatch,
        result=FetchedPlanilhaFundamentos(
            ticker="LVBI11", category="c", document=None, fundamentos=_fundamentos()
        ),
    )
    financials = {"occupancy_rate": 0.85, "avg_lease_term_years": 5, "other": 1}

    out, fetched, warnings = fetch_template._enrich_fii_with_patria_fundamentos(
        financials, "LVBI11"
    )

    assert out["occupancy_rate"] == pytest.approx(0.98)
    assert out["avg_lease_term_years"] == 4.57
    assert out["other"] == 1
    assert fetched == ["occupancy_rate", "avg_lease_term_years"]
    assert warnings == []
    assert financials["occupancy_rate"] == 0.85  # input not mutated


def test_enrich_warns_when_layout_is_not_tijolo(monkeypatch):
    _patch_harvester(
        monkeypatch,
        result=FetchedPlanilhaFundamentos(
            ticker="HGCR11", category="c", document=None, fundamentos=None
        ),
    )
    financials = {"occupancy_rate": 0.85}

    out, fetched, warnings = fetch_template._enrich_fii_with_patria_fundamentos(
        financials, "HGCR11"
    )

    assert out == financials
    assert fetched == []
    assert len(warnings) == 1


def test_enrich_never_raises_on_fetch_failure(monkeypatch):
    _patch_harvester(monkeypatch, error=OSError("rede caiu"))

    out, fetched, warnings = fetch_template._enrich_fii_with_patria_fundamentos(
        {"occupancy_rate": 0.85}, "LVBI11"
    )

    assert out == {"occupancy_rate": 0.85}
    assert fetched == []
    assert "rede caiu" in warnings[0]
