"""Institutional source readiness records for the fund managers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstitutionalSourceRecord:
    provider: str
    source_url: str | None
    url_validated: bool
    requires_custom_adapter: bool
    status: str


# Deliberately conservative: URLs in the portfolio registry are useful source
# hints, but they are not treated as validated production endpoints until an
# actual adapter test proves the path and document behavior.
SOURCE_STATUS = {
    "xp_asset": "validated",
    "patria": "validated",
    "sparta": "mapped",
    "capitania": "mapped",
    "valora": "mapped",
    "btg": "mapped",
    "manati": "mapped",
    "trx": "mapped",
    "araujo_fontes": "mapped",
    "hedge": "mapped",
    "rio_bravo": "mapped",
    "kinea": "mapped",
}


def build_source_records() -> tuple[InstitutionalSourceRecord, ...]:
    return tuple(
        InstitutionalSourceRecord(
            provider=name,
            source_url=None,
            url_validated=(status == "validated"),
            requires_custom_adapter=(status != "validated"),
            status=status,
        )
        for name, status in sorted(SOURCE_STATUS.items())
    )
