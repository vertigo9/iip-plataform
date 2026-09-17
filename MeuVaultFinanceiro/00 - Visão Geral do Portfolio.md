---
type: dashboard
updated_by: IIP Engine
tags:
  - iip/dashboard
  - iip/portfolio
---

# 📊 Visão Geral do Portfolio — IIP Engine

<!-- IIP:BEGIN:METRICS_SUMMARY -->
> [!info] Status do Sistema
> Painel atualizado pelo **DecisionEngine**. Cotações spot, taxas de câmbio, proventos e alertas de rebalanceamento são sincronizados automaticamente.
<!-- IIP:END:METRICS_SUMMARY -->

---

## 🟢 Matriz de Decisão e Vereditos Globais

```dataviewjs
const pages = dv.pages('"01 - Portfolio/Assets"')
    .where(p => p.file.name !== "00 - Visão Geral do Portfolio");

const tableData = pages.map(p => [
    p.file.link,
    p.asset_class || "N/A",
    p.score || "N/A",
    p.verdict || "AGUARDAR",
    p.currency || "BRL",
    p.spot_price_brl ? "R$ " + Number(p.spot_price_brl).toFixed(2) : "N/A",
    p.file.mtime.toFormat("dd/MM/yyyy HH:mm")
]);

dv.table(["Ativo", "Classe", "Score", "Veredito", "Moeda", "Preço (BRL)", "Atualização"], tableData);
```

---

## 💵 Exposição Cambial do Portfolio

```dataviewjs
const pages = dv.pages('"01 - Portfolio/Assets"');
const groups = pages.groupBy(p => p.currency || "BRL");

const summary = groups.map(g => {
    const total = g.rows.length;
    const pct = ((total / Math.max(pages.length, 1)) * 100).toFixed(1) + "%";
    return [g.key, total, pct];
});

dv.table(["Moeda Base", "Qtd. Ativos", "Participação Relativa"], summary);
```

---

## 💰 Projeção de Renda Passiva Mensal

```dataviewjs
const pages = dv.pages('"01 - Portfolio/Assets"');
const incomeData = pages.map(p => [
    p.file.link,
    p.dividend_yield_ttm ? (Number(p.dividend_yield_ttm) * 100).toFixed(2) + "%" : "N/A",
    p.monthly_payout_brl ? "R$ " + Number(p.monthly_payout_brl).toFixed(2) : "N/A",
    p.annual_payout_brl ? "R$ " + Number(p.annual_payout_brl).toFixed(2) : "N/A"
]);

dv.table(["Ativo", "DY TTM", "Est. Mensal (BRL)", "Est. Anual (BRL)"], incomeData);
```

---

## ⚠️ Alertas de Rebalanceamento & Desvios

```dataviewjs
const pages = dv.pages('"01 - Portfolio/Assets"');
const rebalanceData = pages
    .where(p => p.verdict === "REDUZIR" || p.verdict === "COMPRAR")
    .map(p => [
        p.file.link,
        p.asset_class || "N/A",
        p.verdict === "COMPRAR" ? "🎯 APORTAR" : "🔻 REDUZIR",
        p.score || "N/A"
    ]);

dv.table(["Ativo", "Classe", "Ação Sugerida", "Score"], rebalanceData);
```
