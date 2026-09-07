from __future__ import annotations

from iip.analysis import AnalysisReport, Pillar, PillarScore
from iip.analysis.framework import AssetData, BaseAnalyzer


class InfraAnalyzer(BaseAnalyzer):
    def __init__(self):
        self.pillar_weights = {
            Pillar.BUSINESS_MODEL: 0.18,
            Pillar.MOAT: 0.15,
            Pillar.GROWTH: 0.08,
            Pillar.MANAGEMENT: 0.12,
            Pillar.CASH_FLOW: 0.20,
            Pillar.GOVERNANCE: 0.10,
            Pillar.DIVIDENDS: 0.10,
            Pillar.CAPITAL_ALLOCATION: 0.04,
            Pillar.RESILIENCE: 0.03,
        }

    def analyze(self, data: AssetData) -> AnalysisReport:
        report = AnalysisReport(asset_symbol=data.symbol, asset_type="infra")
        fin = data.financials

        report.add_pillar(self._analyze_infra_business_model(fin))
        report.add_pillar(self._analyze_infra_moat(fin))
        report.add_pillar(self._analyze_infra_growth(fin))
        report.add_pillar(self._analyze_infra_management(fin))
        report.add_pillar(self._analyze_infra_cash_flow(fin))
        report.add_pillar(self._analyze_infra_governance(fin))
        report.add_pillar(self._analyze_infra_dividends(fin))
        report.add_pillar(self._analyze_infra_capital_allocation(fin))
        report.add_pillar(self._analyze_infra_resilience(fin))

        report.calculate_overall()
        report.set_recommendation()
        report.notes = f"Infra Fund Analysis for {data.industry} sector"
        return report

    def _analyze_infra_business_model(self, fin: dict) -> PillarScore:
        """Analyze business model specific to infrastructure funds."""
        # Focus on concession quality, regulatory environment, revenue stability
        rev_stability = fin.get("revenue_stability_score", 70)
        concession_term = fin.get("concession_remaining_years", 10)
        regulatory_quality = fin.get("regulatory_environment_score", 65)
        sector_type = fin.get("sector_type", "unknown")

        indicators = {
            "Revenue Stability": rev_stability,
            "Concession Term (years)": concession_term,
            "Regulatory Quality": regulatory_quality,
            "Sector Type": sector_type,
        }
        score = min(
            (rev_stability + concession_term * 3 + regulatory_quality) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.BUSINESS_MODEL,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.BUSINESS_MODEL],
            indicators=indicators,
        )

    def _analyze_infra_moat(self, fin: dict) -> PillarScore:
        """Analyze competitive advantages (natural monopoly characteristics)."""
        market_share = fin.get("market_share_percentage", 50)
        switching_cost = fin.get("customer_switching_cost_score", 70)
        barrier_entry = fin.get("entry_barrier_score", 80)
        geographic_monopoly = fin.get("geographic_monopoly_status", False)

        indicators = {
            "Market Share %": market_share,
            "Customer Switching Cost": switching_cost,
            "Entry Barrier": barrier_entry,
            "Geographic Monopoly": geographic_monopoly,
        }
        geo_bonus = 15 if geographic_monopoly else 0
        score = min(
            ((market_share + switching_cost + barrier_entry) / 3) + geo_bonus, 100.0
        )
        return PillarScore(
            pillar=Pillar.MOAT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MOAT],
            indicators=indicators,
        )

    def _analyze_infra_growth(self, fin: dict) -> PillarScore:
        """Analyze growth potential for infrastructure assets."""
        capex_pipeline = fin.get("capex_expansion_pipeline_millions", 0)
        tariff_adjustment = fin.get("tariff_indexation_clause", True)
        expansion_projects = fin.get("expansion_projects_count", 0)
        demand_growth = fin.get("demand_growth_forecast_5y", 3.0)

        indicators = {
            "CAPEX Pipeline (M)": capex_pipeline,
            "Tariff Indexation": tariff_adjustment,
            "Expansion Projects": expansion_projects,
            "Demand Growth Forecast": demand_growth,
        }
        score = min(
            (
                min(capex_pipeline * 0.5, 100)
                + min(expansion_projects * 10, 100)
                + demand_growth * 15
            )
            / 3,
            100.0,
        )
        tariff_bonus = 10 if tariff_adjustment else 0
        score = min(score + tariff_bonus, 100.0)
        return PillarScore(
            pillar=Pillar.GROWTH,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GROWTH],
            indicators=indicators,
        )

    def _analyze_infra_management(self, fin: dict) -> PillarScore:
        """Analyze management team expertise in infrastructure."""
        mgmt_experience = fin.get("management_infra_experience_years", 10)
        track_record = fin.get("project_completion_rate", 0.85)
        alignment = fin.get("mgmt_asset_alignment_ratio", 0.10)

        indicators = {
            "Infrastructure Experience (years)": mgmt_experience,
            "Project Completion Rate": round(track_record * 100, 2),
            "Management Alignment": round(alignment * 100, 2),
        }
        score = min(
            (mgmt_experience * 2 + track_record * 100 + alignment * 300) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.MANAGEMENT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MANAGEMENT],
            indicators=indicators,
        )

    def _analyze_infra_cash_flow(self, fin: dict) -> PillarScore:
        """Analyze cash flow generation and predictability."""
        fcf_predictability = fin.get("cash_flow_predictability_score", 85)
        fcf_conversion = fin.get("ebitda_to_fcf_conversion", 0.80)
        operating_margin = fin.get("operating_margin_ebitda", 0.60)
        free_cash_flow_yield = fin.get("free_cash_flow_yield_pct", 8.0)

        indicators = {
            "Cash Flow Predictability": fcf_predictability,
            "EBITDA to FCF Conversion %": round(fcf_conversion * 100, 2),
            "Operating Margin %": round(operating_margin * 100, 2),
            "FCF Yield %": free_cash_flow_yield,
        }
        score = min(
            (
                fcf_predictability
                + fcf_conversion * 50
                + operating_margin * 80
                + free_cash_flow_yield * 8
            )
            / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.CASH_FLOW,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CASH_FLOW],
            indicators=indicators,
        )

    def _analyze_infra_governance(self, fin: dict) -> PillarScore:
        """Analyze governance structure for infrastructure fund."""
        board_quality = fin.get("board_independence", 0.6)
        transparency = fin.get("disclosure_quality_score", 75)
        audit_quality = fin.get("audit_quality_score", 70)
        stakeholder_rights = fin.get("stakeholder_rights_protection", 70)

        indicators = {
            "Board Independence %": round(board_quality * 100, 2),
            "Disclosure Quality": transparency,
            "Audit Quality": audit_quality,
            "Stakeholder Rights": stakeholder_rights,
        }
        score = min(
            (board_quality * 100 + transparency + audit_quality + stakeholder_rights)
            / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.GOVERNANCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GOVERNANCE],
            indicators=indicators,
        )

    def _analyze_infra_dividends(self, fin: dict) -> PillarScore:
        """Analyze dividend distribution policy."""
        dividend_yield = fin.get("dividend_yield_pct", 10.0)
        payout_policy = fin.get("mandatory_payout_ratio", 0.95)
        distribution_consistency = fin.get("distribution_consistency_score", 85)

        indicators = {
            "Dividend Yield %": dividend_yield,
            "Payout Policy %": round(payout_policy * 100, 2),
            "Distribution Consistency": distribution_consistency,
        }
        score = min(
            (dividend_yield * 5 + payout_policy * 50 + distribution_consistency) / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.DIVIDENDS,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.DIVIDENDS],
            indicators=indicators,
        )

    def _analyze_infra_capital_allocation(self, fin: dict) -> PillarScore:
        """Analyze capital allocation efficiency."""
        reinvestment_rate = fin.get("reinvestment_rate", 0.15)
        acquisition_quality = fin.get("acquisition_track_record_score", 60)
        debt_optimization = fin.get("debt_cost_optimization", 70)

        indicators = {
            "Reinvestment Rate %": round(reinvestment_rate * 100, 2),
            "Acquisition Track Record": acquisition_quality,
            "Debt Optimization": debt_optimization,
        }
        score = min(
            (
                max(0, 100 - reinvestment_rate * 200)
                + acquisition_quality
                + debt_optimization
            )
            / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.CAPITAL_ALLOCATION,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CAPITAL_ALLOCATION],
            indicators=indicators,
        )

    def _analyze_infra_resilience(self, fin: dict) -> PillarScore:
        """Analyze resilience of infrastructure assets."""
        leverage = fin.get("net_debt_to_ebitda", 4.0)
        maturity_profile = fin.get("weighted_avg_debt_maturity_years", 8)
        hedge_ratio = fin.get("interest_rate_hedge_ratio", 0.70)

        indicators = {
            "Net Debt/EBITDA": leverage,
            "Debt Maturity (years)": maturity_profile,
            "Interest Rate Hedge %": round(hedge_ratio * 100, 2),
        }
        score = min(
            (max(0, 100 - leverage * 12) + maturity_profile * 8 + hedge_ratio * 60) / 3,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.RESILIENCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.RESILIENCE],
            indicators=indicators,
        )
