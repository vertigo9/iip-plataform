import pytest


@pytest.fixture(autouse=True)
def _no_real_patria_planilha_download(monkeypatch):
    """``fetch_fii_template_live`` also tries a best-effort enrichment from
    Pátria's real "Planilha de Fundamentos" (MZIQ API + an XLSX download).
    Any test that goes through it for a Pátria ticker (the refresh/batch tests
    do) would otherwise hit the real network and parse a real workbook --
    minutes per run. Stubbed here for every test; the tests that exercise the
    enrichment itself replace the harvester class explicitly, which takes
    precedence over this."""
    from iip.sources.patria_planilha_fundamentos_harvester import (
        FetchedPlanilhaFundamentos,
        PatriaPlanilhaFundamentosHTTPHarvester,
    )

    def offline_fetch(self, ticker):
        return FetchedPlanilhaFundamentos(
            ticker=ticker.upper(), category="", document=None, fundamentos=None
        )

    monkeypatch.setattr(PatriaPlanilhaFundamentosHTTPHarvester, "fetch", offline_fetch)


@pytest.fixture(autouse=True)
def _no_real_ntnb_rate_in_fii_template(monkeypatch):
    """``fetch_fii_template_live`` asks for the long NTN-B rate (for the FII
    dividends pillar). Tests must not touch the network, and "no rate" is the
    neutral default (the pillar keeps its previous calibration). Tests that need
    a rate patch ``long_ntnb_rate_cached`` themselves, which takes precedence."""
    import iip.sources.tesouro_direto_harvester as harvester_module

    monkeypatch.setattr(harvester_module, "long_ntnb_rate_cached", lambda: None)


@pytest.fixture(autouse=True)
def _no_real_fii_vacancia_report_download(monkeypatch):
    """``fetch_fii_template_live`` also tries to read the vacancy from the
    manager's latest report PDF (TRXF11, BTLG11, HGBS11: a listing page or the
    MZIQ API plus a multi-MB PDF download). Tests must not touch the network, so
    the harvester finds no report. Tests of the enrichment itself replace the
    harvester's ``fetch`` explicitly, which takes precedence over this."""
    from iip.sources.fii_vacancia_harvester import FiiVacanciaHTTPHarvester

    monkeypatch.setattr(FiiVacanciaHTTPHarvester, "fetch", lambda self, ticker: None)
