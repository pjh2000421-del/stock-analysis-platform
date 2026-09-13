"""
Simple View Service (요구사항 23).

전문 금융용어를 최소화하고, 단정적 표현을 피하며 근거 중심 문장을 생성한다.
(요구사항 61: "저평가 주식이다" 대신 "동종업체 대비 valuation multiple이 낮은 편입니다" 형태)
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.news import News
from app.schemas.overview import SimpleLevel, SimpleViewResponse
from app.services.scoring_service import get_composite_score


def _score_to_level(score: float | None, labels: tuple[str, str, str]) -> str:
    """0~100 점수를 3단계 라벨로 변환. labels = (낮음, 보통, 높음)."""
    if score is None:
        return "데이터 부족"
    if score < 40:
        return labels[0]
    if score < 70:
        return labels[1]
    return labels[2]


def _news_sentiment_level(db: Session, company: Company) -> SimpleLevel:
    rows = list(
        db.execute(
            select(News.sentiment_score)
            .where(News.company_id == company.id, News.sentiment_score.is_not(None))
            .order_by(News.published_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    if not rows:
        return SimpleLevel(label="데이터 부족", detail="최근 수집된 뉴스 감정 데이터가 없습니다.")

    avg = sum(rows) / len(rows)
    if avg > 0.15:
        return SimpleLevel(label="긍정적", detail=f"최근 뉴스 {len(rows)}건의 평균 감정 점수가 긍정적입니다.")
    if avg < -0.15:
        return SimpleLevel(label="부정적", detail=f"최근 뉴스 {len(rows)}건의 평균 감정 점수가 부정적입니다.")
    return SimpleLevel(label="중립적", detail=f"최근 뉴스 {len(rows)}건의 평균 감정 점수가 중립적입니다.")


def get_simple_view(db: Session, company: Company) -> SimpleViewResponse:
    composite = get_composite_score(db, company)
    scores_by_category = {s.category: s.score for s in composite.scores}

    price_level = SimpleLevel(
        label=_score_to_level(scores_by_category.get("valuation"), ("비싼 편", "보통", "저렴한 편")),
        detail="Valuation 지표(PER/PBR/EV-EBITDA)를 정규화해 산출한 점수 기준이며, "
        "값이 낮을수록(저PER 등) 상대적으로 저렴한 것으로 해석됩니다.",
    )
    growth_level = SimpleLevel(
        label=_score_to_level(scores_by_category.get("growth"), ("낮음", "보통", "높음")),
        detail="매출/영업이익 성장률 기반 점수입니다.",
    )
    profitability_level = SimpleLevel(
        label=_score_to_level(scores_by_category.get("profitability"), ("낮음", "보통", "양호")),
        detail="ROE, 영업이익률, 순이익률 기반 점수입니다.",
    )
    financial_health_level = SimpleLevel(
        label=_score_to_level(scores_by_category.get("financial_health"), ("주의", "보통", "안정적")),
        detail="부채비율, 유동비율, 이자보상배율 기반 점수입니다.",
    )
    news_level = _news_sentiment_level(db, company)

    # Phase2(과거 유사사례)/Phase3(AI 예측) 미구현 상태에서는 명확히 "데이터 없음"으로 표시
    historical_level = SimpleLevel(
        label="데이터 없음", detail="과거 유사 뉴스 분석 기능은 다음 개발 단계(Phase2)에서 제공될 예정입니다."
    )
    ai_outlook_level = SimpleLevel(
        label="데이터 없음", detail="AI 미래 예측 기능은 다음 개발 단계(Phase3)에서 제공될 예정입니다."
    )

    risk_factors: list[str] = []
    if scores_by_category.get("valuation") is not None and scores_by_category["valuation"] < 40:
        risk_factors.append(
            "설정된 기준(업종 평균적 관행치) 대비 Valuation 부담이 있는 편입니다. "
            "실제 동종업체와의 비교는 Pro View의 'Peer Comparison' 표를 참고하세요."
        )
    if scores_by_category.get("financial_health") is not None and scores_by_category["financial_health"] < 40:
        risk_factors.append("재무 안정성 지표가 상대적으로 취약한 편입니다.")
    if not risk_factors:
        risk_factors.append("현재 계산된 지표 기준으로는 두드러진 위험요인이 식별되지 않았습니다.")

    return SimpleViewResponse(
        ticker=company.ticker,
        company_name=company.company_name,
        price_level=price_level,
        growth_level=growth_level,
        profitability_level=profitability_level,
        financial_health_level=financial_health_level,
        news_sentiment_level=news_level,
        historical_similarity_level=historical_level,
        ai_outlook=ai_outlook_level,
        risk_factors=risk_factors,
    )
