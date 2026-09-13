"""Watchlist / Notification 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WatchlistItemCreate(BaseModel):
    ticker: str
    notify_all_news: bool = False
    notify_event_types: list[str] | None = None


class WatchlistItemOut(BaseModel):
    id: int
    ticker: str
    company_name: str
    current_price: float | None = None
    price_change_pct: float | None = None
    latest_important_news_title: str | None = None
    notify_all_news: bool
    notify_event_types: list[str] | None = None


class NotificationOut(BaseModel):
    id: int
    ticker: str
    company_name: str
    news_id: int
    news_title: str
    importance: float | None = None
    read: bool
    created_at: datetime
