from __future__ import annotations

from iip.analysis import AnalysisReport, Pillar, PillarScore
from iip.analysis.framework import AssetData, BaseAnalyzer, safe_segment


class AgroAnalyzer(BaseAnalyzer):
    def __init__(self):
        self.pillar_weights = {
            Pillar.BUSINESS_MODEL: 0.16,
            Pillar.MOAT: 0.12,
            Pillar.GROWTH: 0.10,
            Pillar.MANAGEMENT: 0.14,
            Pillar.CASH_FLOW: 0.18,
            Pillar.GOVERNANCE: 0.10,
            Pillar.DIVIDENDS: 0.12,
            Pillar.CAPITAL_ALLOCATION: 0.05,
            Pillar.RESILIENCE: 0.03,
        }

    def analyze(self, data: AssetData) -> AnalysisReport:
        report = AnalysisReport(asset_symbol=data.symbol, asset_type="agro")
        fin = data.financials

        report.add_pillar(self._analyze_agro_business_model(fin))
        report.add_pillar(self._analyze_agro_moat(fin))
        report.add_pillar(self._analyze_agro_growth(fin))
        report.add_pillar(self._analyze_agro_management(fin))
        report.add_pillar(self._analyze_agro_cash_flow(fin))
        report.add_pillar(self._analyze_agro_governance(fin))
        report.add_pillar(self._analyze_agro_dividends(fin))
        report.add_pillar(self._analyze_agro_capital_allocation(fin))
        report.add_pillar(self._analyze_agro_resilience(fin))

        report.calculate_overall()
        report.set_recommendation()
        report.notes = f"Agro Fund Analysis for {safe_segment(data.industry, placeholder='setor não preenchido')} sector"
        return report

    def _analyze_agro_business_model(self, fin: dict) -> PillarScore:
        """Analyze agricultural fund business model."""
        land_quality = fin.get("land_quality_score", 75)
        crop_diversification = fin.get("crop_diversification_score", 65)
        regional_focus = fin.get("regional_concentration_score", 70)
        commodity_mix = fin.get("commodity_mix_balance", 60)

        indicators = {
            "Land Quality": land_quality,
            "Crop Diversification": crop_diversification,
            "Regional Focus": regional_focus,
            "Commodity Mix Balance": commodity_mix,
        }
        score = min(
            (land_quality + crop_diversification + regional_focus + commodity_mix) / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.BUSINESS_MODEL,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.BUSINESS_MODEL],
            indicators=indicators,
        )

    def _analyze_agro_moat(self, fin: dict) -> PillarScore:
        """Analyze competitive advantages in agriculture."""
        land_appreciation = fin.get("land_appreciation_potential_score", 65)
        water_resources = fin.get("water_access_quality_score", 70)
        location_advantage = fin.get("logistics_location_score", 60)
        scale_advantage = fin.get("scale_advantage_score", 55)

        indicators = {
            "Land Appreciation Potential": land_appreciation,
            "Water Resources Quality": water_resources,
            "Logistics Location": location_advantage,
            "Scale Advantage": scale_advantage,
        }
        score = min(
            (land_appreciation + water_resources + location_advantage + scale_advantage)
            / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.MOAT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MOAT],
            indicators=indicators,
        )

    def _analyze_agro_growth(self, fin: dict) -> PillarScore:
        """Analyze growth potential for agricultural assets."""
        yield_improvement = fin.get("yield_improvement_trend", 3.5)
        land_expansion = fin.get("land_expansion_pipeline_hectares", 0)
        technology_adoption = fin.get("tech_adoption_rate_score", 65)
        price_cycle_position = fin.get("commodity_price_cycle_position", 0.5)

        indicators = {
            "Yield Improvement Trend %": yield_improvement,
            "Land Expansion (hectares)": land_expansion,
            "Technology Adoption": technology_adoption,
            "Price Cycle Position": round(price_cycle_position * 100, 2),
        }
        score = min(
            (
                yield_improvement * 15
                + min(land_expansion * 0.01, 100)
                + technology_adoption
                + price_cycle_position * 80
            )
            / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.GROWTH,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GROWTH],
            indicators=indicators,
        )

    def _analyze_agro_management(self, fin: dict) -> PillarScore:
        """Analyze management expertise in agriculture."""
        agribusiness_experience = fin.get("agribusiness_experience_years", 12)
        agronomy_team = fin.get("agronomy_team_quality_score", 70)
        operational_efficiency = fin.get("operational_efficiency_score", 68)
        sustainability_focus = fin.get("sustainability_commitment_score", 75)

        indicators = {
            "Agribusiness Experience (years)": agribusiness_experience,
            "Agronomy Team Quality": agronomy_team,
            "Operational Efficiency": operational_efficiency,
            "Sustainability Commitment": sustainability_focus,
        }
        score = min(
            (
                agribusiness_experience * 3
                + agronomy_team
                + operational_efficiency
                + sustainability_focus
            )
            / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.MANAGEMENT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MANAGEMENT],
            indicators=indicators,
        )

    def _analyze_agro_cash_flow(self, fin: dict) -> PillarScore:
        """Analyze cash flow from agricultural operations."""
        harvest_consistency = fin.get("harvest_consistency_score", 72)
        fcf_generation = fin.get("free_cash_flow_per_hectare", 500)
        receivables_quality = fin.get("receivables_collection_rate", 0.90)
        cost_control = fin.get("cost_control_effectiveness", 65)

        indicators = {
            "Harvest Consistency": harvest_consistency,
            "FCF per Hectare (BRL)": fcf_generation,
            "Receivables Collection %": round(receivables_quality * 100, 2),
            "Cost Control Effectiveness": cost_control,
        }
        fcf_normalized = min(fcf_generation / 10, 100)
        score = min(
            (
                harvest_consistency
                + fcf_normalized
                + receivables_quality * 100
                + cost_control
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

    def _analyze_agro_governance(self, fin: dict) -> PillarScore:
        """Analyze governance structure of agro fund."""
        board_independence = fin.get("board_independence", 0.55)
        esg_compliance = fin.get("esg_compliance_score", 70)
        transparency = fin.get("disclosure_transparency_score", 68)
        audit_quality = fin.get("audit_quality_score", 72)

        indicators = {
            "Board Independence %": round(board_independence * 100, 2),
            "ESG Compliance": esg_compliance,
            "Disclosure Transparency": transparency,
            "Audit Quality": audit_quality,
        }
        score = min(
            (board_independence * 100 + esg_compliance + transparency + audit_quality)
            / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.GOVERNANCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GOVERNANCE],
            indicators=indicators,
        )

    def _analyze_agro_dividends(self, fin: dict) -> PillarScore:
        """Analyze dividend distribution policy."""
        dividend_yield = fin.get("dividend_yield_pct", 11.5)
        payout_ratio = fin.get("payout_ratio", 0.90)
        seasonality_smoothing = fin.get("seasonality_smoothing_mechanism", True)
        distribution_frequency = fin.get("distribution_frequency_months", 3)

        indicators = {
            "Dividend Yield %": dividend_yield,
            "Payout Ratio %": round(payout_ratio * 100, 2),
            "Seasonality Smoothing": seasonality_smoothing,
            "Distribution Frequency (months)": distribution_frequency,
        }
        freq_score = max(0, 100 - distribution_frequency * 15)
        seasonal_bonus = 10 if seasonality_smoothing else 0
        score = min(
            (dividend_yield * 5 + payout_ratio * 60 + freq_score) / 3 + seasonal_bonus,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.DIVIDENDS,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.DIVIDENDS],
            indicators=indicators,
        )

    def _analyze_agro_capital_allocation(self, fin: dict) -> PillarScore:
        """Analyze capital allocation decisions."""
        land_acquisition_quality = fin.get("land_acquisition_track_record", 65)
        technology_investment = fin.get("technology_investment_ratio", 0.08)
        diversification_strategy = fin.get("crop_regional_diversification_score", 60)

        indicators = {
            "Land Acquisition Track Record": land_acquisition_quality,
            "Technology Investment %": round(technology_investment * 100, 2),
            "Diversification Strategy": diversification_strategy,
        }
        score = min(
            (
                land_acquisition_quality
                + min(technology_investment * 500, 100)
                + diversification_strategy
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

    def _analyze_agro_resilience(self, fin: dict) -> PillarScore:
        """Analyze resilience against agricultural risks."""
        weather_hedging = fin.get("weather_risk_hedging_score", 60)
        crop_insurance = fin.get("crop_insurance_coverage_ratio", 0.85)
        leverage_ratio = fin.get("debt_to_assets_ratio", 0.35)
        liquidity_buffer = fin.get("liquidity_reserve_months", 4)

        indicators = {
            "Weather Risk Hedging": weather_hedging,
            "Crop Insurance Coverage %": round(crop_insurance * 100, 2),
            "Debt to Assets %": round(leverage_ratio * 100, 2),
            "Liquidity Reserve (months)": liquidity_buffer,
        }
        insurance_bonus = crop_insurance * 15
        liquidity_bonus = liquidity_buffer * 8
        score = min(
            (
                weather_hedging
                + insurance_bonus
                + liquidity_bonus
                + max(0, 100 - leverage_ratio * 150)
            )
            / 4,
            100.0,
        )
        return PillarScore(
            pillar=Pillar.RESILIENCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.RESILIENCE],
            indicators=indicators,
        )
