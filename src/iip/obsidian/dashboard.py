"""Módulo gerador do Dashboard Consolidado do Portfolio no Obsidian.

Redirecionado (17/09/2026) para o vault real usado pelo
``KnowledgeBridge``/``AssetE2ERunner`` (``vault/01_Assets/<Categoria>/
<TICKER>/<TICKER> - Score e Ranking.md``) -- a versão anterior deste
gerador apontava para um layout legado (``01 - Portfolio/Assets/
{TICKER}.md``, do vault de demonstração já removido) que nunca
foi escrito pelo pipeline real, então o dashboard sempre mostrava
"N/A" em tudo.

Os blocos DataviewJS abaixo só conseguem ler campos de frontmatter
(YAML), nunca o texto das seções ``IIP:BEGIN/END`` -- por isso
``KnowledgeBridge.sync_valuation_projection`` /
``sync_quantitative_projection`` / ``sync_cross_asset_projection`` /
``sync_analysis_projection`` também escrevem esses mesmos campos como
frontmatter na nota "Score e Ranking" de cada ativo (ver
``iip.knowledge.bridge``). Um ativo só aparece numa linha se o campo
usado no filtro (``stages_ok``, ``margin_of_safety``,
``concentration_breaches``) já tiver sido escrito por uma rodada real
do ``AssetE2ERunner`` -- nada aqui é calculado ou aproximado pelo
próprio dashboard.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# The valuation note (``iip.obsidian.valuation_report``) carries its highlights in its
# YAML frontmatter -- the only thing the dashboard's DataviewJS can read -- under these
# keys. Defined once here and imported by the report so the two can never drift apart.
VALUATION_NOTE_DV_PATH = "02_Portfolio/Valuation"
VALUATION_NOTE_LINK = "[[Valuation|Valuation da Carteira]]"
HIGHLIGHTS_TOP_KEY = "destaques_maiores_margens"
HIGHLIGHTS_BOTTOM_KEY = "destaques_menores_margens"

# The notes of the follow-up layer (decisions, exposure, income, series). Same rule as the
# valuation note: the dashboard reads their YAML frontmatter with DataviewJS, so the paths and
# the keys are defined once, here, and imported by each report.
DECISIONS_NOTE_DV_PATH = "02_Portfolio/Decisoes"
EXPOSURE_NOTE_DV_PATH = "02_Portfolio/Exposicao"
INCOME_NOTE_DV_PATH = "02_Portfolio/Renda"
SERIES_NOTE_DV_PATH = "02_Portfolio/Series"

DECISIONS_SUMMARY_KEY = "resumo_decisoes"
DECISIONS_CHANGES_KEY = "mudancas"
EXPOSURE_FLAGS_KEY = "alertas_concentracao"
EXPOSURE_STALE_KEY = "snapshot_defasado"
EXPOSURE_AGE_KEY = "snapshot_dias"
EXPOSURE_DATE_KEY = "snapshot_data"
EXPOSURE_MISSING_KEY = "fora_do_snapshot"
INCOME_MONTHLY_KEY = "renda_mensal"
INCOME_COVERAGE_KEY = "cobertura_valor"
INCOME_EXCLUDED_KEY = "sem_projecao"
SERIES_PROBLEMS_KEY = "problemas"
SERIES_TOTAL_KEY = "series_total"


def _missing(note_dv_path: str, command: str) -> str:
    return (
        f'    dv.paragraph("Nota ainda não gerada, ou gerada por uma versão anterior sem os '
        f'campos do painel: rode `{command}` (ou espere o job diário). Caminho: {note_dv_path}.");'
    )


def _tracking_section() -> list[str]:
    """The "Acompanhamento da carteira" blocks: one per follow-up note, each reading only
    that note's frontmatter and saying so when the note does not exist yet."""
    return [
        "## 🧭 Acompanhamento da Carteira",
        "",
        "Cada bloco lê o cabeçalho de uma nota gerada pelo job diário; nada é recalculado "
        "aqui. Uma nota que ainda não existe aparece como aviso, não como tabela vazia.",
        "",
        "### Decisões",
        "",
        "Nota completa: [[Decisoes|Decisões da carteira]]. Gerada por "
        "`iip decide-portfolio --report`. A decisão é uma proposta para aprovação, não uma ordem.",
        "",
        "```dataviewjs",
        f'const p = dv.page("{DECISIONS_NOTE_DV_PATH}");',
        f"if (!p || p.{DECISIONS_SUMMARY_KEY} === undefined) {{",
        _missing(DECISIONS_NOTE_DV_PATH, "iip decide-portfolio --report"),
        "} else {",
        f"    const r = p.{DECISIONS_SUMMARY_KEY} || {{}};",
        '    const resumo = Object.keys(r).map(k => r[k] + " " + k).join(", ");',
        '    dv.paragraph("Decisões de " + String(p.date).slice(0, 10) + ": " + (resumo || "nenhuma") + ".");',
        f"    const ch = Array.from(p.{DECISIONS_CHANGES_KEY} || []);",
        "    if (ch.length) {",
        '        dv.table(["Ativo", "Antes", "Agora", "Sentido"], ch.map(x => [x.ticker, x.de, x.para, x.sentido]));',
        "    } else {",
        '        dv.paragraph("Nenhuma decisão mudou desde a anterior.");',
        "    }",
        "}",
        "```",
        "",
        "### Exposição e concentração",
        "",
        "Nota completa: [[Exposicao|Exposição da carteira]]. Gerada por "
        "`iip portfolio-exposure --report`.",
        "",
        "```dataviewjs",
        f'const p = dv.page("{EXPOSURE_NOTE_DV_PATH}");',
        f"if (!p || p.{EXPOSURE_AGE_KEY} === undefined) {{",
        _missing(EXPOSURE_NOTE_DV_PATH, "iip portfolio-exposure --report"),
        "} else {",
        f'    let txt = "Snapshot de " + String(p.{EXPOSURE_DATE_KEY}).slice(0, 10) + " (" + p.{EXPOSURE_AGE_KEY} + " dias).";',
        f'    if (p.{EXPOSURE_STALE_KEY}) txt += " **Defasado**: os pesos já andaram com os preços.";',
        "    dv.paragraph(txt);",
        f"    const miss = Array.from(p.{EXPOSURE_MISSING_KEY} || []);",
        '    if (miss.length) dv.paragraph("Fora do snapshot: " + miss.join(", ") + " (carteira incompleta).");',
        f"    const fl = Array.from(p.{EXPOSURE_FLAGS_KEY} || []);",
        "    if (fl.length) {",
        '        dv.table(["Tipo", "Visão", "Grupo", "Peso"], fl.map(x => [x.tipo, x.dimensao, x.grupo, (Number(x.peso) * 100).toFixed(1) + "%"]));',
        "    } else {",
        '        dv.paragraph("Nenhum grupo ou posição acima dos limites de atenção.");',
        "    }",
        "}",
        "```",
        "",
        "### Renda projetada",
        "",
        "Nota completa: [[Renda|Renda projetada]]. Gerada por `iip portfolio-income --report`. "
        "Renda bruta estimada, não promessa.",
        "",
        "```dataviewjs",
        f'const p = dv.page("{INCOME_NOTE_DV_PATH}");',
        f"if (!p || p.{INCOME_MONTHLY_KEY} === undefined) {{",
        _missing(INCOME_NOTE_DV_PATH, "iip portfolio-income --report"),
        "} else {",
        f'    dv.paragraph("R$ " + Number(p.{INCOME_MONTHLY_KEY}).toFixed(2) + " por mês, cobrindo " + (Number(p.{INCOME_COVERAGE_KEY}) * 100).toFixed(1) + "% do valor da carteira.");',
        f"    const ex = Array.from(p.{INCOME_EXCLUDED_KEY} || []);",
        "    if (ex.length) {",
        '        dv.paragraph("Fundos com série, mas sem projeção confiável:");',
        '        dv.table(["Fundo", "Situação"], ex.map(x => [x.ticker, x.situacao]));',
        "    }",
        "}",
        "```",
        "",
        "### Séries mensais da CVM",
        "",
        "Nota completa: [[Series|Séries mensais da CVM]]. Atualizada por "
        "`iip collect-fii-history`. São elas que alimentam a renda projetada.",
        "",
        "```dataviewjs",
        f'const p = dv.page("{SERIES_NOTE_DV_PATH}");',
        f"if (!p || p.{SERIES_TOTAL_KEY} === undefined) {{",
        _missing(SERIES_NOTE_DV_PATH, "iip collect-fii-history --report"),
        "} else {",
        f"    const pr = Array.from(p.{SERIES_PROBLEMS_KEY} || []);",
        f'    dv.paragraph(p.{SERIES_TOTAL_KEY} + " séries, " + pr.length + " com problema (dados de " + String(p.date).slice(0, 10) + ").");',
        "    if (pr.length) {",
        '        dv.table(["Fundo", "Situação", "Última competência", "Defasada", "Atualizada em"], pr.map(x => [x.ticker, x.situacao, x.ultima_competencia || "—", x.defasada ? "sim" : "não", x.atualizada_em || "nunca"]));',
        "    }",
        "}",
        "```",
        "",
        "---",
        "",
    ]


