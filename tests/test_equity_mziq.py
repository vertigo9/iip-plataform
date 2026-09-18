import pytest

from iip.sources.equity_mziq import (
    EQUITY_MZIQ_COMPANIES,
    build_documents_target,
    build_years_target,
    company_for_ticker,
    fund_for_ticker,
)


def test_company_for_ticker_is_case_insensitive():
    company = company_for_ticker("abcb4")
    assert company is not None
    assert company.ticker == "ABCB4"
    assert company.company_id == "6298ef6f-2b75-43f8-b2ab-99e3fe33e809"


def test_company_for_ticker_unknown_returns_none():
    assert company_for_ticker("CMIG4") is None


def test_fund_for_ticker_alias_matches_company_for_ticker():
    assert fund_for_ticker("ABCB4") == company_for_ticker("ABCB4")


def test_ten_confirmed_companies_registered():
    assert set(EQUITY_MZIQ_COMPANIES) == {
        "ABCB4", "BBSE3", "CXSE3", "SAUD3", "ALOS3",
        "VBBR3", "KLBN4", "FESA4", "LEVE3", "PASS3",
    }


def test_not_mziq_companies_are_not_registered():
    # Confirmed NOT MZIQ-hosted (18/09/2026) -- see module docstring.
    for ticker in ("ISAE4", "CPFE3", "CMIG4", "CSUD3"):
        assert company_for_ticker(ticker) is None


def test_build_years_target_uses_company_id_and_categories():
    target = build_years_target("ABCB4")
    company = company_for_ticker("ABCB4")
    assert company.company_id in target.url
    assert target.body["categoryInternalNames"] == list(company.category_internal_names)


def test_build_documents_target_includes_year():
    target = build_documents_target("ABCB4", 2026)
    assert target.body["year"] == "2026"


def test_build_years_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="CMIG4"):
        build_years_target("CMIG4")


def test_build_documents_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="CMIG4"):
        build_documents_target("CMIG4", 2026)
