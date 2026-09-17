const pages = dv.pages('"01 - Portfolio/Assets"');
const groups = pages.groupBy(p => p.asset_class || "Outros");

const summary = groups.map(g => {
    const total = g.rows.length;
    const comprar = g.rows.where(p => p.verdict === "COMPRAR").length;
    const manter = g.rows.where(p => p.verdict === "MANTER").length;
    const vender = g.rows.where(p => p.verdict === "VENDER").length;
    return [g.key, total, comprar, manter, vender];
});

dv.table(["Classe de Ativo", "Total", "Comprar", "Manter", "Vender"], summary);