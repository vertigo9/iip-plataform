"""Os insumos da última rodada de valuation, guardados para reavaliar sem buscar nada de novo.

O ``value-portfolio`` busca dados de rede (preço, LPA, VPA, dividendo, NAV) e a taxa real da
NTN-B longa. A sensibilidade a cenários (``iip.macro.sensitivity``) precisa dos MESMOS insumos
para refazer as contas com outra taxa; buscá-los de novo gastaria a cota do bolsai e misturaria
datas. Então cada rodada com ``--report`` grava aqui o que cada método recebeu e a taxa usada,
com a data da rodada: quem reavalia sabe exatamente com que dado, de que dia.

Só números entram (``float`` ou ``None``); o que não é número no template não é insumo de
nenhum método e fica de fora.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path

from iip.portfolio.batch_value import ValuationRunResult

INPUTS_RELATIVE_PATH = Path("07_Research") / "Macro" / "insumos_valuation.json"


@dataclass(frozen=True)
class BaseRate:
    real_yield: float  # fração sobre o IPCA (0,0731 = IPCA + 7,31%)
    reference_date: str  # AAAA-MM-DD, o dia a que a taxa se refere
    maturity: str  # AAAA-MM-DD, o vencimento da NTN-B usada
    title: str
    source: str = "Tesouro Transparente (PrecoTaxaTesouroDireto), Taxa Venda Manhã"


@dataclass(frozen=True)
class PositionInputs:
    ticker: str
    asset_class: str
    sector: str
    industry: str
    price: float | None
    inputs: dict[str, float | None]


@dataclass(frozen=True)
class ValuationInputs:
    run_date: str  # AAAA-MM-DD da rodada de valuation
    base_rate: BaseRate | None
    positions: tuple[PositionInputs, ...]


def _numeric(inputs: dict) -> dict[str, float | None]:
    return {
        key: (float(value) if value is not None else None)
        for key, value in inputs.items()
        if value is None
        or (isinstance(value, (int, float)) and not isinstance(value, bool))
    }


def build_valuation_inputs(
    result: ValuationRunResult, *, run_date: _dt.date
) -> ValuationInputs:
    rate = result.ntnb_rate
    base = (
        BaseRate(
            real_yield=rate.real_yield,
            reference_date=rate.reference_date.isoformat(),
            maturity=rate.maturity.isoformat(),
            title=rate.title,
        )
        if rate is not None
        else None
    )
    positions = tuple(
        PositionInputs(
            ticker=o.ticker,
            asset_class=o.asset_class or "",
            sector=o.sector or "",
            industry=o.industry or "",
            price=o.price,
            inputs=_numeric(o.inputs),
        )
        for o in result.outcomes
        if o.inputs is not None and o.asset_class
    )
    return ValuationInputs(run_date.isoformat(), base, positions)


def save_valuation_inputs(vault_path: str | Path, snapshot: ValuationInputs) -> Path:
    path = Path(vault_path) / INPUTS_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": "valuation_inputs",
        "run_date": snapshot.run_date,
        "base_rate": None if snapshot.base_rate is None else vars(snapshot.base_rate),
        "positions": [vars(p) for p in snapshot.positions],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_valuation_inputs(vault_path: str | Path) -> ValuationInputs | None:
    path = Path(vault_path) / INPUTS_RELATIVE_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        base = raw.get("base_rate")
        return ValuationInputs(
            run_date=raw["run_date"],
            base_rate=BaseRate(**base) if base else None,
            positions=tuple(PositionInputs(**p) for p in raw["positions"]),
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return None
