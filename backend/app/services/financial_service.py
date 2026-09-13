"""
재무제표/재무지표 Service (요구사항 3, 18): Lazy Loading + Caching + 직접 계산.

흐름:
    1) DB(financial_statements)에 데이터가 있으면 재사용, 없거나 오래되면 OpenDART에서 갱신
    2) 최신 재무제표 + 현재가 + (가능하면)발행주식수로 valuation/metrics.py를 이용해
       재무지표를 직접 계산 (요구사항 74: 외부 사이트의 계산된 숫자 그대로 사용하지 않음)
    3) 계산 결과를 financial_metrics 테이블에 출처/계산식과 함께 저장(source_name 등)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.company import Company
from app.models.financial import FinancialMetric, FinancialStatement
from app.models.price import DailyPrice
from app.providers.financial_provider import get_financial_provider
from app.valuation import metrics as calc

logger = get_logger(__name__)

FINANCIALS_REFRESH_INTERVAL = timedelta(days=1)


def refresh_financial_statements(db: Session, company: Company) -> str:
    now = datetime.utcnow()
    if company.financials_last_updated and now - company.financials_last_updated < FINANCIALS_REFRESH_INTERVAL:
        return "cached"

    provider = get_financial_provider()
    result = provider.get_financial_statements(company.ticker)

    if result.status not in ("ok", "empty"):
        logger.info("재무제표 갱신 불가(%s): %s", company.ticker, result.message)
        return result.status

    existing_periods = {
        p
        for (p,) in db.execute(
            select(FinancialStatement.period).where(FinancialStatement.company_id == company.id)
        ).all()
    }

    for raw in result.data or []:
        if raw.period in existing_periods:
            continue
        db.add(
            FinancialStatement(
                company_id=company.id,
                period=raw.period,
                reported_at=raw.reported_at,
                available_at=raw.available_at,
                revenue=raw.revenue,
                operating_income=raw.operating_income,
                net_income=raw.net_income,
                assets=raw.assets,
                liabilities=raw.liabilities,
                equity=raw.equity,
                operating_cash_flow=raw.operating_cash_flow,
                free_cash_flow=raw.free_cash_flow,
                capital_expenditure=raw.capital_expenditure,
                shares_outstanding=raw.shares_outstanding,
                current_assets=raw.current_assets,
                current_liabilities=raw.current_liabilities,
                inventory=raw.inventory,
                interest_expense=raw.interest_expense,
                depreciation_amortization=raw.depreciation_amortization,
                cash_and_equivalents=raw.cash_and_equivalents,
                total_borrowings=raw.total_borrowings,
                non_cash_adjustments_total=raw.non_cash_adjustments_total,
                source_name=result.source_name,
                retrieved_at=result.retrieved_at,
            )
        )

    company.financials_last_updated = now
    db.add(company)
    db.commit()
    return result.status


def get_financial_statements(db: Session, company: Company) -> list[FinancialStatement]:
    refresh_financial_statements(db, company)
    return list(
        db.execute(
            select(FinancialStatement)
            .where(FinancialStatement.company_id == company.id)
            .order_by(FinancialStatement.period.desc())
        )
        .scalars()
        .all()
    )


def get_latest_close_price(db: Session, company: Company) -> float | None:
    row = db.execute(
        select(DailyPrice.close)
        .where(DailyPrice.company_id == company.id)
        .order_by(DailyPrice.date.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def compute_and_store_financial_metrics(db: Session, company: Company) -> FinancialMetric:
    """최신 재무제표 + 현재가를 이용해 재무지표를 직접 계산하고 오늘 날짜로 저장한다."""
    statements = get_financial_statements(db, company)
    latest = statements[0] if statements else None
    prev = statements[1] if len(statements) > 1 else None

    price = get_latest_close_price(db, company)
    market_cap = company.market_cap

    eps_calc = calc.eps(latest.net_income if latest else None, latest.shares_outstanding if latest else None)
    bps_calc = calc.bps(latest.equity if latest else None, latest.shares_outstanding if latest else None)
    per_calc = calc.per(price, eps_calc.value)
    pbr_calc = calc.pbr(price, bps_calc.value)
    psr_calc = calc.psr(market_cap, latest.revenue if latest else None)

    avg_equity = None
    if latest and latest.equity is not None:
        avg_equity = (
            (latest.equity + prev.equity) / 2 if prev and prev.equity is not None else latest.equity
        )
    avg_assets = None
    if latest and latest.assets is not None:
        avg_assets = (
            (latest.assets + prev.assets) / 2 if prev and prev.assets is not None else latest.assets
        )

    roe_calc = calc.roe(latest.net_income if latest else None, avg_equity)
    roa_calc = calc.roa(latest.net_income if latest else None, avg_assets)
    op_margin_calc = calc.operating_margin(
        latest.operating_income if latest else None, latest.revenue if latest else None
    )
    net_margin_calc = calc.net_margin(latest.net_income if latest else None, latest.revenue if latest else None)

    fcf_calc = calc.fcf(
        latest.operating_cash_flow if latest else None, latest.capital_expenditure if latest else None
    )
    fcf_margin_calc = calc.fcf_margin(fcf_calc.value, latest.revenue if latest else None)

    debt_equity_calc = calc.debt_equity(latest.liabilities if latest else None, latest.equity if latest else None)
    current_ratio_calc = calc.current_ratio(
        latest.current_assets if latest else None, latest.current_liabilities if latest else None
    )
    quick_ratio_calc = calc.quick_ratio(
        latest.current_assets if latest else None,
        latest.inventory if latest else None,
        latest.current_liabilities if latest else None,
    )
    interest_coverage_calc = calc.interest_coverage(
        latest.operating_income if latest else None, latest.interest_expense if latest else None
    )

    revenue_growth_calc = calc.revenue_growth_yoy(
        latest.revenue if latest else None, prev.revenue if prev else None
    )

    # EV/EBITDA, Net Debt/EBITDA (요구사항 18): EBITDA는 영업이익+감가상각비,
    # 순차입금은 총차입금(단기+유동성장기부채+사채+장기차입금)-현금성자산으로 직접 계산한다.
    ebitda_calc = calc.ebitda(
        latest.operating_income if latest else None,
        latest.depreciation_amortization if latest else None,
        latest.non_cash_adjustments_total if latest else None,
    )
    net_debt_calc = calc.net_debt(
        latest.total_borrowings if latest else None, latest.cash_and_equivalents if latest else None
    )
    enterprise_value_calc = calc.enterprise_value(market_cap, net_debt_calc.value)
    ev_ebitda_calc = calc.ev_ebitda(enterprise_value_calc.value, ebitda_calc.value, ebitda_calc.is_estimated)
    net_debt_ebitda_calc = calc.net_debt_ebitda(
        net_debt_calc.value, ebitda_calc.value, ebitda_calc.is_estimated
    )

    metric = FinancialMetric(
        company_id=company.id,
        date=date.today(),
        per=per_calc.value,
        per_is_deficit=per_calc.is_deficit,
        pbr=pbr_calc.value,
        pbr_is_deficit=pbr_calc.is_deficit,
        psr=psr_calc.value,
        ev_ebitda=ev_ebitda_calc.value,
        ev_ebitda_is_deficit=ev_ebitda_calc.is_deficit,
        ev_ebitda_is_estimated=ev_ebitda_calc.is_estimated,
        net_debt=net_debt_calc.value,
        net_debt_ebitda=net_debt_ebitda_calc.value,
        roe=roe_calc.value,
        roa=roa_calc.value,
        operating_margin=op_margin_calc.value,
        net_margin=net_margin_calc.value,
        fcf_margin=fcf_margin_calc.value,
        debt_equity=debt_equity_calc.value,
        current_ratio=current_ratio_calc.value,
        quick_ratio=quick_ratio_calc.value,
        interest_coverage=interest_coverage_calc.value,
        revenue_growth_yoy=revenue_growth_calc.value,
        source_name="직접 계산 (OpenDART + 시장가)",
        calculation_method="per=Price/EPS, pbr=Price/BPS, roe=NetIncome/AvgEquity 등 (app/valuation/metrics.py 참조)",
        retrieved_at=datetime.utcnow(),
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric
