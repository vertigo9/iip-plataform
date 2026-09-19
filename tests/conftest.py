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
