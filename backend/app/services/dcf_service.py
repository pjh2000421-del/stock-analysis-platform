"""DCF 계산 Service (요구사항 22)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.company import Company
from app.schemas.dcf import DCFAssumptions, DCFResult, SuggestedDCFAssumptions
from app.services.beta_service import compute_company_beta
from app.services.financial_service import get_financial_statements, get_latest_close_price
from app.valuation.dcf import run_dcf
from app.valuation.wacc import estimate_wacc


def get_suggested_assumptions(db: Session, company: Company) -> SuggestedDCFAssumptions:
    """DCF Calculator 초기값으로 쓸, 종목별 제안 가정값(현재는 WACC만 종목별로 계산)을 반환한다.

    revenue_growth_rate/operating_margin 등 나머지 가정은 아직 종목별 자동 추정 로직이
    없어 DCFAssumptions의 기본값을 그대로 사용한다 - 이 부분을 근거 없이 추정해 보여주면
    오히려 사용자가 실제보다 정교한 값으로 오인할 수 있기 때문이다(요구사항 74).
    """
    settings = get_settings()
    statements = get_financial_statements(db, company)
    latest = statements[0] if statements else None

    default_assumptions = DCFAssumptions()
    beta = compute_company_beta(db, company)

    wacc_result = estimate_wacc(
        market_cap=company.market_cap,
        total_borrowings=latest.total_borrowings if latest else None,
        interest_expense=latest.interest_expense if latest else None,
        tax_rate=default_assumptions.tax_rate,
        beta=beta,
        risk_free_rate=settings.risk_free_rate,
        equity_risk_premium=settings.equity_risk_premium,
    )

    assumptions = default_assumptions.model_copy(update={"wacc": wacc_result.wacc})

    return SuggestedDCFAssumptions(
        assumptions=assumptions,
        wacc_calculation_method=wacc_result.calculation_method,
        wacc_is_estimated=wacc_result.beta_is_estimated or wacc_result.cost_of_debt_is_estimated,
        notes=wacc_result.notes,
    )


def calculate_dcf(db: Session, company: Company, assumptions: DCFAssumptions) -> DCFResult:
    statements = get_financial_statements(db, company)
    latest = statements[0] if statements else None

    base_revenue = latest.revenue if latest else None
    net_debt = None
    if latest and latest.liabilities is not None and latest.assets is not None:
        # 순차입금 근사치가 없으므로 부채총계를 보수적으로 사용 (TODO: 차입금 세부 계정 연동)
        net_debt = None  # 데이터 부족 시 N/A로 두어 임의 가정을 하지 않는다 (요구사항 74)

    shares_outstanding = latest.shares_outstanding if latest else None
    current_price = get_latest_close_price(db, company)

    return run_dcf(
        ticker=company.ticker,
        base_revenue=base_revenue,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        current_price=current_price,
        assumptions=assumptions,
    )
