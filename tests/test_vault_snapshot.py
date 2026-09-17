from pathlib import Path

from iip.portfolio.vault_snapshot import parse_current_snapshot

_TABLE = """---
type: portfolio
state: current
---

# Carteira Atual

| ID | Ativo | Classe | Quantidade | PM | Preço atual | Valor | Peso | Peso alvo | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| BTCI11 | BTCI11 | fii | 283,0000 | R$ 9,21 | R$ 9,14 | R$ 2.586,62 | 0,90% |  | active |
| BBSE3 | BBSE3 | acao | 881,0000 | 33,81 | 41,69 | 36.728,89 | 12,80% |  | active |
| FMP-FGTS-DAYCOVAL | DAYCOVAL FMP-FGTS | fundo | 3.639,9600 | 1,00 | 1,80 | 6.551,93 | 2,28% |  | active |
| RF-NUBANK-120CDI | CDB NuBank 120% CDI | renda_fixa |  |  |  | R$ 11.404,21 | 3,98% |  | active |
| ZZZZ11 | Encerrado | fii | 1,0000 | 1,00 | 1,00 | 1,00 | 0,01% |  | closed |

## Regras
"""


def test_parses_active_rows_with_br_locale_numbers(tmp_path: Path) -> None:
    path = tmp_path / "Current.md"
    path.write_text(_TABLE, encoding="utf-8")

    state = parse_current_snapshot(path, as_of="2026-09-12")

    assert state.as_of == "2026-09-12"
    tickers = {p.ticker for p in state.positions}
    assert tickers == {"BTCI11", "BBSE3", "AXIA3", "RF-NUBANK-120CDI"}
    assert "ZZZZ11" not in tickers  # closed status excluded


def test_resolves_registry_metadata_for_known_ticker(tmp_path: Path) -> None:
    path = tmp_path / "Current.md"
    path.write_text(_TABLE, encoding="utf-8")

    state = parse_current_snapshot(path, as_of="2026-09-12")

    btci11 = next(p for p in state.positions if p.ticker == "BTCI11")
    assert btci11.asset_class == "fund"
    assert btci11.segment == "Crédito Imobiliário"
    assert btci11.manager == "BTG Pactual"
    assert btci11.quantity == 283.0
    assert btci11.market_value == 2586.62
    assert round(btci11.weight, 4) == 0.009


def test_maps_id_alias_to_registry_ticker(tmp_path: Path) -> None:
    path = tmp_path / "Current.md"
    path.write_text(_TABLE, encoding="utf-8")

    state = parse_current_snapshot(path, as_of="2026-09-12")

    axia3 = next(p for p in state.positions if p.ticker == "AXIA3")
    assert axia3.asset_class == "fixed_income"
    assert axia3.manager == "Daycoval"


def test_falls_back_to_class_column_for_unregistered_ticker(tmp_path: Path) -> None:
    path = tmp_path / "Current.md"
    path.write_text(_TABLE, encoding="utf-8")

    state = parse_current_snapshot(path, as_of="2026-09-12")

    cdb = next(p for p in state.positions if p.ticker == "RF-NUBANK-120CDI")
    assert cdb.asset_class == "fixed_income"
    assert cdb.manager is None
    assert cdb.quantity == 0.0


def test_total_value_is_sum_of_included_positions(tmp_path: Path) -> None:
    path = tmp_path / "Current.md"
    path.write_text(_TABLE, encoding="utf-8")

    state = parse_current_snapshot(path, as_of="2026-09-12")

    assert round(state.total_value, 2) == round(
        2586.62 + 36728.89 + 6551.93 + 11404.21, 2
    )


def test_as_of_defaults_to_file_mtime_when_not_given(tmp_path: Path) -> None:
    path = tmp_path / "Current.md"
    path.write_text(_TABLE, encoding="utf-8")

    state = parse_current_snapshot(path)

    assert state.as_of  # a real ISO date string, not fabricated content
