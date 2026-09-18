import pytest

from iip.sources.patria_mziq import (
    PATRIA_MZIQ_FUNDS,
    build_documents_target,
    build_years_target,
    fund_for_ticker,
)


def test_fund_for_ticker_is_case_insensitive():
    fund = fund_for_ticker("lvbi11")
    assert fund is not None
    assert fund.ticker == "LVBI11"
    assert fund.company_id == "ef0151fe-a22e-456d-8cc4-55ef365d7e3b"


def test_fund_for_ticker_unknown_returns_none():
    assert fund_for_ticker("XPML11") is None


def test_all_five_patria_funds_registered():
    assert set(PATRIA_MZIQ_FUNDS) == {"HGRU11", "LVBI11", "HGCR11", "PVBI11", "PCIP11"}


def test_build_years_target_uses_fund_company_id_and_categories():
    target = build_years_target("PCIP11")
    fund = fund_for_ticker("PCIP11")
    assert fund.company_id in target.url
    assert target.body["categoryInternalNames"] == list(fund.category_internal_names)


def test_build_documents_target_includes_year():
    target = build_documents_target("HGRU11", 2026)
    assert target.body["year"] == "2026"


def test_build_years_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="XPML11"):
        build_years_target("XPML11")


def test_build_documents_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="XPML11"):
        build_documents_target("XPML11", 2026)
