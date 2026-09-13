"""재무제표/재무지표 스키마."""
from __future__ import annotations

from datetime import date as date_

from pydantic import BaseModel

from app.schemas.common import ValueWithSource


class FinancialStatementOut(BaseModel):
    period: str
    reported_at: date_ | None = None
    available_at: date_ | None = None
    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    assets: float | None = None
    liabilities: float | None = None
    equity: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None


class ValuationMetrics(BaseModel):
    per: ValueWithSource
    forward_per: ValueWithSource
    pbr: ValueWithSource
    psr: ValueWithSource
    ev_ebitda: ValueWithSource
    peg: ValueWithSource
    fcf_yield: ValueWithSource
    earnings_yield: ValueWithSource


class ProfitabilityMetrics(BaseModel):
    roe: ValueWithSource
    roa: ValueWithSource
    roic: ValueWithSource
    gross_margin: ValueWithSource
    operating_margin: ValueWithSource
    net_margin: ValueWithSource
    fcf_margin: ValueWithSource


class GrowthMetrics(BaseModel):
    revenue_growth_yoy: ValueWithSource
    eps_growth_yoy: ValueWithSource
    operating_income_growth_yoy: ValueWithSource
    fcf_growth_yoy: ValueWithSource
    revenue_cagr_3y: ValueWithSource
    revenue_cagr_5y: ValueWithSource


class FinancialHealthMetrics(BaseModel):
    debt_equity: ValueWithSource
    net_debt: ValueWithSource
    net_debt_ebitda: ValueWithSource
    current_ratio: ValueWithSource
    quick_ratio: ValueWithSource
    interest_coverage: ValueWithSource


class CapitalCostMetrics(BaseModel):
    roic: ValueWithSource
    wacc: ValueWithSource
    roic_minus_wacc: ValueWithSource


class CompanyMetricsResponse(BaseModel):
    ticker: str
    as_of: date_ | None = None
    valuation: ValuationMetrics
    profitability: ProfitabilityMetrics
    growth: GrowthMetrics
    financial_health: FinancialHealthMetrics
    capital_cost: CapitalCostMetrics


class PeerComparisonRow(BaseModel):
    label: str  # 기업명 또는 "업종 Median"
    ticker: str | None = None  # 기업 행이면 종목코드, "업종 Median" 집계행이면 None(클릭 불가)
    per: float | None = None
    per_is_deficit: bool = False  # PER이 없는 이유가 적자(당기순손실)인 경우 True
    ev_ebitda: float | None = None
    ev_ebitda_is_deficit: bool = False  # EV/EBITDA가 없는 이유가 적자(EBITDA<=0)인 경우 True
    # 감가상각비를 단독 계정으로 찾지 못해 현금흐름표 "조정" 합계로 EBITDA를 근사한 경우 True.
    ev_ebitda_is_estimated: bool = False
    pbr: float | None = None
    pbr_is_deficit: bool = False  # PBR이 없는 이유가 자본잠식인 경우 True
    roe: float | None = None


class PeerComparisonResponse(BaseModel):
    ticker: str
    industry: str | None = None
    rows: list[PeerComparisonRow]
    discount_premium: dict[str, float | None]  # {"per": -19.0, "pbr": -30.0} (% , 업종 대비)


class HistoricalValuationPoint(BaseModel):
    metric: str  # "per" | "pbr" | "ev_ebitda"
    current: float | None
    avg_5y: float | None
    median_5y: float | None
    percentile_5y: float | None  # 0~100


class HistoricalValuationResponse(BaseModel):
    ticker: str
    points: list[HistoricalValuationPoint]
