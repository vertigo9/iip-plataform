from iip.analysis import Pillar
from iip.analysis.etf_analyzer import ETFAnalyzer
from iip.analysis.framework import AssetData


def _growth(**financials):
    data = AssetData(
        symbol="TEST11", sector="Renda Fixa", industry="ETF", financials=financials
    )
    report = ETFAnalyzer().analyze(data)
    return next(p for p in report.pillar_scores if p.pillar == Pillar.GROWTH)


def test_etf_growth_reads_the_aum_key_the_fetch_template_fills():
    pillar = _growth(assets_under_management_millions=40.0)

    assert pillar.indicators["AUM (Millions)"] == 40.0


def test_etf_growth_still_accepts_the_old_aum_key():
    pillar = _growth(aum_millions=40.0)

    assert pillar.indicators["AUM (Millions)"] == 40.0


def test_etf_growth_prefers_the_current_key_when_both_exist():
    pillar = _growth(assets_under_management_millions=40.0, aum_millions=90.0)

    assert pillar.indicators["AUM (Millions)"] == 40.0


def test_etf_growth_small_aum_lowers_the_score():
    small = _growth(assets_under_management_millions=10.0).score
    large = _growth(assets_under_management_millions=5000.0).score

    assert small < large
