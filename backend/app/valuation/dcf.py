"""DCF(현금흐름할인법) 계산기 (요구사항 22).

사용자가 조정한 가정(Revenue Growth, Operating Margin, Tax Rate, Capex,
Working Capital, WACC, Terminal Growth)으로 기업가치를 추정한다.
결과는 어디까지나 입력 가정에 의존하는 추정치이며 "정답"이 아님을 명시한다.
"""
from __future__ import annotations

from app.schemas.dcf import DCFAssumptions, DCFResult


def run_dcf(
    ticker: str,
    base_revenue: float | None,
    net_debt: float | None,
    shares_outstanding: float | None,
    current_price: float | None,
    assumptions: DCFAssumptions,
) -> DCFResult:
    if not base_revenue or base_revenue <= 0:
        # 기준 매출이 없으면 추정 자체가 불가능하므로 0 기반 결과를 명확히 N/A로 표시
        return DCFResult(
            ticker=ticker,
            assumptions=assumptions,
            projected_fcf=[],
            terminal_value=0.0,
            enterprise_value=0.0,
            net_debt=net_debt,
            equity_value=0.0,
            shares_outstanding=shares_outstanding,
            estimated_price_per_share=None,
            current_price=current_price,
            upside_pct=None,
            note="기준 매출 데이터가 없어 DCF를 계산할 수 없습니다 (N/A).",
        )

    revenue = base_revenue
    projected_fcf: list[float] = []
    for _ in range(assumptions.projection_years):
        revenue = revenue * (1 + assumptions.revenue_growth_rate)
        operating_income = revenue * assumptions.operating_margin
        nopat = operating_income * (1 - assumptions.tax_rate)
        capex = revenue * assumptions.capex_pct_revenue
        wc_change = revenue * assumptions.working_capital_pct_revenue
        # 단순화된 FCFF: NOPAT - Capex - 운전자본 증가분 (감가상각비는 Capex와 상쇄된다고 가정)
        year_fcf = nopat - capex - wc_change
        projected_fcf.append(year_fcf)

    wacc = assumptions.wacc
    g = assumptions.terminal_growth_rate
    discounted_fcf = [f / ((1 + wacc) ** (i + 1)) for i, f in enumerate(projected_fcf)]

    if wacc <= g:
        terminal_value = 0.0
        pv_terminal_value = 0.0
    else:
        terminal_value = projected_fcf[-1] * (1 + g) / (wacc - g)
        pv_terminal_value = terminal_value / ((1 + wacc) ** assumptions.projection_years)

    enterprise_value = sum(discounted_fcf) + pv_terminal_value
    equity_value = enterprise_value - (net_debt or 0.0)

    price_per_share = None
    upside_pct = None
    if shares_outstanding and shares_outstanding > 0:
        price_per_share = equity_value / shares_outstanding
        if current_price and current_price > 0:
            upside_pct = (price_per_share - current_price) / current_price * 100

    return DCFResult(
        ticker=ticker,
        assumptions=assumptions,
        projected_fcf=projected_fcf,
        terminal_value=terminal_value,
        enterprise_value=enterprise_value,
        net_debt=net_debt,
        equity_value=equity_value,
        shares_outstanding=shares_outstanding,
        estimated_price_per_share=price_per_share,
        current_price=current_price,
        upside_pct=upside_pct,
    )
