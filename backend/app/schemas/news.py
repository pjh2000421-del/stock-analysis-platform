"""뉴스 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.event import NewsEventOut


class NewsItem(BaseModel):
    id: int
    title: str
    summary: str | None = None
    source: str | None = None
    published_at: datetime | None = None
    url: str
    sentiment_score: float | None = None
    importance_score: float | None = None
    event_type: str | None = None
    event_subtype: str | None = None
    is_mock: bool = False
    # 이 기사를 실제로 가져온 Provider (예: "naver_news", "newsdata_io", "gnews", "internal_db")
    provider: str | None = None
    # 같은 사건을 보도한 대표 기사의 id. 이 값이 None이면 자신이 대표이거나 단독 기사.
    cluster_head_id: int | None = None
    # 같은 사건으로 클러스터링된 다른 기사 수(조회된 목록 범위 내 근사치)
    related_count: int = 0


class NewsListResponse(BaseModel):
    ticker: str
    # Provider 다변화: {"naver_news": "ok", "newsdata_io": "skipped", "gnews": "unavailable", "bigkinds": "not_used_by_default"}
    provider_status: dict[str, str]
    news: list[NewsItem]


class NewsDetail(NewsItem):
    events: list[NewsEventOut] = []


class DailySentimentSummary(BaseModel):
    date: str
    mean: float | None = None
    median: float | None = None
    weighted: float | None = None
    news_count: int = 0
