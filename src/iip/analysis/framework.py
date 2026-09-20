from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from iip.analysis import AnalysisReport, Pillar, PillarScore


def safe_segment(value: str | None, *, placeholder: str = "") -> str:
    """Guard de relatório: placeholder de julgamento não deve sair na entrega.

    Campos de segmento (sector/industry) chegam dos templates com
    'REPLACE_WITH_*' quando não foram derivados do dado real — isso é
    instrução para o usuário, não entrega. Imprimir o placeholder cru no
    relatório (ex.: "FII Analysis for REPLACE_WITH_INDUSTRY fund") vaza
    instrução no artefato persistido no vault; omitir é mais honesto.
    """
    if not value or value.startswith("REPLACE_WITH"):
        return placeholder
    return value


@dataclass
class AssetData:
    symbol: str
    sector: str
    industry: str
    market_cap: float | None = None
    price: float | None = None
    financials: dict[str, Any] = field(default_factory=dict)


class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, data: AssetData) -> AnalysisReport:
        pass

    @staticmethod
    def calc_roic(ebit: float, invested_capital: float) -> float:
        if invested_capital == 0:
            return 0.0
        return min((ebit / invested_capital) * 100, 100.0)

    @staticmethod
    def calc_roe(net_income: float, equity: float) -> float:
        if equity == 0:
            return 0.0
        return min((net_income / equity) * 100, 100.0)

    @staticmethod
    def calc_margin(ebit: float, revenue: float) -> float:
        if revenue == 0:
            return 0.0
        return min((ebit / revenue) * 100, 100.0)


class EquityAnalyzer(BaseAnalyzer):
    def __init__(self):
        self.pillar_weights = {
            Pillar.BUSINESS_MODEL: 0.15,
            Pillar.MOAT: 0.15,
            Pillar.GROWTH: 0.12,
            Pillar.MANAGEMENT: 0.10,
            Pillar.CASH_FLOW: 0.15,
            Pillar.GOVERNANCE: 0.08,
            Pillar.DIVIDENDS: 0.10,
            Pillar.CAPITAL_ALLOCATION: 0.10,
            Pillar.RESILIENCE: 0.05,
        }

    def analyze(self, data: AssetData) -> AnalysisReport:
        report = AnalysisReport(asset_symbol=data.symbol, asset_type="equity")
        report.add_pillar(self._analyze_business_model(data))
        report.add_pillar(self._analyze_moat(data))
        report.add_pillar(self._analyze_growth(data))
        report.add_pillar(self._analyze_management(data))
        report.add_pillar(self._analyze_cash_flow(data))
        report.add_pillar(self._analyze_governance(data))
        report.add_pillar(self._analyze_dividends(data))
        report.add_pillar(self._analyze_capital_allocation(data))
        report.add_pillar(self._analyze_resilience(data))
        report.calculate_overall()
        report.set_recommendation()
        report.notes = (
            f"Analysis for {safe_segment(data.sector, placeholder='—')}"
            f"/{safe_segment(data.industry, placeholder='—')} sector"
        )
        return report

    def _analyze_business_model(self, data: AssetData) -> PillarScore:
        fin = data.financials
        roic = min(
            self.calc_roic(fin.get("ebit", 0), fin.get("invested_capital", 1)), 100.0
        )
        roe = min(self.calc_roe(fin.get("net_income", 0), fin.get("equity", 1)), 100.0)
        margin = min(self.calc_margin(fin.get("ebit", 0), fin.get("revenue", 1)), 100.0)
        indicators = {
            "ROIC": round(roic, 2),
            "ROE": round(roe, 2),
            "EBIT Margin": round(margin, 2),
        }
        score = min((roic + roe + min(margin * 3, 100)) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.BUSINESS_MODEL,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.BUSINESS_MODEL],
            indicators=indicators,
        )

    def _analyze_moat(self, data: AssetData) -> PillarScore:
        fin = data.financials
        gms = fin.get("gross_margin_stability", 50)
        pp = fin.get("pricing_power", 50)
        sc = fin.get("switching_costs", 50)
        indicators = {
            "Gross Margin Stability": gms,
            "Pricing Power": pp,
            "Switching Costs": sc,
        }
        score = min((gms + pp + sc) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.MOAT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MOAT],
            indicators=indicators,
        )

    def _analyze_growth(self, data: AssetData) -> PillarScore:
        fin = data.financials
        rg = fin.get("revenue_growth_3y", 0)
        eg = fin.get("earnings_growth_3y", 0)
        bg = fin.get("book_value_growth_3y", 0)
        indicators = {
            "Revenue Growth (3y)": rg,
            "Earnings Growth (3y)": eg,
            "Book Value Growth (3y)": bg,
        }
        score = min((min(rg * 2, 100) + min(eg * 2, 100) + min(bg * 2, 100)) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.GROWTH,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GROWTH],
            indicators=indicators,
        )

    def _analyze_management(self, data: AssetData) -> PillarScore:
        fin = data.financials
        io = fin.get("insider_ownership", 0)
        mt = fin.get("management_tenure_years", 0)
        sig = fin.get("skin_in_game_ratio", 0)
        indicators = {
            "Insider Ownership": io,
            "Management Tenure": mt,
            "Skin in Game": sig,
        }
        score = min(
            (min(io * 5, 100) + min(mt * 5, 100) + min(sig * 100, 100)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.MANAGEMENT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MANAGEMENT],
            indicators=indicators,
        )

    def _analyze_cash_flow(self, data: AssetData) -> PillarScore:
        fin = data.financials
        fcr = fin.get("fcf_conversion_ratio", 0)
        og = fin.get("ocf_growth_3y", 0)
        ci = fin.get("capex_to_revenue", 0.1)
        indicators = {
            "FCF Conversion Ratio": round(fcr * 100, 2),
            "OCF Growth (3y)": og,
            "Capex Intensity": round(ci * 100, 2),
        }
        score = min(
            (min(fcr * 100, 100) + min(og * 2, 100) + max(0, 100 - ci * 100)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.CASH_FLOW,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CASH_FLOW],
            indicators=indicators,
        )

    def _analyze_governance(self, data: AssetData) -> PillarScore:
        fin = data.financials
        bi = fin.get("board_independence", 0.5)
        rpt = fin.get("related_party_transactions_ratio", 0)
        aq = fin.get("audit_quality_score", 50)
        indicators = {
            "Board Independence": round(bi * 100, 2),
            "Related Party Transactions": round(rpt * 100, 2),
            "Audit Quality": aq,
        }
        score = min((bi * 100 + max(0, 100 - rpt * 200) + aq) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.GOVERNANCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GOVERNANCE],
            indicators=indicators,
        )

    def _analyze_dividends(self, data: AssetData) -> PillarScore:
        fin = data.financials
        dy = fin.get("dividend_yield", 0)
        pr = fin.get("payout_ratio", 0)
        dc = fin.get("dividend_consistency_years", 0)
        indicators = {
            "Dividend Yield": round(dy * 10, 2),
            "Payout Ratio": round(pr * 100, 2),
            "Dividend Consistency": dc,
        }
        score = min(
            (min(dy * 15, 100) + min(pr * 1.5, 100) + min(dc * 5, 100)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.DIVIDENDS,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.DIVIDENDS],
            indicators=indicators,
        )

    def _analyze_capital_allocation(self, data: AssetData) -> PillarScore:
        fin = data.financials
        roic_val = self.calc_roic(fin.get("ebit", 0), fin.get("invested_capital", 1))
        wacc = fin.get("wacc", 8)
        rvs = min(max(roic_val - wacc, -100), 100)
        aus = fin.get("acquisition_success_score", 50)
        bfe = fin.get("buyback_effectiveness", 50)
        indicators = {
            "ROIC vs WACC Spread": round(rvs, 2),
            "Acquisition Success": aus,
            "Buyback Effectiveness": bfe,
        }
        score = min((min(max(rvs * 5, 0), 100) + aus + bfe) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.CAPITAL_ALLOCATION,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CAPITAL_ALLOCATION],
            indicators=indicators,
        )

    def _analyze_resilience(self, data: AssetData) -> PillarScore:
        fin = data.financials
        de = fin.get("debt_to_equity", 0.5)
        ic = fin.get("interest_coverage", 5)
        cr = fin.get("current_ratio", 1.5)
        indicators = {"Debt/Equity": de, "Interest Coverage": ic, "Current Ratio": cr}
        score = min(
            (max(0, 100 - de * 50) + min(ic * 10, 100) + min(cr * 30, 100)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.RESILIENCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.RESILIENCE],
            indicators=indicators,
        )


# Prazo médio dos contratos que ainda soma pontos no pilar de modelo de negócio (FII).
_FII_LEASE_TERM_CAP_YEARS = 10


