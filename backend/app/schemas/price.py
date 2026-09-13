"""주가 데이터 스키마."""
from __future__ import annotations

from datetime import date as date_

from pydantic import BaseModel


class PricePoint(BaseModel):
    date: date_
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class EventMarker(BaseModel):
    """차트 위에 표시할 뉴스 Event 마커 (요구사항 7)."""

    date: date_
    news_id: int
    title: str
    event_type: str | None = None


class PriceHistoryResponse(BaseModel):
    ticker: str
    period: str
    prices: list[PricePoint]
    event_markers: list[EventMarker] = []
