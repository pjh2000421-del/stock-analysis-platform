"""
재무제표 원자료 및 파생 재무지표(Valuation/Profitability/Growth/Financial Health).

Point-in-Time 원칙 (요구사항 30):
- reported_at: 해당 재무 수치가 실제로 발생/집계된 회계기간 관련 시점
- available_at: 해당 수치가 "시장에 실제로 공개된" 시점 (공시일 등)
ML/분석에서는 반드시 available_at 기준으로만 데이터를 사용해야 미래 정보 누수를 막을 수 있다.
"""
from __future__ import annotations

from datetime import date as date_
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import SourceMetadataMixin


class FinancialStatement(Base):
    """재무제표 원자료 (연/분기)."""

    __tablename__ = "financial_statements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    period: Mapped[str] = mapped_column(String(20))  # 예: "2025Q4", "2025FY"
    reported_at: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    available_at: Mapped[date_ | None] = mapped_column(Date, nullable=True, index=True)

    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    capital_expenditure: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_outstanding: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 유동성/이자보상 비율 계산에 필요한 보조 계정
    current_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_liabilities: Mapped[float | None] = mapped_column(Float, nullable=True)
    inventory: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_expense: Mapped[float | None] = mapped_column(Float, nullable=True)
    depreciation_amortization: Mapped[float | None] = mapped_column(Float, nullable=True)

    # EV(기업가치)/순차입금 계산에 필요 (요구사항: EV/EBITDA, Net Debt/EBITDA)
    cash_and_equivalents: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_borrowings: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 감가상각비를 별도 공시하지 않는 대기업의 EBITDA 추정 fallback (현금흐름표 "조정" 합계)
    non_cash_adjustments_total: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    company = relationship("Company", back_populates="financial_statements")


class FinancialMetric(Base, SourceMetadataMixin):
    """
    파생 재무지표 (Valuation / Profitability / Growth / Financial Health).
    가능한 경우 원자료(FinancialStatement + 시장가)로부터 직접 계산하며,
    그 계산식과 출처를 SourceMetadataMixin 필드에 기록한다.
    """

    __tablename__ = "financial_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    date: Mapped[date_] = mapped_column(Date, index=True)

    # Valuation
    per: Mapped[float | None] = mapped_column(Float, nullable=True)
    # PER이 None인 이유가 데이터 부족이 아니라 "적자(당기순손실)"라서 배수 자체가
    # 의미 없는 경우 True. 화면에는 raw 음수 배수 대신 "적자"로 표시하기 위함.
    per_is_deficit: Mapped[bool] = mapped_column(Boolean, default=False)
    forward_per: Mapped[float | None] = mapped_column(Float, nullable=True)
    pbr: Mapped[float | None] = mapped_column(Float, nullable=True)
    # PBR이 None인 이유가 "자본잠식(자본총계 마이너스)"인 경우 True.
    pbr_is_deficit: Mapped[bool] = mapped_column(Boolean, default=False)
    psr: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    # EV/EBITDA가 None인 이유가 "적자(EBITDA가 0 이하)"인 경우 True.
    ev_ebitda_is_deficit: Mapped[bool] = mapped_column(Boolean, default=False)
    # 감가상각비를 단독 계정으로 찾지 못해 현금흐름표 "조정" 합계로 EBITDA를 근사 계산한 경우 True.
    ev_ebitda_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    peg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fcf_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    earnings_yield: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Profitability
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    roa: Mapped[float | None] = mapped_column(Float, nullable=True)
    roic: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    fcf_margin: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Growth
    revenue_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_income_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    fcf_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_cagr_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_cagr_5y: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Financial Health
    debt_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_debt_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    quick_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Capital cost (데이터 부족 시 None -> "데이터 없음" 표시)
    roic_minus_wacc: Mapped[float | None] = mapped_column(Float, nullable=True)
    wacc: Mapped[float | None] = mapped_column(Float, nullable=True)

    company = relationship("Company", back_populates="financial_metrics")
