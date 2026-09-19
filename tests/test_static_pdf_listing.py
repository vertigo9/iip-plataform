import pytest

from iip.sources.static_pdf_listing import (
    STATIC_PDF_LISTING_FUNDS,
    build_target,
    fund_for_ticker,
    parse_pdf_links,
)


def test_fund_for_ticker_is_case_insensitive():
    fund = fund_for_ticker("trxf11")
    assert fund is not None
    assert fund.ticker == "TRXF11"
    assert fund.manager == "TRX"


def test_fund_for_ticker_unknown_returns_none():
    assert fund_for_ticker("XPML11") is None


def test_all_seven_funds_and_the_isae4_cmig4_companies_registered():
    assert set(STATIC_PDF_LISTING_FUNDS) == {
        "TRXF11", "VGIP11", "CPTI11", "MANA11", "RBVA11", "HGBS11", "KNRI11", "ISAE4", "CMIG4",
    }


def test_build_target_uses_fund_page_url():
    target = build_target("KNRI11")
    fund = fund_for_ticker("KNRI11")
    assert target.url == fund.page_url
    assert target.ticker == "KNRI11"


def test_build_target_raises_for_unregistered_ticker():
    with pytest.raises(ValueError, match="XPML11"):
        build_target("XPML11")


def test_parse_pdf_links_extracts_and_dedupes():
    html = """
    <a href="https://example.com/wp-content/uploads/Relatorio-Gerencial-Agosto-2026.pdf">Download</a>
    <a href="https://example.com/wp-content/uploads/Relatorio-Gerencial-Agosto-2026.pdf">Baixar de novo</a>
    <a href="/relatorios/Fato_Relevante_2026.pdf">Fato relevante</a>
    <a href="https://example.com/pagina-sem-pdf">Não é PDF</a>
    """
    docs = parse_pdf_links(html, "https://example.com/fundo/", "TICK11")

    assert len(docs) == 2
    assert docs[0].ticker == "TICK11"
    assert docs[0].url == "https://example.com/wp-content/uploads/Relatorio-Gerencial-Agosto-2026.pdf"
    assert docs[0].title == "Relatorio Gerencial Agosto 2026"
    assert docs[1].url == "https://example.com/relatorios/Fato_Relevante_2026.pdf"
    assert docs[1].title == "Fato Relevante 2026"


def test_parse_pdf_links_resolves_relative_urls_against_base():
    html = '<a href="/docs/report.pdf">Relatório</a>'
    docs = parse_pdf_links(html, "https://fundo.com.br/pagina/", "TICK11")

    assert docs[0].url == "https://fundo.com.br/docs/report.pdf"


def test_parse_pdf_links_empty_when_no_pdf_links():
    docs = parse_pdf_links("<html><body>nada aqui</body></html>", "https://example.com", "TICK11")
    assert docs == ()


def test_parse_pdf_links_percent_encodes_non_ascii_hrefs():
    # Confirmed live on HGBS11's own page: raw, un-escaped accented
    # characters in an href break urllib's request line unless encoded.
    html = '<a href="/arquivos/HGBS_Laudo_São_Bernardo.pdf">Laudo</a>'
    docs = parse_pdf_links(html, "https://hedgeinvest.com.br/fundos/hgbs", "HGBS11")

    assert len(docs) == 1
    assert docs[0].url == "https://hedgeinvest.com.br/arquivos/HGBS_Laudo_S%C3%A3o_Bernardo.pdf"
    # Title stays human-readable (derived before percent-encoding).
    assert docs[0].title == "HGBS Laudo São Bernardo"


def test_parse_pdf_links_does_not_double_encode_existing_percent_sequences():
    html = '<a href="/docs/Relat%C3%B3rio%20Final.pdf">Relatório</a>'
    docs = parse_pdf_links(html, "https://fundo.com.br/", "TICK11")

    assert docs[0].url == "https://fundo.com.br/docs/Relat%C3%B3rio%20Final.pdf"
