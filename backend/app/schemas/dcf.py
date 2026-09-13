"""DCF Calculator 스키마 (요구사항 22)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DCFAssumptions(BaseModel):
    revenue_growth_rate: float = Field(0.05, description="연평균 매출 성장률 (예: 0.05 = 5%)")
    operating_margin: float = Field(0.15, description="영업이익률")
    tax_rate: float = Field(0.22, description="법인세율")
    capex_pct_revenue: float = Field(0.05, description="매출 대비 Capex 비중")
    working_capital_pct_revenue: float = Field(0.02, description="매출 대비 운전자본 변동 비중")
    wacc: float = Field(0.09, description="가중평균자본비용")
    terminal_growth_rate: float = Field(0.02, description="영구성장률")
    projection_years: int = Field(5, description="추정 기간(년)")


class DCFRequest(BaseModel):
    ticker: str
    assumptions: DCFAssumptions = DCFAssumptions()


class DCFResult(BaseModel):
    ticker: str
    assumptions: DCFAssumptions
    projected_fcf: list[float]
    terminal_value: float
    enterprise_value: float
    net_debt: float | None
    equity_value: float
    shares_outstanding: float | None
    estimated_price_per_share: float | None
    current_price: float | None
    upside_pct: float | None
    note: str = "DCF 결과는 입력 가정에 따라 크게 달라질 수 있는 추정치이며 '정답'이 아닙니다."
