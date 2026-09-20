"""A sensibilidade a cenários como nota do vault: ``07_Research/Macro/Sensibilidade.md``.

Explica o impacto por ativo e por modelo, separa a taxa OBSERVADA das premissas de CENÁRIO e
traz a rastreabilidade do cálculo (versões, parâmetros, hash dos cenários, taxa-base com data
de referência e de coleta, data dos insumos). É sensibilidade das premissas: não é ordem de
compra ou venda, e não altera aporte nem peso-alvo.
"""

from __future__ import annotations

from pathlib import Path

from iip.macro.scenarios import Scenario, ScenarioSet
from iip.macro.sensitivity import (
    AssetSensitivity,
    MethodValue,
    SensitivityResult,
)
from iip.obsidian.frontmatter import flow_line

REPORT_RELATIVE_PATH = Path("07_Research") / "Macro" / "Sensibilidade.md"


def _pp(value: float) -> str:
    return f"{value:+.2f}".replace(".", ",") + " p.p."


def _num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cell(base: MethodValue, other: MethodValue) -> str:
    if other.fair_value is None:
        return "sem valor"
    text = _num(other.fair_value)
    if base.fair_value:
        delta = (other.fair_value / base.fair_value - 1) * 100
        text += f" ({delta:+.0f}%)"
    if other.margin is not None:
        text += f" · margem {other.margin * 100:+.0f}%"
    return text


def _sign_flips(asset: AssetSensitivity, index: int) -> list[str]:
    base_margin = asset.base[index].margin
    if base_margin is None:
        return []
    return [
        out.scenario_id
        for out in asset.scenarios
        if out.methods[index].margin is not None
        and (out.methods[index].margin > 0) != (base_margin > 0)
    ]


def _frontmatter(result: SensitivityResult) -> list[str]:
    rate = result.base_rate
    return [
        "---",
        "type: macro_sensitivity",
        f"date: {result.today}",
        flow_line("modelo_versao", result.model_version),
        flow_line("cenarios_versao", result.scenario_version),
        flow_line("cenarios_hash", result.scenario_hash),
        flow_line("insumos_data", result.inputs_run_date),
        flow_line(
            "taxa_base",
            (
                None
                if rate is None
                else {
                    "real": rate.real_yield,
                    "referencia": rate.reference_date,
                    "vencimento": rate.maturity,
                    "fonte": rate.source,
                }
            ),
        ),
        flow_line("avisos", list(result.warnings)),
        "---",
    ]


