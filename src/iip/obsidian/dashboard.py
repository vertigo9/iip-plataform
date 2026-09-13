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
    "> Painel atualizado pelo **DecisionEngine**. Cotações spot e taxas de câmbio são normalizadas automaticamente.",
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
    "const tableData = pages.map(p => [",
    "    p.file.link,",
    '    p.asset_class || "N/A",',
    '    p.score || "N/A",',
    '    p.verdict || "AGUARDAR",',
    '    p.currency || "BRL",',
    '    p.spot_price_brl ? "R$ " + Number(p.spot_price_brl).toFixed(2) : "N/A",',
    '    p.file.mtime.toFormat("dd/MM/yyyy HH:mm")',
    "]);",
    "",
    'dv.table(["Ativo", "Classe", "Score", "Veredito", "Moeda", "Preço (BRL)", "Atualização"], tableData);',
    "```",
    "",
    "---",
    "",
    "## 💵 Exposição Cambial do Portfolio",
    "",
    "```dataviewjs",
    'const pages = dv.pages(\'"01 - Portfolio/Assets"\');',
    'const groups = pages.groupBy(p => p.currency || "BRL");',
    "",
    "const summary = groups.map(g => {",
    "    const total = g.rows.length;",
    '    const pct = ((total / Math.max(pages.length, 1)) * 100).toFixed(1) + "%";',
    "    return [g.key, total, pct];",
    "});",
    "",
    'dv.table(["Moeda Base", "Qtd. Ativos", "Participação Relative"], summary);',
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