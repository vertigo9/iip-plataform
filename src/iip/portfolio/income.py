"""Renda mensal projetada da carteira: distribuição por cota x quantidade.

A distribuição por cota de cada mês sai da série histórica da CVM (Informe Mensal de FII,
guardada em ``02_Portfolio/Historical/<TICKER>.json``): ``dividend_yield_mes x
valor_patrimonial_cotas`` do mesmo mês. Conferido contra a própria CVM (20/09/2026): para
HGRU11 e KNRI11 esse produto bate com ``Rendimentos_Distribuir / Cotas_Emitidas`` do balanço
em menos de 0,5% (HGRU11 ago/2026: R$ 0,9493 contra R$ 0,9500; KNRI11: R$ 1,1013 contra
R$ 1,1002). Para o XPML11 o balanço não serve de prova (o valor a distribuir é de um mês
parcial), e a série dele tem meses repetidos (ver abaixo).

A série tem defeitos reais, que aqui viram exclusão declarada e não número inventado:

  - **Rendimento zero**: AFHI11, BTCI11 e VGIP11 trazem ``dividend_yield_mes = 0`` em quase
    todos os últimos meses. Um fundo de recebíveis não distribui zero por um ano; o campo não
    foi preenchido. Projetar zero seria fabricar um número, então a posição fica sem projeção.
  - **Rendimento negativo ou solto**: a série tem meses impossíveis (XPML11 jan/2026 com
    rendimento de -5,9%; LVBI11 fev/2026 negativo) e meses que não parecem a distribuição
    (XPML11 R$ 0,30 e R$ 0,36 antes de R$ 0,86). Meses de valor não positivo são descartados.
    E uma posição só é projetada se a série for REGULAR: ao menos 2/3 dos meses da janela a
    ±25% da mediana. Sem isso ela fica sem projeção, com a faixa observada, e o valor de
    verdade está no relatório do gestor.
  - **Meses repetidos**: o XPML11 tem meses consecutivos idênticos (mesmo rendimento e mesma
    cota patrimonial), sinal de um informe reapresentado sem atualização. Só o primeiro de
    cada repetição entra.
  - **Meses atípicos**: distribuição extra (KNRI11 R$ 1,38 entre meses de R$ 1,10) ou
    parcial (BTLG11 R$ 0,31). A projeção é a MEDIANA da janela (padrão 6 meses), que ignora
    um mês fora do padrão, e o mês atípico é apontado.
  - **Desdobramento/grupamento** na janela: a cota patrimonial muda de escala e o valor por
    cota deixa de ser comparável entre os meses; a posição fica sem projeção.

O que NÃO cobre: ações (o dividendo vem do balanço anual, não de uma série mensal), FI-Infra,
FIAGRO, ETF, o FMP-FGTS e a renda fixa bancária, que não têm série mensal de distribuição por
cota nas fontes atuais. É renda BRUTA estimada, não uma promessa nem uma previsão de mercado.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, replace

from iip.portfolio.historical_series import (
    HistoricalObservation,
    HistoricalSeries,
    HistoricalSeriesStore,
)
from iip.portfolio_data.income_forecast import (
    MonthlyDistribution,
    forecast_next_distribution,
)
from iip.universal.portfolio_state import PortfolioState, PositionState

DEFAULT_WINDOW = 6
# menos meses que isto e a mediana diz pouco: a posição fica sem projeção
MIN_MONTHS = 3
# um mês mais de X% fora da mediana da janela é atípico
OUTLIER_TOLERANCE = 0.25
# fração mínima dos meses da janela que precisa estar dentro da tolerância para a série
# contar como regular (abaixo disso o ruído da fonte é maior que a informação)
MIN_REGULAR_SHARE = 2 / 3
# mais zeros/negativos que isto entre os últimos 12 meses e a série não é confiável
MAX_INVALID_IN_12 = 5
# a CVM publica o mês M por volta da metade de M+1: uma última competência com mais de
# isto (meses de calendário) atrás já perdeu pelo menos um mês publicado
STALE_AFTER_MONTHS = 2

# motivos de exclusão (o texto vai para a nota)
NO_SERIES = "sem série mensal de distribuição por cota nas fontes atuais"


@dataclass(frozen=True)
class IncomeLine:
    ticker: str
    quantity: float
    market_value: float
    status: str  # "projetada" ou "sem projeção"
    reason: str = ""
    # regular | absent | zero | split | few | irregular (o motivo em texto está em reason)
    code: str = ""
    months: tuple[MonthlyDistribution, ...] = ()  # os meses que entraram na mediana
    unusual: tuple[str, ...] = ()  # períodos fora do padrão dentro da janela
    repeated: tuple[str, ...] = ()  # períodos repetidos, descartados
    last_period: str | None = None
    per_unit: float | None = (
        None  # a estimativa da CVM (cvm_estimate), sempre preservada
    )
    monthly_income: float | None = None
    # --- o que o gestor declara e a estimativa que vale (ver apply_manager_estimates) ---
    manager_reported_distribution: float | None = None
    manager_reference: str | None = (
        None  # data do relatório / da distribuição, se conhecida
    )
    manager_source_url: str | None = None
    validation_status: str | None = None  # a situação da validação cruzada, se houve
    effective_estimate: float | None = None  # R$/cota que entra no total
    effective_income: float | None = None
    estimate_source: str = ""  # cvm | manager | cvm_capped_by_manager
    override_reason: str = ""

    @property
    def cvm_estimate(self) -> float | None:
        return self.per_unit


# de onde vem a estimativa efetiva, em português, para as notas
SOURCE_LABELS = {
    "cvm": "CVM",
    "manager": "gestor",
    "cvm_capped_by_manager": "CVM limitada pelo gestor",
}


@dataclass(frozen=True)
class IncomeReport:
    as_of: _dt.date | None
    total_value: float
    lines: tuple[IncomeLine, ...]
    window: int
    today: _dt.date

    @property
    def projected(self) -> tuple[IncomeLine, ...]:
        return tuple(ln for ln in self.lines if ln.status == "projetada")

    @property
    def effective_lines(self) -> tuple[IncomeLine, ...]:
        """As posições que entram no total: a estimativa da CVM ou, onde a regra manda, a do
        gestor."""
        return tuple(ln for ln in self.lines if ln.effective_income is not None)

    @property
    def excluded(self) -> tuple[IncomeLine, ...]:
        """As que ficam fora do total: sem estimativa efetiva (nem da CVM, nem do gestor)."""
        return tuple(ln for ln in self.lines if ln.effective_income is None)

    @property
    def monthly_income(self) -> float:
        """O total, com a estimativa efetiva de cada posição (híbrido se houver do gestor)."""
        return sum(ln.effective_income or 0.0 for ln in self.effective_lines)

    @property
    def cvm_monthly_income(self) -> float:
        """O total só das projeções da CVM, sem nenhum ajuste do gestor."""
        return sum(ln.monthly_income or 0.0 for ln in self.projected)

    @property
    def adjustments(self) -> tuple[IncomeLine, ...]:
        """As posições cuja estimativa efetiva NÃO é a da CVM pura."""
        return tuple(ln for ln in self.effective_lines if ln.estimate_source != "cvm")

    @property
    def is_hybrid(self) -> bool:
        return bool(self.adjustments)

    @property
    def covered_share(self) -> float:
        return sum(ln.market_value for ln in self.effective_lines) / self.total_value

    @property
    def stale_series(self) -> tuple[IncomeLine, ...]:
        return tuple(
            ln for ln in self.projected if _is_stale(ln.last_period, self.today)
        )


def _is_stale(last_period: str | None, today: _dt.date) -> bool:
    if not last_period:
        return False
    year, month = int(last_period[:4]), int(last_period[5:7])
    months_old = (today.year - year) * 12 + (today.month - month)
    return months_old > STALE_AFTER_MONTHS


def _per_unit(observation: HistoricalObservation) -> float | None:
    dy, nav = observation.dividend_yield_mes, observation.valor_patrimonial_cotas
    if dy is None or nav is None or nav <= 0:
        return None
    return dy * nav


def _scale_break_in(series: HistoricalSeries, periods: set[str]) -> bool:
    return any(period in periods for period, _ in series.scale_breaks)


def _project(
    position: PositionState, series: HistoricalSeries, window: int
) -> IncomeLine:
    base = {
        "ticker": position.ticker,
        "quantity": position.quantity,
        "market_value": position.market_value,
    }
    observed = sorted(
        (o for o in series.observations if _per_unit(o) is not None),
        key=lambda o: o.period,
    )
    if not observed:
        return IncomeLine(
            **base, status="sem projeção", reason=NO_SERIES, code="absent"
        )

    recent = observed[-12:]
    last_period = observed[-1].period[:7]
    invalid_recent = sum(1 for o in recent if _per_unit(o) <= 0)
    if invalid_recent > MAX_INVALID_IN_12:
        return IncomeLine(
            **base,
            status="sem projeção",
            code="zero",
            last_period=last_period,
            reason=(
                f"a CVM informa rendimento zero ou negativo em {invalid_recent} dos "
                f"últimos {len(recent)} meses; o campo parece não preenchido por este "
                "fundo, e projetar zero seria inventar um número"
            ),
        )

    # descarta a cópia de um mês idêntico ao anterior (mesmo rendimento e mesma cota)
    kept: list[HistoricalObservation] = []
    repeated: list[str] = []
    for obs in observed:
        if (
            kept
            and obs.dividend_yield_mes == kept[-1].dividend_yield_mes
            and obs.valor_patrimonial_cotas == kept[-1].valor_patrimonial_cotas
        ):
            repeated.append(obs.period[:7])
            continue
        kept.append(obs)

    sample = [o for o in kept if _per_unit(o) > 0][-window:]
    if _scale_break_in(series, {o.period for o in sample}):
        return IncomeLine(
            **base,
            status="sem projeção",
            code="split",
            last_period=last_period,
            reason="desdobramento ou grupamento na janela: o valor por cota não é "
            "comparável entre os meses",
        )
    if len(sample) < MIN_MONTHS:
        return IncomeLine(
            **base,
            status="sem projeção",
            code="few",
            last_period=last_period,
            reason=f"só {len(sample)} mês(es) utilizável(is) na janela (mínimo "
            f"{MIN_MONTHS})",
        )

    history = tuple(
        MonthlyDistribution(o.period[:7], round(_per_unit(o), 6)) for o in sample
    )
    forecast = forecast_next_distribution(
        position.ticker, history, window=window, statistic="median"
    )
    centre = forecast.projected_amount_per_unit
    unusual = tuple(
        h.period
        for h in history
        if abs(h.amount_per_unit - centre) / centre > OUTLIER_TOLERANCE
    )
    regular = len(history) - len(unusual)
    if regular / len(history) < MIN_REGULAR_SHARE:
        amounts = [h.amount_per_unit for h in history]
        return IncomeLine(
            **base,
            status="sem projeção",
            code="irregular",
            last_period=last_period,
            months=history,
            unusual=unusual,
            repeated=tuple(r for r in repeated if r >= sample[0].period[:7]),
            reason=(
                f"série irregular: só {regular} de {len(history)} meses ficam a "
                f"±{OUTLIER_TOLERANCE:.0%} da mediana (R$ {min(amounts):.4f} a "
                f"R$ {max(amounts):.4f} por cota); o dado da CVM deste fundo é ruidoso, "
                "confira no relatório do gestor"
            ),
        )
    return IncomeLine(
        **base,
        status="projetada",
        code="regular",
        months=history,
        unusual=unusual,
        repeated=tuple(r for r in repeated if r >= sample[0].period[:7]),
        last_period=last_period,
        per_unit=centre,
        monthly_income=centre * position.quantity,
    )


def _effective(line: IncomeLine, check) -> IncomeLine:
    """Aplica a regra de estimativa efetiva a uma posição.

    A estimativa da CVM nunca é sobrescrita nem descartada (``per_unit`` continua nela); a
    efetiva é outro campo, com a fonte e o motivo. As regras (decisão do usuário, 20/09/2026):

      - a CVM não projeta e o gestor declara (``so_gestor``): entra o valor do gestor, como
        estimativa do gestor;
      - a validação DIVERGE e o gestor declara MENOS que a CVM: o consolidado fica no valor do
        gestor (limite conservador provisório, até a divergência ser esclarecida); se o gestor
        declara mais, mantém a CVM (a divergência não infla a renda);
      - nos demais casos (confere, mudança recente, sem gestor) vale a CVM.
    """
    cvm = line.per_unit if line.status == "projetada" else None
    declared = getattr(check, "declared", None) if check is not None else None
    status = getattr(check, "status", None) if check is not None else None
    common = {
        "manager_reported_distribution": declared,
        "manager_reference": getattr(check, "reference", None) if check else None,
        "manager_source_url": getattr(check, "source_url", None) if check else None,
        "validation_status": status,
    }
    if declared and cvm is None and status == "so_gestor":
        return replace(
            line,
            **common,
            effective_estimate=declared,
            effective_income=declared * line.quantity,
            estimate_source="manager",
            override_reason="a série da CVM não permite projetar este fundo; entra a "
            "estimativa declarada pelo gestor, identificada como tal",
        )
    if declared and cvm is not None and status == "diverge" and declared < cvm:
        return replace(
            line,
            **common,
            effective_estimate=declared,
            effective_income=declared * line.quantity,
            estimate_source="cvm_capped_by_manager",
            override_reason="a CVM e o gestor divergem e o gestor declara menos: o "
            "consolidado usa o valor do gestor como limite conservador provisório, até a "
            "divergência ser esclarecida; o valor da CVM segue registrado ao lado",
        )
    if cvm is None:
        return replace(line, **common)
    return replace(
        line,
        **common,
        effective_estimate=cvm,
        effective_income=line.monthly_income,
        estimate_source="cvm",
    )


def build_income(
    state: PortfolioState,
    store: HistoricalSeriesStore,
    *,
    today: _dt.date,
    window: int = DEFAULT_WINDOW,
    checks: dict | None = None,
) -> IncomeReport:
    positions = tuple(p for p in state.positions if p.market_value > 0)
    total = sum(p.market_value for p in positions)
    if total <= 0:
        raise ValueError("o snapshot não tem posição com valor: nada a projetar")
    if window < MIN_MONTHS:
        raise ValueError(f"a janela precisa de pelo menos {MIN_MONTHS} meses")

    lines = []
    for position in positions:
        try:
            series = store.load(position.ticker)
        except FileNotFoundError:
            lines.append(
                IncomeLine(
                    position.ticker,
                    position.quantity,
                    position.market_value,
                    "sem projeção",
                    NO_SERIES,
                    code="absent",
                )
            )
            continue
        lines.append(_project(position, series, window))

    try:
        as_of = _dt.date.fromisoformat(state.as_of)
    except ValueError:
        as_of = None
    checks = checks or {}
    lines = [_effective(ln, checks.get(ln.ticker)) for ln in lines]
    lines.sort(
        key=lambda ln: (
            ln.effective_income is None,
            -(ln.effective_income or 0.0),
            ln.ticker,
        )
    )
    return IncomeReport(as_of, total, tuple(lines), window, today)