def render_sensitivity_report(
    result: SensitivityResult, scenario_set: ScenarioSet
) -> str:
    by_id = {s.id: s for s in scenario_set.scenarios}
    sensitive = [a for a in result.assets if a.sensitive_methods]
    insensitive = [a for a in result.assets if not a.sensitive_methods]
    lines = [
        *_frontmatter(result),
        "",
        "# Sensibilidade dos valuations a cenários de juros e inflação",
        "",
        "É **sensibilidade das premissas**, não previsão nem recomendação: mostra o que o "
        "Bazin e o Yield diriam se a taxa real de referência fosse outra. **Não altera aporte, "
        "peso-alvo nem rebalanceamento**, e não substitui a análise fundamentalista nem a "
        "aprovação humana.",
        "",
        f"{len(result.assets)} ativos reavaliados; **{len(sensitive)} sensíveis** a estes "
        f"cenários, {len(insensitive)} não (nenhum método deles usa a taxa).",
        "",
    ]
    if result.warnings:
        lines += ["## Avisos", ""]
        lines += [f"- {w}" for w in result.warnings]
        lines.append("")

    lines += ["## Taxa observada (a base)", ""]
    rate = result.base_rate
    if rate is None:
        lines += ["Sem taxa-base nesta rodada.", ""]
    else:
        lines += [
            f"- **{rate.title}**, vencimento mais longo ({rate.maturity}): "
            f"**IPCA + {rate.real_yield:.2%}** (taxa REAL, sobre o IPCA).",
            f"- Referência: **{rate.reference_date}**. Fonte: {rate.source}.",
        ]
        if result.stored_observation:
            o = result.stored_observation
            lines.append(
                f"- No armazenamento macro: {o.value_pct:.2f}% (ref. {o.reference}), "
                f"**coletada em {o.collected_at}** ({o.note})."
            )
        lines += [
            "- Os insumos dos modelos (preço, dividendo, LPA, VPA, NAV) são da rodada de "
            f"**{result.inputs_run_date}**.",
            "",
        ]

    lines += [
        "## Cenários (premissas, não observações)",
        "",
        f"Versão **{result.scenario_version}**, hash `{result.scenario_hash}`. "
        f"Origem: {result.scenario_origin}. Arquivo: `07_Research/Macro/cenarios.json` "
        "(edite lá; cada resultado carrega o hash do que foi usado).",
        "",
        f"Regra de transmissão ({result.transmission}).",
        "",
        "| Cenário | Juros nominais | Inflação esperada | Taxa real direta | Deslocamento da taxa real | Taxa real do cenário |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for scenario_id, name, shift in result.scenarios:
        s: Scenario = by_id[scenario_id]
        scenario_rate = (
            "—" if rate is None else f"IPCA + {rate.real_yield + shift / 100:.2%}"
        )
        lines.append(
            f"| {name} (`{scenario_id}`) | {_pp(s.nominal_rate_shock_pp)} | "
            f"{_pp(s.inflation_shock_pp)} | {_pp(s.real_yield_shock_pp)} | {_pp(shift)} | "
            f"{scenario_rate} |"
        )

    lines += ["", "## Impacto por ativo e por modelo", ""]
    if not sensitive:
        lines.append("Nenhum ativo é sensível a estes cenários.")
    header = (
        "| Ativo | Modelo | Base (valor · margem) | "
        + " | ".join(f"`{sid}`" for sid, _, _ in result.scenarios)
        + " | Margem muda de sinal em |"
    )
    separator = "|---|---|---|" + "---|" * len(result.scenarios) + "---|"
    if sensitive:
        lines += [header, separator]
    for asset in sensitive:
        for index, base in enumerate(asset.base):
            if base.method not in asset.sensitive_methods:
                continue
            base_cell = (
                f"{_num(base.fair_value)} · margem {base.margin * 100:+.0f}%"
                if base.fair_value is not None and base.margin is not None
                else (
                    _num(base.fair_value)
                    if base.fair_value is not None
                    else "sem valor"
                )
            )
            cells = " | ".join(
                _cell(base, out.methods[index]) for out in asset.scenarios
            )
            flips = ", ".join(_sign_flips(asset, index)) or "—"
            lines.append(
                f"| {asset.ticker} ({asset.asset_class}) | {base.method} | {base_cell} | "
                f"{cells} | {flips} |"
            )

    with_inert = [a for a in result.assets if a.insensitive_methods]
    if with_inert:
        lines += ["", "## Métodos que não reagem à taxa", ""]
        lines.append(
            "Nenhum destes métodos usa a taxa real da NTN-B (Graham, NAV, transparência): o "
            "valor justo é o mesmo em todos os cenários. Um ativo cujos métodos todos estão "
            "aqui é insensível a estes cenários."
        )
        lines.append("")
        lines += [
            f"- **{a.ticker}**: {', '.join(a.insensitive_methods)}"
            + ("" if a.sensitive_methods else " (ativo inteiramente insensível)")
            for a in with_inert
        ]
    notes = [a for a in result.assets if a.note]
    if notes:
        lines += [""]
        lines += [f"- **{a.ticker}**: {a.note}." for a in notes]

    lines += [
        "",
        "## Rastreabilidade",
        "",
        f"- **Modelo de sensibilidade:** `{result.model_version}`. Reavalia com "
        "`evaluate_valuations`, o mesmo avaliador do `value-portfolio`; a única entrada que "
        "muda entre cenários é `ntnb_real_yield`.",
        "- **Parâmetros dos modelos de valuation:** "
        + ", ".join(f"`{k}`={v}" for k, v in result.model_parameters.items())
        + ".",
        f"- **Cenários:** versão `{result.scenario_version}`, hash `{result.scenario_hash}`.",
        f"- **Insumos:** rodada de {result.inputs_run_date} (`07_Research/Macro/insumos_valuation.json`).",
        "- **Indicador macro usado no cálculo:** só a taxa real da NTN-B longa "
        "(`ntnb_longa_real`). Selic, IPCA e os demais indicadores do contexto macro NÃO "
        "entram nas contas.",
        f"- **Calculado em:** {result.today}.",
        "",
        "## O que esta sensibilidade não faz",
        "",
        "- Não prevê juros nem inflação: os choques são hipóteses do arquivo de cenários.",
        "- Não muda o dividendo nem o lucro: o Bazin trata o dividendo como já protegido da "
        "inflação, e o Yield capitaliza a renda de 12 meses. Só o retorno exigido se move.",
        "- **Real e nominal não se misturam:** a taxa da base é real (IPCA + x%); os choques de "
        "juros são nominais e entram pela regra de transmissão acima.",
        "- Nenhum aporte, peso-alvo ou rebalanceamento é sugerido, calculado ou alterado aqui.",
    ]
    return "\n".join(lines) + "\n"


def write_sensitivity_report(
    vault_path: Path | str, result: SensitivityResult, scenario_set: ScenarioSet
) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sensitivity_report(result, scenario_set), encoding="utf-8")
    return path
