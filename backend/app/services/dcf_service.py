"""DCF 계산 Service (요구사항 22)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.company import Company
from app.schemas.dcf import DCFAssumptions, DCFResult
from app.services.financial_service import get_financial_statements, get_latest_close_price
from app.valuation.dcf import run_dcf


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
