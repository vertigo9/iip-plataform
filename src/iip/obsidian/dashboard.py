"""Módulo gerador do Dashboard Consolidado do Portfolio no Obsidian."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DASHBOARD_TEMPLATE = "\n".join([
    "---",
    "type: dashboard",
    "updated_by: IIP Engine",
    "tags:",
    "  - iip/dashboard",
    "  - iip/portfolio",
    "---",
    "",
    "# 📊 Visão Geral do Portfolio — IIP Engine",
    "",
    "<!-- IIP:BEGIN:METRICS_SUMMARY -->",
    "> [!info] Status do Sistema",
    "> O painel abaixo é atualizado automaticamente pelo **DecisionEngine**. As métricas de FIIs, Ações, ETFs e Renda Fixa são extraídas dos delimitadores cirúrgicos em tempo real.",
    "<!-- IIP:END:METRICS_SUMMARY -->",
    "",
    "---",
    "",
    "## 🟢 Matriz de Decisão e Vereditos Globais",
    "",
    "```dataviewjs",
    'const pages = dv.pages(\'"01 - Portfolio/Assets"\')',
    '    .where(p => p.file.name !== "00 - Visão Geral do Portfolio");',
    "",
    "const tableData = pages.map(p => {",
    "    return [",
    "        p.file.link,",
    '        p.asset_class || "N/A",',
    '        p.score || "N/A",',
    '        p.verdict || "AGUARDAR",',
    '        p.confidence || "0.00",',
    '        p.file.mtime.toFormat("dd/MM/yyyy HH:mm")',
    "    ];",
    "});",
    "",
    'dv.table(["Ativo", "Classe", "Score", "Veredito", "Confiança", "Última Atualização"], tableData);',
    "```",
    "",
    "---",
    "",
    "## 📈 Resumo por Classe de Ativo",
    "",
    "```dataviewjs",
    'const pages = dv.pages(\'"01 - Portfolio/Assets"\');',
    'const groups = pages.groupBy(p => p.asset_class || "Outros");',
    "",
    "const summary = groups.map(g => {",
    "    const total = g.rows.length;",
    '    const comprar = g.rows.where(p => p.verdict === "COMPRAR").length;',
    '    const manter = g.rows.where(p => p.verdict === "MANTER").length;',
    '    const vender = g.rows.where(p => p.verdict === "VENDER").length;',
    "    return [g.key, total, comprar, manter, vender];",
    "});",
    "",
    'dv.table(["Classe de Ativo", "Total", "Comprar", "Manter", "Vender"], summary);',
    "```",
    "",
])


def generate_portfolio_dashboard(vault_path: Path | str) -> Path:
    """Gera ou atualiza de forma idempotente a nota de Dashboard no Obsidian Vault."""
    vault = Path(vault_path)
    dashboard_path = vault / "00 - Visão Geral do Portfolio.md"

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(DASHBOARD_TEMPLATE, encoding="utf-8")
    logger.info("Dashboard consolidado gerado com sucesso em: %s", dashboard_path)
    return dashboard_path