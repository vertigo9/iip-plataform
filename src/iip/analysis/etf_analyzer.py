from __future__ import annotations

from iip.analysis import AnalysisReport, Pillar, PillarScore
from iip.analysis.framework import AssetData, BaseAnalyzer, safe_segment


class ETFAnalyzer(BaseAnalyzer):
    """Reinterprets the shared 9-pillar framework for passive index
    funds. An ETF has no active management to judge on moat/growth the
    way a stock or FII does — what actually differentiates a good ETF
    from a bad one is liquidity, tracking accuracy, and cost. Weights
    reflect that: CASH_FLOW (liquidity) and RESILIENCE (tracking
    accuracy) carry the most weight; MOAT and GROWTH the least, since
    an ETF is a largely commoditized wrapper around an index, not a
    business with a competitive position to defend or grow.
    """

    def __init__(self):
        self.pillar_weights = {
            Pillar.BUSINESS_MODEL: 0.10,
            Pillar.MOAT: 0.05,
            Pillar.GROWTH: 0.08,
            Pillar.MANAGEMENT: 0.15,
            Pillar.CASH_FLOW: 0.20,
            Pillar.GOVERNANCE: 0.08,
            Pillar.DIVIDENDS: 0.09,
            Pillar.CAPITAL_ALLOCATION: 0.10,
            Pillar.RESILIENCE: 0.15,
        }

    def analyze(self, data: AssetData) -> AnalysisReport:
        report = AnalysisReport(asset_symbol=data.symbol, asset_type="etf")
        fin = data.financials

        report.add_pillar(self._analyze_etf_business_model(fin))
        report.add_pillar(self._analyze_etf_moat(fin))
        report.add_pillar(self._analyze_etf_growth(fin))
        report.add_pillar(self._analyze_etf_management(fin))
        report.add_pillar(self._analyze_etf_cash_flow(fin))
        report.add_pillar(self._analyze_etf_governance(fin))
        report.add_pillar(self._analyze_etf_dividends(fin))
        report.add_pillar(self._analyze_etf_capital_allocation(fin))
        report.add_pillar(self._analyze_etf_resilience(fin))

        report.calculate_overall()
        report.set_recommendation()
        report.notes = f"ETF Analysis for {safe_segment(data.industry, placeholder='índice não preenchido')} index exposure"
        return report

    def _analyze_etf_business_model(self, fin: dict) -> PillarScore:
        """Index methodology and replication quality — a physically
        replicated ETF tracking a well-constructed index from a
        reputable provider is the baseline "good business model" for
        a passive fund."""
        methodology_quality = fin.get("index_methodology_quality_score", 70)
        replication_method = fin.get("replication_method", "physical")
        provider_reputation = fin.get("index_provider_reputation_score", 70)

        indicators = {
            "Index Methodology Quality": methodology_quality,
            "Replication Method": replication_method,
            "Index Provider Reputation": provider_reputation,
        }
        replication_bonus = 10 if replication_method == "physical" else 0
        score = min(
            (methodology_quality + provider_reputation) / 2 + replication_bonus, 100.0
        )
        return PillarScore(
            pillar=Pillar.BUSINESS_MODEL,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.BUSINESS_MODEL],
            indicators=indicators,
        )

    def _analyze_etf_moat(self, fin: dict) -> PillarScore:
        """An ETF's "moat" is exposure uniqueness — being first (or
        only) to a differentiated index matters more than brand, since
        the product itself is a commodity wrapper."""
        uniqueness = fin.get("index_uniqueness_score", 50)
        first_mover = fin.get("first_mover_status", False)
        competitors = fin.get("competing_etfs_count", 3)

        indicators = {
            "Index Uniqueness": uniqueness,
            "First Mover": first_mover,
            "Competing ETFs": competitors,
        }
        first_mover_bonus = 15 if first_mover else 0
        competition_penalty = min(competitors * 8, 60)
        score = min(max(0, uniqueness + first_mover_bonus - competition_penalty), 100.0)
        return PillarScore(
            pillar=Pillar.MOAT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MOAT],
            indicators=indicators,
        )

    def _analyze_etf_growth(self, fin: dict) -> PillarScore:
        """AUM trajectory — a growing ETF tends toward better liquidity
        and lower closure risk; a shrinking one risks delisting."""
        aum = fin.get("aum_millions", 100)
        net_inflows_ytd = fin.get("net_inflows_ytd_millions", 0)
        aum_growth_3y = fin.get("aum_growth_3y_pct", 0)

        indicators = {
            "AUM (Millions)": aum,
            "Net Inflows YTD (Millions)": net_inflows_ytd,
            "AUM Growth 3y %": aum_growth_3y,
        }
        score = min(
            (
                min(aum, 100)
                + min(max(net_inflows_ytd, 0) * 2, 100)
                + min(max(aum_growth_3y, 0) * 2, 100)
            )
            / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.GROWTH,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GROWTH],
            indicators=indicators,
        )

    def _analyze_etf_management(self, fin: dict) -> PillarScore:
        """Cost is the single biggest controllable driver of long-run
        ETF returns — a lower expense ratio directly benefits every
        holder, unlike active-fund fees which at least buy a shot at
        outperformance."""
        expense_ratio = fin.get("expense_ratio_pct", 0.5)
        manager_experience = fin.get("manager_etf_experience_years", 5)
        lending_revenue_share = fin.get("securities_lending_revenue_share_pct", 50)

        indicators = {
            "Expense Ratio %": expense_ratio,
            "Manager ETF Experience (years)": manager_experience,
            "Securities Lending Revenue Share %": lending_revenue_share,
        }
        expense_score = max(0, 100 - expense_ratio * 80)
        score = min(
            (expense_score + min(manager_experience * 8, 100) + lending_revenue_share)
            / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.MANAGEMENT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MANAGEMENT],
            indicators=indicators,
        )

    def _analyze_etf_cash_flow(self, fin: dict) -> PillarScore:
        """Liquidity — the practical thing that determines whether you
        can actually get in and out of an ETF at a fair price."""
        avg_daily_volume = fin.get("avg_daily_volume_brl", 1_000_000)
        bid_ask_spread_bps = fin.get("avg_bid_ask_spread_bps", 20)
        market_makers = fin.get("market_makers_count", 2)

        indicators = {
            "Avg Daily Volume (BRL)": avg_daily_volume,
            "Avg Bid-Ask Spread (bps)": bid_ask_spread_bps,
            "Market Makers": market_makers,
        }
        volume_score = min(avg_daily_volume / 50_000, 100)
        spread_score = max(0, 100 - bid_ask_spread_bps * 2)
        score = min(
            (volume_score + spread_score + min(market_makers * 25, 100)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.CASH_FLOW,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CASH_FLOW],
            indicators=indicators,
        )

    def _analyze_etf_governance(self, fin: dict) -> PillarScore:
        """Transparency — how visible the fund's holdings and
        securities-lending activity are to holders."""
        disclosure_frequency_days = fin.get("portfolio_disclosure_frequency_days", 1)
        disclosure_quality = fin.get("disclosure_quality_score", 70)
        lending_transparency = fin.get(
            "securities_lending_policy_transparency_score", 70
        )

        indicators = {
            "Disclosure Frequency (days)": disclosure_frequency_days,
            "Disclosure Quality": disclosure_quality,
            "Securities Lending Transparency": lending_transparency,
        }
        frequency_score = max(0, 100 - disclosure_frequency_days * 10)
        score = min(
            (frequency_score + disclosure_quality + lending_transparency) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.GOVERNANCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GOVERNANCE],
            indicators=indicators,
        )

    def _analyze_etf_dividends(self, fin: dict) -> PillarScore:
        """Income distribution — relevant mainly for income-oriented
        ETFs (bond, dividend-index); growth-index ETFs legitimately
        score low here without that being a flaw."""
        dividend_yield = fin.get("dividend_yield_pct", 0)
        distribution_frequency = fin.get("distribution_frequency_per_year", 0)
        distribution_consistency = fin.get("distribution_consistency_score", 70)

        indicators = {
            "Dividend Yield %": dividend_yield,
            "Distribution Frequency (per year)": distribution_frequency,
            "Distribution Consistency": distribution_consistency,
        }
        score = min(
            (
                min(dividend_yield * 8, 100)
                + min(distribution_frequency * 15, 100)
                + distribution_consistency
            )
            / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.DIVIDENDS,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.DIVIDENDS],
            indicators=indicators,
        )

    def _analyze_etf_capital_allocation(self, fin: dict) -> PillarScore:
        """Creation/redemption mechanism efficiency — how cleanly the
        ETF structure itself operates, including the tax efficiency of
        in-kind creation/redemption."""
        creation_redemption_efficiency = fin.get(
            "creation_redemption_efficiency_score", 70
        )
        rebalancing_cost_bps = fin.get("rebalancing_cost_bps", 10)
        in_kind_ratio = fin.get("in_kind_creation_ratio", 0.8)

        indicators = {
            "Creation/Redemption Efficiency": creation_redemption_efficiency,
            "Rebalancing Cost (bps)": rebalancing_cost_bps,
            "In-Kind Creation Ratio %": round(in_kind_ratio * 100, 2),
        }
        rebalancing_score = max(0, 100 - rebalancing_cost_bps * 4)
        score = min(
            (creation_redemption_efficiency + rebalancing_score + in_kind_ratio * 100)
            / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.CAPITAL_ALLOCATION,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CAPITAL_ALLOCATION],
            indicators=indicators,
        )

    def _analyze_etf_resilience(self, fin: dict) -> PillarScore:
        """Tracking accuracy — the thing an ETF fundamentally promises
        to do well. High tracking error or a volatile premium/discount
        to NAV means the fund isn't reliably delivering the exposure
        it claims to."""
        tracking_error = fin.get("tracking_error_pct", 0.5)
        tracking_difference = fin.get("tracking_difference_pct", 0.3)
        premium_discount_volatility = fin.get("premium_discount_volatility_pct", 0.2)

        indicators = {
            "Tracking Error %": tracking_error,
            "Tracking Difference %": tracking_difference,
            "Premium/Discount Volatility %": premium_discount_volatility,
        }
        score = min(
            (
                max(0, 100 - tracking_error * 40)
                + max(0, 100 - abs(tracking_difference) * 40)
                + max(0, 100 - premium_discount_volatility * 50)
            )
            / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.RESILIENCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.RESILIENCE],
            indicators=indicators,
        )