class FIIAnalyzer(BaseAnalyzer):
    def __init__(self):
        self.pillar_weights = {
            Pillar.BUSINESS_MODEL: 0.15,
            Pillar.MOAT: 0.10,
            Pillar.GROWTH: 0.10,
            Pillar.MANAGEMENT: 0.12,
            Pillar.CASH_FLOW: 0.18,
            Pillar.GOVERNANCE: 0.10,
            Pillar.DIVIDENDS: 0.15,
            Pillar.CAPITAL_ALLOCATION: 0.05,
            Pillar.RESILIENCE: 0.10,
        }

    def analyze(self, data: AssetData) -> AnalysisReport:
        report = AnalysisReport(asset_symbol=data.symbol, asset_type="fii")
        fin = data.financials
        report.add_pillar(self._analyze_fii_business_model(fin))
        report.add_pillar(self._analyze_fii_moat(fin))
        report.add_pillar(self._analyze_fii_growth(fin))
        report.add_pillar(self._analyze_fii_management(fin))
        report.add_pillar(self._analyze_fii_cash_flow(fin))
        report.add_pillar(self._analyze_fii_governance(fin))
        report.add_pillar(self._analyze_fii_dividends(fin))
        report.add_pillar(self._analyze_fii_capital_allocation(fin))
        report.add_pillar(self._analyze_fii_resilience(fin))
        report.calculate_overall()
        report.set_recommendation()
        report.notes = f"FII Analysis for {safe_segment(data.industry, placeholder='setor não preenchido')} fund"
        return report

    def _analyze_fii_business_model(self, fin: dict) -> PillarScore:
        occupancy = fin.get("occupancy_rate", 0.85)
        lease = fin.get("avg_lease_term_years", 5)
        tenant = fin.get("tenant_concentration_top5", 0.3)
        indicators = {
            "Occupancy Rate": round(occupancy * 100, 2),
            "Avg Lease Term": lease,
            "Tenant Concentration": round(tenant * 100, 2),
        }
        # 10 pontos por ano de prazo, com teto em 10 anos (100 pontos, a escala dos
        # outros dois termos): sem o teto, um WALE de 13 anos valia 134 pontos e
        # compensava vacância ou concentração no pilar
        lease_points = min(max(lease, 0), _FII_LEASE_TERM_CAP_YEARS) * 10
        score = min(
            (occupancy * 100 + lease_points + max(0, 100 - tenant * 200)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.BUSINESS_MODEL,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.BUSINESS_MODEL],
            indicators=indicators,
        )

    def _analyze_fii_moat(self, fin: dict) -> PillarScore:
        loc = fin.get("location_quality_score", 70)
        prop = fin.get("property_diversification_score", 60)
        premium = fin.get("reit_premium_discount", 0.0)
        indicators = {
            "Location Quality": loc,
            "Property Diversification": prop,
            "REIT Premium/Discount": round(premium * 100, 2),
        }
        score = min((loc + prop + max(0, 100 - abs(premium) * 200)) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.MOAT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MOAT],
            indicators=indicators,
        )

    def _analyze_fii_growth(self, fin: dict) -> PillarScore:
        npa = fin.get("npa_growth_3y", 0)
        dg = fin.get("dividend_growth_3y", 0)
        acq = fin.get("acquisitions_pipeline_value", 0)
        indicators = {
            "NPA Growth (3y)": npa,
            "Dividend Growth (3y)": dg,
            "Acquisitions Pipeline": acq,
        }
        score = min(
            (min(npa * 3, 100) + min(dg * 3, 100) + min(acq * 10, 100)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.GROWTH,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GROWTH],
            indicators=indicators,
        )

    def _analyze_fii_management(self, fin: dict) -> PillarScore:
        fee = fin.get("management_fee_ratio", 0.005)
        record = fin.get("manager_track_record_years", 5)
        aum = fin.get("assets_under_management_millions", 100)
        indicators = {
            "Management Fee Ratio": round(fee * 1000, 2),
            "Track Record": record,
            "AUM (Millions)": aum,
        }
        # FIXED: Added min caps to prevent score > 100
        score = min(
            (max(0, 100 - fee * 500) + min(record * 10, 100) + min(aum, 100)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.MANAGEMENT,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.MANAGEMENT],
            indicators=indicators,
        )

    def _analyze_fii_cash_flow(self, fin: dict) -> PillarScore:
        dist = fin.get("distribution_ytd", 0)
        consistency = fin.get("distribution_consistency_months", 12)
        reserves = fin.get("reserves_to_npa", 0.05)
        indicators = {
            "Distribution YTD": dist,
            "Consistency": consistency,
            "Reserves/NPA": round(reserves * 100, 2),
        }
        score = min((min(dist * 2, 100) + consistency * 8 + reserves * 100) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.CASH_FLOW,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CASH_FLOW],
            indicators=indicators,
        )

    def _analyze_fii_governance(self, fin: dict) -> PillarScore:
        bi = fin.get("board_independence", 0.5)
        rp = fin.get("related_party_leasing_ratio", 0)
        dq = fin.get("disclosure_quality_score", 70)
        indicators = {
            "Board Independence": round(bi * 100, 2),
            "Related Party Leasing": round(rp * 100, 2),
            "Disclosure Quality": dq,
        }
        score = min((bi * 100 + max(0, 100 - rp * 200) + dq) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.GOVERNANCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.GOVERNANCE],
            indicators=indicators,
        )

    def _analyze_fii_dividends(self, fin: dict) -> PillarScore:
        """Dividends pillar for FIIs.

        Two calibrations, chosen by whether the data carries the market's
        risk-free rate (``risk_free_real_yield``, the long NTN-B real yield in
        percent -- filled by ``fetch-template``/the batches):

        - WITH it: the yield term is ``dy / (2 * risk_free)`` clamped to 0-100
          (a yield equal to the real risk-free rate scores 50, twice it scores
          100), so it does not saturate at a fixed yield; ``yield_on_cost`` (the
          investor's own cost basis, which public data cannot provide) only
          counts when explicitly supplied; the pillar averages the terms present.
        - WITHOUT it (hand-written data files): the original formula, unchanged --
          ``(min(dy*12, 100) + min(yoc*12, 100) + sustainability) / 3``, which
          saturates at an 8.3% yield.
        """
        dy = fin.get("dividend_yield", 0)
        yoc = fin.get("yield_on_cost", 0)
        sus = fin.get("payout_sustainability_score", 80)
        risk_free = fin.get("risk_free_real_yield")
        indicators = {
            "Dividend Yield": round(dy * 10, 2),
            "Yield on Cost": round(yoc * 10, 2),
            "Payout Sustainability": sus,
        }
        if risk_free is not None and risk_free > 0:
            yield_term = max(0.0, min(dy / (2 * risk_free) * 100, 100.0))
            terms = [yield_term, sus]
            if yoc:
                terms.append(min(yoc * 12, 100))
            indicators["Risk-free real yield"] = risk_free
            score = min(sum(terms) / len(terms), 100.0)
        else:
            score = min((min(dy * 12, 100) + min(yoc * 12, 100) + sus) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.DIVIDENDS,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.DIVIDENDS],
            indicators=indicators,
        )

    def _analyze_fii_capital_allocation(self, fin: dict) -> PillarScore:
        acq = fin.get("successful_acquisitions_3y", 0)
        disp = fin.get("disposal_success_ratio", 0.5)
        dil = fin.get("dilution_from_capital_raise", 0)
        indicators = {
            "Acquisitions (3y)": acq,
            "Disposal Success": round(disp * 100, 2),
            "Dilution Impact": round(dil * 100, 2),
        }
        score = min(
            (min(acq * 10, 100) + disp * 100 + max(0, 100 - dil * 200)) / 3, 100.0
        )
        return PillarScore(
            pillar=Pillar.CAPITAL_ALLOCATION,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.CAPITAL_ALLOCATION],
            indicators=indicators,
        )

    def _analyze_fii_resilience(self, fin: dict) -> PillarScore:
        lev = fin.get("leverage_to_npa", 0.3)
        mat = fin.get("weighted_avg_debt_maturity_years", 5)
        fixed = fin.get("fixed_debt_ratio", 0.8)
        indicators = {
            "Leverage/NPA": round(lev * 100, 2),
            "Debt Maturity": mat,
            "Fixed Debt Ratio": round(fixed * 100, 2),
        }
        score = min((max(0, 100 - lev * 150) + mat * 10 + fixed * 50) / 3, 100.0)
        return PillarScore(
            pillar=Pillar.RESILIENCE,
            score=round(score, 2),
            weight=self.pillar_weights[Pillar.RESILIENCE],
            indicators=indicators,
        )
