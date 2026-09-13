"""종합 기업 분석 점수 Service (요구사항 25)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config.loader import load_scoring_weights
from app.models.company import Company
from app.models.financial import FinancialMetric
from app.schemas.overview import CompositeScoreResponse, ScoreBreakdown
from app.services.financial_service import compute_and_store_financial_metrics
from app.valuation.scoring import compute_category_score, compute_total_score


def get_latest_metric(db: Session, company: Company) -> FinancialMetric:
    """캐시된 최신 FinancialMetric이 있으면 재사용하고, 없으면 새로 계산한다."""
    from sqlalchemy import select

    row = db.execute(
        select(FinancialMetric)
        .where(FinancialMetric.company_id == company.id)
        .order_by(FinancialMetric.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        row = compute_and_store_financial_metrics(db, company)
    return row


# 하위 호환 별칭 (기존 내부 호출부 유지)
_latest_metric = get_latest_metric


def get_composite_score(db: Session, company: Company) -> CompositeScoreResponse:
    metric = _latest_metric(db, company)
    weights_config = load_scoring_weights()

    category_raw_metrics = {
        "valuation": {"per": metric.per, "pbr": metric.pbr, "ev_ebitda": metric.ev_ebitda},
        "growth": {
            "revenue_growth_yoy": metric.revenue_growth_yoy,
            "eps_growth_yoy": metric.eps_growth_yoy,
            "operating_income_growth_yoy": metric.operating_income_growth_yoy,
        },
        "profitability": {
            "roe": metric.roe,
            "operating_margin": metric.operating_margin,
            "net_margin": metric.net_margin,
        },
        "financial_health": {
            "debt_equity": metric.debt_equity,
            "current_ratio": metric.current_ratio,
            "interest_coverage": metric.interest_coverage,
        },
    }

    breakdowns: list[ScoreBreakdown] = []
    category_scores: dict[str, float | None] = {}
    for category, raw in category_raw_metrics.items():
        score, components = compute_category_score(category, raw)
        category_scores[category] = score
        breakdowns.append(
            ScoreBreakdown(
                category=category,
                score=score,
                weight=weights_config["category_weights"][category],
                components=components,
                is_na=score is None,
            )
        )

    total_score = compute_total_score(category_scores)

    return CompositeScoreResponse(
        ticker=company.ticker,
        scores=breakdowns,
        total_score=total_score,
        weights_config_version=weights_config["version"],
    )
