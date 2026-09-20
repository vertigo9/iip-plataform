"""As exceções metodológicas de valuation como nota do vault: ``02_Portfolio/Excecoes_Valuation.md``.

Sobrescrita a cada execução. Lista cada exceção com o motivo, quem decidiu, a data de revisão e o
efeito HOJE sobre os métodos do ativo (com a classificação atual do registro), e sinaliza as
vencidas. Uma exceção vencida continua aplicada; nada é removido nem reativado sozinho. O motivo
é a premissa metodológica, não uma conclusão sobre o valor justo do ativo.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from iip.obsidian.frontmatter import flow_line
from iip.portfolio.registry import get_asset
from iip.portfolio_data.valuation import ValuationMethod
from iip.portfolio_data.valuation_exceptions import MethodException, ValuationExceptions
from iip.portfolio_data.valuation_methods import applicability, ordered_methods

REPORT_RELATIVE_PATH = Path("02_Portfolio") / "Excecoes_Valuation.md"


def effect_of(item: MethodException, exceptions: ValuationExceptions) -> str:
    """O que a exceção faz HOJE com os métodos do ativo, com a classificação do registro."""
    asset = get_asset(item.ticker, include_closed=True)
    if asset is None:
        return "ativo fora do registro"
    order = ordered_methods(
        asset.asset_class,
        asset.sector or "",
        asset.industry or "",
        ticker=item.ticker,
        exceptions=exceptions,
    )
    method = next((m for m in ValuationMethod if m.value == item.method), None)
    fit = applicability(
        method,
        asset.asset_class,
        asset.sector or "",
        asset.industry or "",
        ticker=item.ticker,
        exceptions=exceptions,
    )
    state = "aplicável" if fit.applicable else "excluído"
    # o líder é o primeiro método que de fato se aplica (um excluído não lidera)
    lead = next(
        (
            m.value
            for m in order
            if applicability(
                m,
                asset.asset_class,
                asset.sector or "",
                asset.industry or "",
                ticker=item.ticker,
                exceptions=exceptions,
            ).applicable
        ),
        "—",
    )
    return f"{item.method} {state}; método líder: {lead}"


def _status(item: MethodException, today: _dt.date) -> str:
    if item.overdue(today):
        return f"**VENCIDA** (revisão era até {item.review_by}); segue aplicada"
    return f"vigente (revisão até {item.review_by})"


def render_exceptions_report(exceptions: ValuationExceptions, today: _dt.date) -> str:
    overdue = exceptions.overdue(today)
    lines = [
        "---",
        "type: valuation_exceptions",
        f"date: {today.isoformat()}",
        f"excecoes_versao: {exceptions.version}",
        f"excecoes_hash: {exceptions.content_hash}",
        flow_line("excecoes", len(exceptions.items)),
        flow_line("excecoes_vencidas", [i.id for i in overdue]),
        "---",
        "",
        "# Exceções metodológicas de valuation",
        "",
        f"{len(exceptions.items)} exceção(ões), {len(overdue)} vencida(s) (versão "
        f"{exceptions.version}, hash `{exceptions.content_hash}`, dados de {today:%d/%m/%Y}).",
        "",
        "A classificação cadastral (setor, segmento) DESCREVE o ativo; o método de valuation "
        "apropriado é outra pergunta. Uma exceção declarada aqui **prevalece sobre as palavras-"
        "chave do setor** (que decidem o método líder e as exclusões) e fica citada no "
        "valuation, na decisão e na sensibilidade. O motivo é a premissa metodológica: não é "
        "conclusão sobre o valor justo nem recomendação, e o resultado recalculado é a "
        "consequência da regra aplicada.",
        "",
        "## Exceções",
        "",
    ]
    if exceptions.items:
        lines += [
            "| Id | Ativo | Método | Ação | Efeito hoje | Decidida | Situação |",
            "|---|---|---|---|---|---|---|",
        ]
        for item in exceptions.items:
            action = "exclui" if item.action == "exclude" else "lidera"
            lines.append(
                f"| `{item.id}` | `{item.ticker}` | {item.method} | {action} | "
                f"{effect_of(item, exceptions)} | {item.decided_on} por {item.decided_by} | "
                f"{_status(item, today)} |"
            )
        lines += ["", "### Motivos", ""]
        lines += [f"- **{i.id}**: {i.reason}." for i in exceptions.items]
    else:
        lines.append(
            "Nenhuma exceção declarada: valem só as regras por palavra-chave do setor."
        )
    lines += [
        "",
        "## Como funcionam",
        "",
        "- **Escopo:** só ações, nesta versão. No máximo uma exceção por (ativo, método) e um "
        "só método líder por ativo.",
        "- **`exclude`** tira o método da lista, citando a exceção; **`lead`** o coloca em "
        "primeiro, seja qual for a ordem do setor.",
        "- **Revisão obrigatória:** toda exceção tem `review_by`. Vencida, **continua "
        "aplicada** e é sinalizada; nada a remove nem a reativa automaticamente.",
        "- **Arquivo ausente** = sem exceções. **Arquivo inválido** (JSON, chave, método, data, "
        'ativo fora das ações) para o comando com o motivo, nunca vira "sem exceções" em '
        "silêncio.",
        "- Edite `02_Portfolio/Excecoes_Valuation.json` e rode "
        "`iip valuation-exceptions --report` para validar e atualizar esta nota.",
        "",
    ]
    return "\n".join(lines)


def write_exceptions_report(
    vault_path: str | Path, exceptions: ValuationExceptions, today: _dt.date
) -> Path:
    path = Path(vault_path) / REPORT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_exceptions_report(exceptions, today), encoding="utf-8")
    return path
