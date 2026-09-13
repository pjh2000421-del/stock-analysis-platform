"""뉴스 Event 구조화 / 과거 유사사례 / Event Study 스키마 (Phase2)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsEventOut(BaseModel):
    id: int
    event_type: str
    event_subtype: str | None = None
    product: str | None = None
    technology: str | None = None
    counterparty: str | None = None
    country: str | None = None
    amount_nominal: float | None = None
    amount_real: float | None = None
    revenue_ratio: float | None = None
    market_cap_ratio: float | None = None
    development_stage: str | None = None
    commercialization_stage: str | None = None
    industry: str | None = None
    sentiment: float | None = None
    importance: float | None = None
    event_date: datetime | None = None


class MarketReactionOut(BaseModel):
    return_0d: float | None = None
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None
    excess_return_1d: float | None = None
    excess_return_5d: float | None = None
    excess_return_20d: float | None = None
    volatility_before: float | None = None
    volatility_after: float | None = None
    max_upside: float | None = None
    max_drawdown: float | None = None
    benchmark_index: str | None = None


class SimilarHistoricalEvent(BaseModel):
    similarity_score: float
    event: NewsEventOut
    company_name: str
    ticker: str
    market_reaction: MarketReactionOut | None = None


class SimilarEventGroupStats(BaseModel):
    """유사 뉴스 집단 통계 (요구사항 17)."""

    total_count: int
    up_count_1d: int
    up_count_5d: int
    up_count_20d: int
    mean_return_5d: float | None = None
    median_return_5d: float | None = None
    mean_excess_return_5d: float | None = None
    mean_volatility_change_pct: float | None = None
    return_distribution_5d: list[float] = []  # histogram 원자료 (Return 값 리스트)


class SimilarNewsResponse(BaseModel):
    news_id: int
    top_similar: list[SimilarHistoricalEvent]
    group_stats: SimilarEventGroupStats
    similarity_config_version: str


class EventStudyPoint(BaseModel):
    offset_days: int  # -20, -5, 0, 1, 5, 20, 60
    return_pct: float | None = None
    volume: int | None = None
    volatility: float | None = None


class EventStudyResponse(BaseModel):
    news_id: int
    # "ok": 정상 계산됨 / "insufficient_data": 이벤트 직후라 반응 데이터가 아직 부족함 /
    # "no_event": 이 뉴스에서 추출된 Event 정보가 없음
    status: str = "ok"
    message: str | None = None
    current_event: list[EventStudyPoint] = []
    summary: MarketReactionOut | None = None
    # 유사 과거 사례 오버레이는 Historical Similarity 기능(다음 단계)에서 채워진다.
    overlay_historical: dict[int, list[EventStudyPoint]] = {}
