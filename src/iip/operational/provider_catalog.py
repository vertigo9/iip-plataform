"""Real-source catalog derived from the IIP portfolio source map."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEntry:
    provider: str
    source_kind: str
    source_url: str | None
    status: str


SOURCE_ENTRIES = (
    SourceEntry(
        "xp_asset",
        "institutional_primary",
        "https://xpasset.com.br/fundos/xp-malls",
        "validated",
    ),
    SourceEntry(
        "patria",
        "institutional_primary",
        "https://realestate.patria.com/tijolo/hgru",
        "validated",
    ),
    SourceEntry(
        "sparta",
        "institutional_primary",
        "https://sparta.com.br/sparta-cdii11",
        "mapped",
    ),
    SourceEntry(
        "capitania",
        "institutional_primary",
        "https://capitaniainfra.com.br/cpti11",
        "mapped",
    ),
    SourceEntry(
        "valora",
        "institutional_primary",
        "https://valorainvest.com.br/fundo/vgip11",
        "mapped",
    ),
    SourceEntry(
        "btg",
        "institutional_primary",
        "https://btgpactual.com/asset-management/.../BTCI11",
        "mapped",
    ),
    SourceEntry(
        "manati", "institutional_primary", "https://manaticm.com/fundo/mana11", "mapped"
    ),
    SourceEntry(
        "trx",
        "institutional_primary",
        "https://trxf11.com.br/relatorios-gerenciais-2",
        "mapped",
    ),
    SourceEntry("araujo_fontes", "institutional_primary", None, "mapped"),
    SourceEntry(
        "hedge",
        "institutional_primary",
        "https://hedgeinvest.com.br/fundos/hgbs",
        "mapped",
    ),
    SourceEntry(
        "rio_bravo", "institutional_primary", "https://riobravo.com.br/rbva11", "mapped"
    ),
    SourceEntry(
        "kinea",
        "institutional_primary",
        "https://kinea.com.br/fundos/.../knri11",
        "mapped",
    ),
)


def source_entry(provider: str) -> SourceEntry | None:
    target = provider.strip().lower()
    return next((item for item in SOURCE_ENTRIES if item.provider == target), None)