DASHBOARD_TEMPLATE = "\n".join(
    [
        "---",
        "type: dashboard",
        "updated_by: IIP Engine",
        "tags:",
        "  - iip/dashboard",
        "  - iip/portfolio",
        "---",
        "",
        "# 📊 Dashboard Consolidado — IIP",
        "",
        "<!-- IIP:BEGIN:METRICS_SUMMARY -->",
        "> [!info] Status do Sistema",
        "> Cada tabela abaixo lê o frontmatter que `AssetE2ERunner` grava na nota "
        '"Score e Ranking" de cada ativo ao rodar as 5 etapas (coleta, análise '
        "fundamentalista, valuation, quantitativo, cross-asset). Um ativo sem "
        "nenhuma rodada ainda não aparece em nenhuma tabela.",
        "<!-- IIP:END:METRICS_SUMMARY -->",
        "",
        "---",
        "",
        "## 🔎 Valuation da Carteira — Destaques",
        "",
        f"Nota completa, com todos os métodos por ativo: {VALUATION_NOTE_LINK}. "
        "Gerada por `iip value-portfolio --report`.",
        "",
        "```dataviewjs",
        f'const p = dv.page("{VALUATION_NOTE_DV_PATH}");',
        "if (!p) {",
        '    dv.paragraph("Nota de valuation ainda não gerada: rode `iip value-portfolio --report`.");',
        "} else {",
        '    const fmt = (m) => (Number(m) * 100).toFixed(0) + "%";',
        "    const rows = (list) => Array.from(list || []).map(x => [",
        "        x.ticker, x.classe, x.metodo, x.preco, x.valor, fmt(x.margem)",
        "    ]);",
        '    const head = ["Ativo", "Classe", "Método", "Preço", "Valor", "Margem de segurança"];',
        '    dv.paragraph("Dados de " + String(p.as_of).slice(0, 10) + ". Margens de métodos diferentes '
        'não são diretamente comparáveis: veja a coluna Método.");',
        '    dv.header(3, "Maiores margens de segurança");',
        f"    dv.table(head, rows(p.{HIGHLIGHTS_TOP_KEY}));",
        '    dv.header(3, "Menores margens de segurança");',
        f"    dv.table(head, rows(p.{HIGHLIGHTS_BOTTOM_KEY}));",
        "}",
        "```",
        "",
        "---",
        "",
        *_tracking_section(),
        "## 🟢 Status do Pipeline por Ativo",
        "",
        "```dataviewjs",
        "const pages = dv.pages('\"01_Assets\"')",
        "    .where(p => p.stages_ok !== undefined);",
        "",
        "const tableData = pages",
        "    .sort(p => p.stages_ok, 'asc')",
        "    .map(p => [",
        "        p.file.link,",
        '        p.asset_class || "N/A",',
        '        (p.stages_ok !== undefined ? p.stages_ok : "?") + "/5",',
        '        p.score !== undefined ? p.score : "N/A",',
        '        p.recommendation || "N/A",',
        '        p.risk || "N/A",',
        '        p.as_of || "N/A"',
        "    ]);",
        "",
        'dv.table(["Ativo", "Classe", "Estágios OK", "Score", "Recomendação", "Risco", "Atualizado em"], tableData);',
        "```",
        "",
        "---",
        "",
        "## 💰 Valuation — Margem de Segurança",
        "",
        "```dataviewjs",
        "const pages = dv.pages('\"01_Assets\"')",
        "    .where(p => p.margin_of_safety !== undefined);",
        "",
        "const tableData = pages",
        "    .sort(p => p.margin_of_safety, 'desc')",
        "    .map(p => [",
        "        p.file.link,",
        '        p.valuation_method || "N/A",',
        '        p.fair_value !== undefined ? p.fair_value : "N/A",',
        '        p.market_price !== undefined ? p.market_price : "N/A",',
        '        p.margin_of_safety !== undefined ? (Number(p.margin_of_safety) * 100).toFixed(1) + "%" : "N/A"',
        "    ]);",
        "",
        'dv.table(["Ativo", "Método", "Valor Justo", "Preço de Mercado", "Margem de Segurança"], tableData);',
        "```",
        "",
        "---",
        "",
        "## 📈 Qualidade Quantitativa (Volatilidade / Retorno)",
        "",
        "```dataviewjs",
        "const pages = dv.pages('\"01_Assets\"')",
        "    .where(p => p.quantitative_observations !== undefined);",
        "",
        "const tableData = pages",
        "    .sort(p => p.return_volatility, 'desc')",
        "    .map(p => [",
        "        p.file.link,",
        '        p.quantitative_observations !== undefined ? p.quantitative_observations : "N/A",',
        '        p.total_return !== undefined ? (Number(p.total_return) * 100).toFixed(1) + "%" : "N/A",',
        '        p.return_volatility !== undefined ? (Number(p.return_volatility) * 100).toFixed(2) + "%" : "N/A"',
        "    ]);",
        "",
        'dv.table(["Ativo", "Observações", "Retorno Total", "Volatilidade do Retorno"], tableData);',
        "```",
        "",
        "---",
        "",
        "## ⚠️ Alertas de Concentração",
        "",
        "```dataviewjs",
        "const pages = dv.pages('\"01_Assets\"')",
        "    .where(p => p.concentration_breaches !== undefined && Number(p.concentration_breaches) > 0);",
        "",
        "const tableData = pages.map(p => [",
        "    p.file.link,",
        '    p.asset_class || "N/A",',
        "    p.concentration_breaches",
        "]);",
        "",
        "if (tableData.length > 0) {",
        '    dv.table(["Ativo", "Classe", "Dimensões de Concentração Excedidas"], tableData);',
        "} else {",
        '    dv.paragraph("Nenhuma concentração acima do limite nas últimas rodadas.");',
        "}",
        "```",
        "",
    ]
)


def generate_portfolio_dashboard(vault_path: Path | str) -> Path:
    """Gera ou atualiza de forma idempotente a nota de Dashboard no Obsidian Vault."""
    vault = Path(vault_path)
    dashboard_path = vault / "02_Portfolio" / "Dashboard.md"

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(DASHBOARD_TEMPLATE, encoding="utf-8")
    logger.info("Dashboard consolidado gerado com sucesso em: %s", dashboard_path)
    return dashboard_path
