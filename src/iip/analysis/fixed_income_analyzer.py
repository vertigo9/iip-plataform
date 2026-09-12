from __future__ import annotations

from iip.analysis import AnalysisReport, Pillar, PillarScore
from iip.analysis.framework import AssetData, BaseAnalyzer, safe_segment


class FixedIncomeAnalyzer(BaseAnalyzer):
    """Reinterprets the shared 9-pillar framework for restricted,
    NAV-based funds with no market ticker of their own — the concrete
    case this session found: FMP-FGTS (Fundo Mútuo de Privatização do
    FGTS) funds, only accessible via FGTS, valued by CVM-reported NAV,
    never traded on B3.

    These funds have two structural traits that don't apply to
    FII/ETF/equity, and drive the weighting here:
      - Redemption is restricted (FGTS withdrawal rules, not a normal
        sell order) — CASH_FLOW here means "how easily can a cotista
        actually get their money back", not trading liquidity.
      - Many hold a SINGLE underlying asset (e.g. 100% Eletrobras
        shares for the Daycoval FMP-FGTS Eletrobras fund) — RESILIENCE
        here is dominated by underlying concentration risk, which
        matters far more than for a diversified ETF.

    MOAT and GROWTH carry the least weight — these funds aren't
    competing for flows or growing a business, they're a fixed
    privatization-era vehicle.
    """

    def __init__(self):
        self.pillar_weights = {
            Pillar.BUSINESS_MODEL: 0.10,
            Pillar.MOAT: 0.05,
            Pillar.GROWTH: 0.05,
            Pillar.MANAGEMENT: 0.10,
            Pillar.CASH_FLOW: 0.20,
            Pillar.GOVERNANCE: 0.10,
            Pillar.DIVIDENDS: 0.10,
            Pillar.CAPITAL_ALLOCATION: 0.10,
            Pillar.RESILIENCE: 0.20,
        }

    def analyze(self, data: AssetData) -> AnalysisReport:
        report = AnalysisReport(asset_symbol=data.symbol, asset_type="fixed_income")
        fin = data.financials

        report.add_pillar(self._analyze_business_model(fin))
        report.add_pillar(self._analyze_moat(fin))
        report.add_pillar(self._analyze_growth(fin))
        report.add_pillar(self._analyze_management(fin))
        report.add_pillar(self._analyze_cash_flow(fin))
        report.add_pillar(self._analyze_governance(fin))
        report.add_pillar(self._analyze_dividends(fin))
        report.add_pillar(self._analyze_capital_allocation(fin))
        report.add_pillar(self._analyze_resilience(fin))

        report.calculate_overall()
        report.set_recommendation()
        report.notes = f"Fixed Income Analysis for {safe_segment(data.industry, placeholder='fundo não preenchido')} fund"
        return report

    def _analyze_business_model(self, fin: dict) -> PillarScore:
        """Mandate clarity and regulatory standing — a restricted fund's
        "business" is simply doing what its mandate says, cleanly."""
        mandate_clarity = fin.get("mandate_clarity_score", 70)
        regulatory_compliance = fin.get("regulatory_compliance_score", 80)
        underlying_type = fin.get("underlying_asset_type", "ação única")

        indicators = {
            "Mandate Clarity": mandate_clarity,
            "Regulatory Compliance": regulatory_compliance,
            "Underlying Asset Type": underlying_type,
        }
        score = min((mandate_clarity + regulatory_compliance) / 2, 100.0)
        return PillarScore(
            pillar=Pillar.BUSINESS_MODEL,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.BUSINESS_MODEL],
            indicators=indicators,
        )

    def _analyze_moat(self, fin: dict) -> PillarScore:
        """These funds don't compete for flows — "moat" here is really
        just how hard the access channel is to replicate (irrelevant
        in practice, since nobody is trying to)."""
        exclusive_access = fin.get("exclusive_access_channel", True)
        replacement_difficulty = fin.get("replacement_difficulty_score", 50)

        indicators = {
            "Exclusive Access Channel": exclusive_access,
            "Replacement Difficulty": replacement_difficulty,
        }
        access_bonus = 20 if exclusive_access else 0
        score = min(replacement_difficulty + access_bonus, 100.0)
        return PillarScore(
            pillar=Pillar.MOAT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MOAT],
            indicators=indicators,
        )

    def _analyze_growth(self, fin: dict) -> PillarScore:
        """AUM trajectory — mostly informational for a fixed vehicle,
        not a growth thesis driver."""
        aum = fin.get("assets_under_management_millions", 100)
        cotista_growth = fin.get("cotista_growth_pct", 0)
        net_flows = fin.get("net_flows_millions", 0)

        indicators = {
            "AUM (Millions)": aum,
            "Cotista Growth %": cotista_growth,
            "Net Flows (Millions)": net_flows,
        }
        score = min(
            (min(aum, 100) + min(max(cotista_growth, 0) * 2, 100) + min(max(net_flows, 0) * 2, 100))
            / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.GROWTH,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GROWTH],
            indicators=indicators,
        )

    def _analyze_management(self, fin: dict) -> PillarScore:
        """Administrator track record and fee level."""
        manager_experience = fin.get("manager_experience_years", 10)
        management_fee = fin.get("management_fee_pct", 0.5)

        indicators = {
            "Manager Experience (years)": manager_experience,
            "Management Fee %": management_fee,
        }
        fee_score = max(0, 100 - management_fee * 40)
        score = min((min(manager_experience * 5, 100) + fee_score) / 2, 100.0)
        return PillarScore(
            pillar=Pillar.MANAGEMENT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MANAGEMENT],
            indicators=indicators,
        )

    def _analyze_cash_flow(self, fin: dict) -> PillarScore:
        """Redemption liquidity — NOT market trading liquidity (there is
        none). This is the single most practically important pillar
        for a FGTS-style fund: how restricted is getting your money
        back."""
        redemption_frequency_days = fin.get("redemption_frequency_days", 90)
        redemption_restriction = fin.get("redemption_restriction_score", 50)
        avg_processing_days = fin.get("avg_redemption_processing_days", 30)

        indicators = {
            "Redemption Frequency (days)": redemption_frequency_days,
            "Redemption Restriction Score": redemption_restriction,
            "Avg Redemption Processing (days)": avg_processing_days,
        }
        frequency_score = max(0, 100 - redemption_frequency_days / 3)
        processing_score = max(0, 100 - avg_processing_days * 2)
        score = min(
            (frequency_score + redemption_restriction + processing_score) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.CASH_FLOW,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CASH_FLOW],
            indicators=indicators,
        )

    def _analyze_governance(self, fin: dict) -> PillarScore:
        """Disclosure transparency about what's actually held."""
        disclosure_frequency_days = fin.get("portfolio_disclosure_frequency_days", 30)
        disclosure_quality = fin.get("disclosure_quality_score", 70)

        indicators = {
            "Disclosure Frequency (days)": disclosure_frequency_days,
            "Disclosure Quality": disclosure_quality,
        }
        frequency_score = max(0, 100 - disclosure_frequency_days)
        score = min((frequency_score + disclosure_quality) / 2, 100.0)
        return PillarScore(
            pillar=Pillar.GOVERNANCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GOVERNANCE],
            indicators=indicators,
        )

    def _analyze_dividends(self, fin: dict) -> PillarScore:
        """Distribution history, if the fund distributes at all (many
        FMP-FGTS funds accumulate rather than distribute)."""
        distribution_yield = fin.get("distribution_yield_pct", 0)
        distribution_frequency = fin.get("distribution_frequency_per_year", 0)

        indicators = {
            "Distribution Yield %": distribution_yield,
            "Distribution Frequency (per year)": distribution_frequency,
        }
        score = min(
            (min(distribution_yield * 8, 100) + min(distribution_frequency * 20, 100)) / 2,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.DIVIDENDS,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.DIVIDENDS],
            indicators=indicators,
        )

    def _analyze_capital_allocation(self, fin: dict) -> PillarScore:
        """How well the underlying holding itself is managed — since
        the fund itself doesn't allocate capital actively, this proxies
        through the quality of whatever it's required to hold."""
        underlying_management_quality = fin.get(
            "underlying_management_quality_score", 60
        )
        rebalancing_frequency_per_year = fin.get("rebalancing_frequency_per_year", 0)

        indicators = {
            "Underlying Management Quality": underlying_management_quality,
            "Rebalancing Frequency (per year)": rebalancing_frequency_per_year,
        }
        score = min(
            (underlying_management_quality + min(rebalancing_frequency_per_year * 25, 100))
            / 2,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.CAPITAL_ALLOCATION,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CAPITAL_ALLOCATION],
            indicators=indicators,
        )

    def _analyze_resilience(self, fin: dict) -> PillarScore:
        """Dominated by underlying concentration risk — a fund holding
        100% of one stock (the real AXIA3/Eletrobras case) is
        structurally fragile to that one company's fortunes, no matter
        how good anything else about the fund is."""
        underlying_concentration_pct = fin.get("underlying_concentration_pct", 100)
        nav_volatility_pct = fin.get("nav_volatility_pct", 20)
        underlying_credit_quality = fin.get("underlying_credit_quality_score", 60)

        indicators = {
            "Underlying Concentration %": underlying_concentration_pct,
            "NAV Volatility %": nav_volatility_pct,
            "Underlying Credit Quality": underlying_credit_quality,
        }
        concentration_score = max(0, 100 - underlying_concentration_pct)
        volatility_score = max(0, 100 - nav_volatility_pct * 2)
        score = min(
            (concentration_score + volatility_score + underlying_credit_quality) / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.RESILIENCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.RESILIENCE],
            indicators=indicators,
        )