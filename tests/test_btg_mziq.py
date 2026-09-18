import pytest

from iip.sources.btg_mziq import (
    BTG_MZIQ_FUNDS,
    build_documents_target,
    build_years_target,
    fund_for_ticker,
)


def test_fund_for_ticker_is_case_insensitive():
    fund = fund_for_ticker("btlg11")
    assert fund is not None
    assert fund.ticker == "BTLG11"
    assert fund.company_id == "41be6346-c17f-47f5-88be-58b333a14261"


def test_fund_for_ticker_unknown_returns_none():
    assert fund_for_ticker("BTCI11") is None


def test_only_btlg11_registered():
    assert set(BTG_MZIQ_FUNDS) == {"BTLG11"}


def test_build_years_target_uses_fund_company_id_and_categories():
    target = build_years_target("BTLG11")
    fund = fund_for_ticker("BTLG11")
    assert fund.company_id in target.url
    assert target.body["categoryInternalNames"] == list(fund.category_internal_names)


def test_build_documents_target_includes_year():
    target = build_documents_target("BTLG11", 2026)
    assert target.body["year"] == "2026"


def test_build_years_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="BTCI11"):
        build_years_target("BTCI11")


def test_build_documents_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="BTCI11"):
        build_documents_target("BTCI11", 2026)
