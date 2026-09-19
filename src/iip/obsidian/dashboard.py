"""Módulo gerador do Dashboard Consolidado do Portfolio no Obsidian.

Redirecionado (17/09/2026) para o vault real usado pelo
``KnowledgeBridge``/``AssetE2ERunner`` (``vault/01_Assets/<Categoria>/
<TICKER>/<TICKER> - Score e Ranking.md``) -- a versão anterior deste
gerador apontava para um layout legado (``01 - Portfolio/Assets/
{TICKER}.md``, vault de demonstração ``MeuVaultFinanceiro``) que nunca
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

DASHBOARD_TEMPLATE = "\n".join([
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
    "## 🟢 Status do Pipeline por Ativo",
    "",
    "```dataviewjs",
    'const pages = dv.pages(\'"01_Assets"\')',
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
    'const pages = dv.pages(\'"01_Assets"\')',
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
    'const pages = dv.pages(\'"01_Assets"\')',
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
    'const pages = dv.pages(\'"01_Assets"\')',
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
])


def generate_portfolio_dashboard(vault_path: Path | str) -> Path:
    """Gera ou atualiza de forma idempotente a nota de Dashboard no Obsidian Vault."""
    vault = Path(vault_path)
    dashboard_path = vault / "02_Portfolio" / "Dashboard.md"

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(DASHBOARD_TEMPLATE, encoding="utf-8")
    logger.info("Dashboard consolidado gerado com sucesso em: %s", dashboard_path)
    return dashboard_path
