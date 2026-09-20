"""A exposição da carteira como nota do vault: ``02_Portfolio/Exposicao.md``.

Sobrescrita a cada execução, como ``Valuation.md`` e ``Decisoes.md``. Abre com o que limita
a leitura (idade do snapshot, posições fora dele), depois os alertas de concentração e uma
tabela por visão.
"""

from __future__ import annotations

from pathlib import Path

from iip.obsidian.dashboard import (
    EXPOSURE_AGE_KEY,
    EXPOSURE_DATE_KEY,
    EXPOSURE_FLAGS_KEY,
    EXPOSURE_MISSING_KEY,
    EXPOSURE_STALE_KEY,
)
from iip.obsidian.frontmatter import flow_line
from iip.portfolio.exposure import (
    LOW_COVERAGE,
    SEM_CLASSIFICACAO,
    STALE_AFTER_DAYS,
    DimensionExposure,
    ExposureReport,
)

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Exposicao.md"

_MAX_TICKERS = 8


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _tickers(tickers: tuple[str, ...]) -> str:
    if len(tickers) <= _MAX_TICKERS:
        return ", ".join(tickers)
    return ", ".join(tickers[:_MAX_TICKERS]) + f" e mais {len(tickers) - _MAX_TICKERS}"


def _table(dimension: DimensionExposure) -> list[str]:
    lines = [
        f"### {dimension.name}",
        "",
        f"Classificado: {dimension.classified_weight:.1%} da carteira.",
    ]
    if dimension.low_coverage:
        lines.append(
            f"**Cobertura baixa** (menos de {LOW_COVERAGE:.0%}): esta visão descreve pouco "
            "da carteira; o registro de ativos não classifica o resto."
        )
    lines += ["", "| Grupo | Peso | Valor | Posições |", "|---|---:|---:|---|"]
    lines += [
        f"| {row.label} | {row.weight:.1%} | {_brl(row.value)} | "
        f"{row.count}: {_tickers(row.tickers)} |"
        for row in dimension.rows
    ]
    return lines


def render_exposure_report(report: ExposureReport) -> str:
    lines = [
        "---",
        "type: portfolio_exposure",
        f"snapshot_date: {report.as_of.isoformat() if report.as_of else 'desconhecida'}",
        f"positions: {report.position_count}",
        f"flags: {len(report.flags)}",
        flow_line(
            EXPOSURE_DATE_KEY, report.as_of.isoformat() if report.as_of else None
        ),
        flow_line(EXPOSURE_AGE_KEY, report.age_days),
        flow_line(EXPOSURE_STALE_KEY, report.stale),
        flow_line(EXPOSURE_MISSING_KEY, list(report.missing_from_snapshot)),
        flow_line(
            EXPOSURE_FLAGS_KEY,
            [
                {
                    "tipo": f.kind,
                    "dimensao": f.dimension,
                    "grupo": f.label,
                    "peso": round(f.weight, 4),
                }
                for f in report.flags
            ],
        ),
        "---",
        "",
        "# Exposição e concentração da carteira",
        "",
        f"{report.position_count} posições, {_brl(report.total_value)}. Fonte: "
        "`02_Portfolio/Current.md` (Investidor10). A data abaixo é a do ARQUIVO, não a dos "
        "preços.",
        "",
    ]
    if report.as_of is not None:
        lines.append(
            f"- **Snapshot de {report.as_of:%d/%m/%Y}** ({report.age_days} dias)."
            + (
                f" **Defasado** (mais de {STALE_AFTER_DAYS} dias): os pesos já andaram com os "
                "preços desde então."
                if report.stale
                else ""
            )
        )
    else:
        lines.append("- Data do snapshot desconhecida.")
    if report.missing_from_snapshot:
        lines.append(
            "- **Fora do snapshot** (estão no registro de ativos): "
            + ", ".join(report.missing_from_snapshot)
            + ". A soma dos pesos abaixo é de uma carteira incompleta."
        )
    for closed_ticker, closed_on in report.closed_in_snapshot:
        lines.append(
            f"- **Posição de ativo encerrado voltou ao snapshot**: `{closed_ticker}` "
            f"(encerrado no registro em {closed_on}). O job diário não o atualiza, avalia nem "
            "decide até ele ser reativado (apagar `closed_on` em `portfolio/registry.py`)."
        )

    lines += ["", "## Alertas de concentração", ""]
    if report.flags:
        lines += [
            f"Limites de **atenção** (não são política de alocação): grupo de gestora ou "
            f"setor/segmento acima de {report.group_limit:.0%}, posição acima de "
            f"{report.position_limit:.0%}. A divisão por classe e por perfil de risco é "
            "alocação, não concentração: só é mostrada.",
            "",
        ]
        lines += [
            f"- {flag.kind.capitalize()} — {flag.dimension}: **{flag.label}** com "
            f"{flag.weight:.1%}"
            for flag in report.flags
        ]
    else:
        lines.append("Nenhum grupo ou posição acima dos limites de atenção.")

    lines += ["", "## Visões", ""]
    for dimension in report.dimensions:
        lines += _table(dimension) + [""]

    lines += [
        "## Como ler",
        "",
        "- O peso é o valor da posição sobre o valor total das posições do snapshot.",
        f"- `{SEM_CLASSIFICACAO}` é o que o registro de ativos não classifica (a renda fixa "
        "bancária não está no registro; ações não têm gestora nem perfil de risco no "
        "registro). Ele não é somado como concentração.",
        "- **Setor / segmento** mistura, de propósito, o setor das ações com o segmento dos "
        "fundos. O AXIA3 (fundo do FGTS, dono de ações de energia elétrica) aparece com o "
        "setor do registro dele, sem transparência: a exposição indireta a energia elétrica é "
        "maior que a mostrada.",
        "- Só descreve. Sem peso-alvo definido (regra do próprio snapshot), não há "
        "desvio a corrigir, só concentração a observar.",
    ]
    return "\n".join(lines) + "\n"


def write_exposure_report(vault_path: Path | str, report: ExposureReport) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_exposure_report(report), encoding="utf-8")
    return path
